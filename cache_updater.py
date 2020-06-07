import struct
from bisect import bisect_left, bisect_right
from collections import namedtuple
from contextlib import contextmanager
from datetime import timedelta
from enum import Enum
from itertools import chain, dropwhile, islice, repeat

from sqlalchemy import Boolean, Column, Integer, String, create_engine, event, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .time import day_start_of, imprecise_clock, is_on_day, max_time
from .util import PositionError, die_unless, pairwise, retry_on, takeuntil_inclusive

Session = sessionmaker()


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
        Session.configure(bind=engine)
        yield Session

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
        return setting

    @property
    def name(self):
        return EventType(self.id).name

    def update_if_newer(self, value, time):
        if self.time < time:
            self.value = value


class ActivityEdge(Base):
    __tablename__ = "activity_edges"
    time = Column(Integer, primary_key=True)
    rising = Column(Boolean, nullable=False)

    def __eq__(self, other):
        return (
            isinstance(other, ActivityEdge)
            and self.time == other.time
            and self.rising == other.rising
        )

    def __repr__(self):
        arrow = "⬈" if self.rising else "⬊"
        return f"<ActivityEdge {self.time} {arrow}>"

    @staticmethod
    def session_interval_cache(session):
        rest_target = Setting.get(session, EventType.rest_target).value
        edges = session.query(ActivityEdge).order_by(ActivityEdge.time.desc())
        pauses = (Interval(start.time, end.time) for end, start in pairwise(edges))
        rests = (p for p in pauses if (p.end - p.start) >= rest_target)
        last_rest, prior_rest = islice(
            chain(islice(rests, 2), repeat(Interval(0, 0))), 2
        )
        return dict(session_start=prior_rest.end, session_end=last_rest.start)

    @staticmethod
    def activity_total(session, start, end):
        edges = ActivityEdge.get_edges_including_bounds(session, start, end)
        edges = dropwhile(lambda edge: not edge.rising, edges)

        activities = (
            Interval(max(activity_start.time, start), min(activity_end.time, end))
            for activity_start, activity_end in pairwise(edges)
        )

        return sum(activity.end - activity.start for activity in activities)

    @staticmethod
    def get_edges_including_bounds(session, start, end):
        lower_bound = session.query(func.max(ActivityEdge.time)).filter(
            ActivityEdge.time < start
        )
        edges = (
            session.query(ActivityEdge)
            .filter(ActivityEdge.time >= lower_bound)
            .order_by(ActivityEdge.time)
        )

        return takeuntil_inclusive(lambda edge: edge.time > end, edges)


@event.listens_for(ActivityEdge.__table__, "after_create")
def do_after_create(target, connection, **kwds):
    session = Session(bind=connection)
    session.add(ActivityEdge(time=0, rising=False))
    session.add(ActivityEdge(time=max_time, rising=True))
    session.commit()


min_pause = 15


def clip_span(span):
    return 0 if span < min_pause else span


class ActivityUpdater:
    def __init__(self, session):
        self.session = session
        self.edges = []


    def update(self, start, end):
        start_index = bisect_left(self.edges, start)
        end_index = bisect_right(self.edges, end)
        if start_index == 0 or end_index == len(self.edges):
            self.edges = [*ActivityEdge.get_edges_including_bounds(self.session, start, end)]
            
        self.session.execute(ActivityEdge.__table__.delete().where(start <= ActivityEdge.time <= end))
        self.update_bound(self.lower_bound, ActivityEdge(time=start, rising=True))
        end_edge = ActivityEdge(time=end, rising=False)
        if self.update_bound(self.upper_bound, end_edge):
            self.lower_bound = end_edge


    def update_bound(self, bound, edge):
        if bound.rising != edge.rising:
            if abs(bound.time - edge.time) < min_pause:
                self.session.delete(bound)
            else:
                self.session.add(edge)
                return True


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


Interval = namedtuple("Interval", ["start", "end"])

data_format = "<BxxxIQ"


@retry_on(PositionError)
async def cache_updater(cache, broker):
    Session = connect("sqlite:///cache.db")
    host_positions = initialize_cache(cache, imprecise_clock(), Session())
    async for args in broker.subscribe(host_positions):
        update_cache(cache, imprecise_clock(), Session(), *args)


def initialize_cache(cache, now, session):
    today_start = day_start_of(now)
    today_end = today_start + timedelta(days=1).total_seconds()
    delta = {
        **{s.name: s.value for s in session.query(Setting)},
        "day_start": today_start,
        "daily_total": ActivityEdge.activity_total(session, today_start, today_end),
        **ActivityEdge.session_interval_cache(session),
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
    pause_updater = ActivityUpdater(session)

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
        today_end = today_start + timedelta(days=1).total_seconds()
        daily_total = ActivityEdge.activity_total(session, today_start, today_end)
    delta.update(day_start=day_start, daily_total=daily_total)
    if pause_updater.updated:
        delta.update(ActivityEdge.session_interval_cache(session))
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
