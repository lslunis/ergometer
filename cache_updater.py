from contextlib import contextmanager
from datetime import timedelta
from enum import Enum
from itertools import chain, islice, repeat
import struct

from sqlalchemy import Column, Integer, String, create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .time import day_start_of, is_on_day, imprecise_clock, max_time
from .util import retry_on, PositionError, die_unless


@contextmanager
def connect(db_address):
    engine = create_engine(db_address)

    try:
        # Override pysqlite's broken transaction handling
        # https://docs.sqlalchemy.org/en/13/dialects/sqlite.html#pysqlite-serializable
        @event.listens_for(engine, "connect")
        def do_connect(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def do_begin(connection):
            connection.execute("BEGIN")

        Base.metadata.create_all(engine)

        yield sessionmaker(bind=engine)

    finally:
        engine.dispose()


Base = declarative_base()


class HostPosition(Base):
    __tablename__ = "host_positions"
    host = Column(String, primary_key=True)
    position = Column(Integer, nullable=False)

    def __str__(self):
        return f"{self.host}:{self.position}"

    @staticmethod
    def update(session, host, data, position):
        host_position = session.query(HostPosition).get(host)
        if not host_position:
            host_position = HostPosition(host=host, position=0)
            session.add(host_position)
        if position != host_position.position:
            raise PositionError(f"expected {host_position}, got {position}")
        host_position.position += len(data)


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    value = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)

    @staticmethod
    def get(session, event_type):
        die_unless(event_type.default_value, f"unexpected: {event_type}")
        id = event_type.value
        setting = session.query(Setting).get(id)
        exists = setting is not None
        if not exists:
            setting = Setting(id=id, value=event_type.default_value, time=0)
            session.add(setting)
        if event_type == EventType.rest_target:
            if exists:
                session.execute("DROP INDEX rests")
            rest_target = setting.value
            session.execute(
                f"CREATE INDEX rests ON pauses(end) WHERE end - start >= {rest_target}"
            )
        return setting

    @property
    def name(self):
        return EventType(self.id).name

    def update_if_newer(self, value, time):
        if self.time < time:
            self.value = value


class Pause(Base):
    __tablename__ = "pauses"
    start = Column(Integer, nullable=False, unique=True)
    end = Column(Integer, primary_key=True)

    def __eq__(self, other):
        return (
            isinstance(other, Pause)
            and self.start == other.start
            and self.end == other.end
        )

    def __repr__(self):
        return f"<Pause {self.start} {self.end}>"

    @staticmethod
    def session_interval_cache(session):
        rest_target = Setting.get(session, EventType.rest_target).value
        rests = (
            session.query(Pause)
            .order_by(Pause.end.desc())
            .filter((Pause.end - Pause.start) >= rest_target)
        )
        last_rest, prior_rest = islice(chain(rests.limit(2), repeat(None)), 2)
        return dict(
            session_start=prior_rest.end if prior_rest else 0,
            session_end=last_rest.start if last_rest else 0,
        )

    @staticmethod
    def daily_activity_total(session, day_start):
        day_end = day_start + timedelta(days=1).total_seconds()
        pauses = (
            session.query(Pause)
            .filter(Pause.start < day_end)  # drop pauses that are in the future
            .filter(Pause.end > day_start)  # drops pauses that are in the past
            .order_by(Pause.end)
        )
        total = 0
        prior_pause = None
        for pause in pauses:
            if prior_pause:
                total += pause.start - prior_pause.end
            prior_pause = pause
        return total


min_span = 15


def clip_span(span):
    return 0 if span < min_span else span


