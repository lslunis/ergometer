from enum import Enum
from itertools import chain, islice, repeat
from contextlib import contextmanager
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


# TODO: rename to Setting
class Target(Base):
    __tablename__ = "targets"
    id = Column(Integer, primary_key=True)
    target = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)

    @staticmethod
    def get(session, kind):
        id = kind.value
        target = session.query(Target).get(id)
        if target is None:
            target = Target(id=id, time=0)
            session.add(target)
        return target

    @staticmethod
    def as_state(*targets):
        return {Kind(t.id).name: t.target for t in targets}

    def update_if_newer(self, target, time):
        if self.time < time:
            self.target = target
            return True


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
    def as_state(session):
        rest_target = Target.get(session, Kind.rest_target).target
        rests = (
            session.query(Pause)
            .order_by(Pause.end.desc())
            .filter((Pause.end - Pause.start) >= rest_target)
        )
        last_rest, prior_rest = islice(chain(rests.limit(2), repeat(None)), 2)
        return dict(
            session_start=prior_rest.end if prior_rest else 0,
            rest_start=last_rest.start if last_rest else 0,
        )

    @staticmethod
    def daily_activity_total(session, day):
        pauses = (
            session.query(Pause)
            .filter(Pause.start < day + 86400)  # drop pauses that are in the future
            .filter(Pause.end > day)  # drops pauses that are in the past
            .orderby(Pause.end)
        )
        total = 0
        for i in range(1, len(pauses)):
            total += pauses[i].start - pauses[i - 1].end
        return total


min_span = 15


def clip_span(span):
    return 0 if span < min_span else span


class PauseUpdater:
    def __init__(self, session):
        self.session = session
        self.start = None
        self.pause = None

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
        total = span - left_span - right_span
        die_unless(0 < total < 2 * min_span, f"unexpected total: {total}")

        if right_span:
            self.pause.start = self.pause.end - right_span
        else:
            self.session.delete(self.pause)
            self.session.flush()
            self.pause = None

        if left_span:
            self.session.add(Pause(start=(time - left_span), end=time))
            self.start = time

        return total


# TODO: rename kind to make it more specific


class Kind(Enum):
    daily_target = 1
    session_target = 2
    rest_target = 3
    action = 4


# TODO: rename state to reflect its functionality as cache


@retry_on(PositionError)
async def state_updater(state, broker):
    Session = connect("sqlite:///state.db")
    host_positions = initialize_state(state, imprecise_clock(), Session())
    async for args in broker.subscribe(host_positions):
        update_state(state, imprecise_clock(), Session(), *args)


def initialize_state(state, now, session):
    today = day_start_of(now)
    delta = {
        **Target.as_state(*session.query(Target)),
        "day": today,
        "daily_total": Pause.daily_activity_total(session, today),
        **Pause.as_state(session),
    }
    host_positions = {hp.host: hp.position for hp in session.query(HostPosition)}
    session.commit()
    state.update(delta)
    return host_positions


# TODO: rename all instances of "day" to "day_start"
def update_state(state, now, session, host, data, position):
    host_position = session.query(HostPosition).get(host)
    if position != host_position.position:
        raise PositionError(f"expected {host_position}, got {position}")
    host_position.position += len(data)

    updated_targets = set()
    today = day_start_of(now)
    day = state["day"]
    daily_total = state["daily_total"]
    if day != today:
        day = today
        daily_total = None
    pauses_changed = False
    pause_updater = PauseUpdater(session)

    for kind_value, value, time in struct.iter_unpack("<BxxxIQ", data):
        kind = Kind(kind_value)
        if kind == Kind.action:
            increment = pause_updater.update(time, value)
            if increment:
                pauses_changed = True
            if daily_total is not None and day == day_start_of(time):
                # this could attribute the increment to the wrong day if
                # activity occurs at day boundary, but it can only be wrong
                # by less than min_idle seconds
                daily_total += increment
        else:
            target = Target.get(session, kind)
            if target.update_if_newer(value, time):
                updated_targets.add(target)
    delta = Target.as_state(*updated_targets)
    if daily_total is None:
        daily_total = Pause.daily_activity_total(session, today)
    delta.update(day=day, daily_total=daily_total)
    if pauses_changed:
        delta.update(Pause.as_state(session))
    session.commit()
    state.update(delta)


def metrics_at(
    now,
    daily_target,
    session_target,
    rest_target,
    day,
    daily_total,
    session_start,
    rest_start,
):
    rest_value = now - rest_start
    return dict(
        daily_target=daily_target,
        session_target=session_target,
        rest_target=rest_target,
        daily_value=daily_total if is_on_day(now, day) else 0,
        session_value=now - session_start if rest_value < rest_target else 0,
        rest_value=rest_value,
    )