class PauseUpdater:
    def __init__(self, session):
        self.session = session
        self.start = None
        self.pause = None
        self.updated = False

    def seek(self, time):
        if self.pause and self.start <= time < self.pause.end:
            return
        self.pause = (
            self.session.query(Pause)
            .filter(time < Pause.end)
            .order_by(Pause.end)
            .limit(1)
            .one_or_none()
        )
        if not self.pause:
            self.pause = Pause(start=0, end=max_time)
            self.session.add(self.pause)
        self.start = min(time, self.pause.start)

    def update(self, time, value):
        # enforces non-overlapping intervals
        die_unless(value == 1, f"unexpected value: {value}")
        self.seek(time)
        left_span = time - self.pause.start
        if left_span < 0:
            return 0

        span = self.pause.end - self.pause.start
        right_span = span - left_span - value
        left_span = clip_span(left_span)
        right_span = clip_span(right_span)
        activity_increase = span - left_span - right_span
        die_unless(
            0 < activity_increase < 2 * min_span,
            f"unexpected activity_increase: {activity_increase}",
        )

        if right_span:
            self.pause.start = self.pause.end - right_span
        else:
            self.session.delete(self.pause)
            self.session.flush()
            self.pause = None

        if left_span:
            self.session.add(Pause(start=(time - left_span), end=time))
            self.start = time

        self.updated = True
        return activity_increase


class EventType(Enum):
    action = 0
    daily_target = (1, timedelta(hours=8))
    session_target = (2, timedelta(hours=1))
    rest_target = (3, timedelta(minutes=5))

    def __new__(cls, value, default=None):
        self = object.__new__(cls)
        self._value_ = value
        if default:
            self.default_value = default.total_seconds()
        return self


data_format = "<BxxxIQ"


@retry_on(PositionError)
async def cache_updater(cache, broker):
    Session = connect("sqlite:///cache.db")
    host_positions = initialize_cache(cache, imprecise_clock(), Session())
    async for args in broker.subscribe(host_positions):
        update_cache(cache, imprecise_clock(), Session(), *args)


def initialize_cache(cache, now, session):
    today_start = day_start_of(now)
    delta = {
        **{s.name: s.value for s in session.query(Setting)},
        "day_start": today_start,
        "daily_total": Pause.daily_activity_total(session, today_start),
        **Pause.session_interval_cache(session),
    }
    host_positions = {hp.host: hp.position for hp in session.query(HostPosition)}
    session.commit()
    cache.update(delta)
    return host_positions


def update_cache(cache, now, session, host, data, position):
    HostPosition.update(session, host, data, position)

    today_start = day_start_of(now)
    day_start = cache["day_start"]
    daily_total = cache["daily_total"]
    if day_start != today_start:
        day_start = today_start
        daily_total = None
    pause_updater = PauseUpdater(session)

    for event_type_id, value, time in struct.iter_unpack(data_format, data):
        event_type = EventType(event_type_id)
        if event_type == EventType.action:
            activity_increase = pause_updater.update(time, value)
            if daily_total is not None and is_on_day(time, day_start):
                # this could attribute the activity_increase to the wrong day_start if
                # activity occurs at day_start boundary, but it can only be wrong
                # by less than min_idle seconds
                daily_total += activity_increase
        else:
            setting = Setting.get(session, event_type)
            setting.update_if_newer(value, time)

    delta = {
        setting.name: setting.value
        for setting in session.dirty
        if isinstance(setting, Setting)
    }
    if daily_total is None:
        daily_total = Pause.daily_activity_total(session, today_start)
    delta.update(day_start=day_start, daily_total=daily_total)
    if pause_updater.updated:
        delta.update(Pause.session_interval_cache(session))
    session.commit()
    cache.update(delta)


def metrics_at(
    now,
    daily_target,
    session_target,
    rest_target,
    day_start,
    daily_total,
    session_start,
    rest_start,
):
    rest_value = now - rest_start
    return dict(
        daily_target=daily_target,
        session_target=session_target,
        rest_target=rest_target,
        daily_value=daily_total if is_on_day(now, day_start) else 0,
        session_value=now - session_start if rest_value < rest_target else 0,
        rest_value=rest_value,
    )
