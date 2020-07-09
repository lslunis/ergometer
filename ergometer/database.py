import struct
from bisect import bisect_left, bisect_right
from enum import Enum
from functools import total_ordering
from itertools import chain, dropwhile, islice, repeat
from time import time_ns

from ergometer.time import (
    day_start_of,
    imprecise_clock,
    in_seconds,
    is_on_day,
    max_time,
)
from ergometer.util import (
    Interval,
    PositionError,
    async_log_exceptions,
    die_unless,
    log,
    pairwise,
    retry_on,
    takeuntil_inclusive,
)
from sqlalchemy import Boolean, Column, Integer, String, create_engine, event, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


class connect(sessionmaker):
    def __init__(self, db_address):
        super().__init__()
        self.__engine = create_engine(db_address)

        # Override pysqlite's broken transaction handling
        # https://docs.sqlalchemy.org/en/13/dialects/sqlite.html#pysqlite-serializable

        @event.listens_for(self.__engine, "connect")
        def do_connect(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None

        @event.listens_for(self.__engine, "begin")
        def do_begin(connection):
            connection.execute("BEGIN")

        Base.metadata.create_all(self.__engine)
        self.configure(bind=self.__engine)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.__engine.dispose()


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
    def activity_total(session, start, end):
        edges = get_edges_including_bounds(session, start, end)
        activities = get_overlapping_intervals(edges, start, end)
        return sum(
            min(activity.end.time, end) - max(activity.start.time, start)
            for activity in activities
        )

    @staticmethod
    def session_start(session):
        rest_target = EventType.rest_target.get(session).value
        edges = session.query(ActivityEdge).order_by(ActivityEdge.time.desc())
        pauses = (Interval(start.time, end.time) for end, start in pairwise(edges))
        rests = (p for p in pauses if (p.end - p.start) >= rest_target)
        try:
            last_rest, prior_rest = islice(rests, 2)
            return prior_rest.end
        except ValueError:
            return 0

    @staticmethod
    def rest_start(session):
        return (
            session.query(ActivityEdge)
            .order_by(ActivityEdge.time.desc())
            .slice(1, 2)
            .one()
            .time
        )


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


def get_overlapping_intervals(edges, start, end, as_pauses=False):
    edges = dropwhile(lambda edge: edge.rising == as_pauses, edges)
    return (Interval(start_edge, end_edge) for start_edge, end_edge in pairwise(edges))


@event.listens_for(ActivityEdge.__table__, "after_create")
def do_after_create(target, connection, **kwds):
    session = sessionmaker()(bind=connection)
    session.add(ActivityEdge(time=0, rising=False))
    session.add(ActivityEdge(time=max_time, rising=True))
    session.commit()


min_pause = 15


def clip_span(span):
    return 0 if span < min_pause else span


class ActivityUpdater:
    def __init__(self, session):
        self.session = session
        self.boxed_edges = []

    def update(self, start, value):
        end = start + value
        start_edge = ActivityEdge(time=start, rising=True)
        end_edge = ActivityEdge(time=end, rising=False)
        activity = Interval(start_edge, end_edge)

        # lower bound <= start < end <= upper bound
        start_index = bisect_right(
            self.boxed_edges, ActivityEdgeOrderedByTime(start_edge)
        )
        end_index = bisect_left(self.boxed_edges, ActivityEdgeOrderedByTime(end_edge))
        if start_index == 0 or end_index == len(self.boxed_edges):
            self.boxed_edges = [
                ActivityEdgeOrderedByTime(edge)
                for edge in get_edges_including_bounds(self.session, start, end)
            ]
            start_index = 1
            end_index = len(self.boxed_edges) - 1

        boxed_bounds = dict(
            start=self.boxed_edges[start_index - 1], end=self.boxed_edges[end_index],
        )
        edges = [
            self.boxed_edges[i].edge for i in range(start_index - 1, end_index + 1)
        ]
        pauses = get_overlapping_intervals(edges, start, end, as_pauses=True)

        self.boxed_edges = []
        bound_deleted = {}
        total = 0

        for pause in pauses:
            total += pause.end.time - pause.start.time
            for x in ("start", "end"):
                activity_edge = getattr(activity, x)
                pause_edge = getattr(pause, x)
                sign = 1 if activity_edge.rising else -1
                d = sign * (activity_edge.time - pause_edge.time)
                if d >= min_pause:
                    total -= d
                    self.boxed_edges.append(ActivityEdgeOrderedByTime(activity_edge))
                    self.session.add(activity_edge)
                else:
                    if d > 0:
                        bound_deleted[x] = True
                    self.session.delete(pause_edge)

        self.session.flush()

        for x in ("start", "end"):
            if not bound_deleted.get(x):
                self.boxed_edges.append(boxed_bounds[x])

        self.boxed_edges.sort()
        return total


@total_ordering
class ActivityEdgeOrderedByTime:
    def __init__(self, edge):
        self.edge = edge

    def __eq__(self, other):
        return (
            isinstance(other, ActivityEdgeOrderedByTime)
            and self.edge.time == other.edge.time
        )

    def __lt__(self, other):
        if not isinstance(other, ActivityEdgeOrderedByTime):
            return NotImplemented
        return self.edge.time < other.edge.time


class EventType(Enum):
    action = 0
    daily_target = (1, in_seconds(hours=8))
    session_target = (2, in_seconds(hours=1))
    rest_target = (3, in_seconds(minutes=5))

    def __new__(cls, value, default=None):
        self = object.__new__(cls)
        self._value_ = value
        self.default = default
        return self

    @property
    def is_setting(self):
        return self.default is not None

    def get(self, session):
        die_unless(self.is_setting, f"unexpected: {self}")
        id = self.value
        setting = session.query(Setting).get(id)
        exists = setting is not None
        if not exists:
            setting = Setting(id=id, value=self.default, time=0)
            session.add(setting)
        return setting


setting_types = [t for t in EventType.__members__.values() if t.is_setting]

data_format = "<BxxxIQ"


@async_log_exceptions
@retry_on(PositionError)
async def database_updater(Session, update_cache, subscribe):
    log.debug("Starting database_updater")
    cache, host_positions = init(update_cache, imprecise_clock(), Session())
    async for args in subscribe(host_positions):
        cache = update_database(
            cache, update_cache, imprecise_clock(), Session(), *args
        )


def init(update_cache, now, session):
    today_start = day_start_of(now)
    today_end = today_start + in_seconds(days=1)
    delta = {
        "day_start": today_start,
        "daily_total": ActivityEdge.activity_total(session, today_start, today_end),
        "session_start": ActivityEdge.session_start(session),
        "rest_start": ActivityEdge.rest_start(session),
    }
    for type in setting_types:
        setting = type.get(session)
        delta[setting.name] = setting.value
    host_positions = {hp.host: hp.position for hp in session.query(HostPosition)}
    session.commit()
    return update_cache(delta), host_positions


def update_database(cache, update_cache, now, session, host, position, data):
    start = time_ns()
    HostPosition.update(session, host, data, position)

    today_start = day_start_of(now)
    day_start = cache["day_start"]
    daily_total = cache["daily_total"]
    if day_start != today_start:
        day_start = today_start
        daily_total = None
    activity_updater = ActivityUpdater(session)
    min_activity_start = max_time
    max_activity_end = 0

    for event_type_id, value, time in struct.iter_unpack(data_format, data):
        event_type = EventType(event_type_id)
        if event_type == EventType.action:
            if time < min_activity_start:
                min_activity_start = time
            if time + value > max_activity_end:
                max_activity_end = time + value
            activity_increase = activity_updater.update(time, value)
            if daily_total is not None and is_on_day(time, day_start):
                # this could attribute the activity_increase to the wrong day_start if
                # activity occurs at day_start boundary, but it can only be wrong
                # by less than min_idle seconds
                daily_total += activity_increase
        elif event_type.is_setting:
            event_type.get(session).update_if_newer(value, time)
        else:
            log.error(f"Unhandled: {event_type}")

    delta = {}
    rest_target_changed = False
    for setting in session.dirty:
        if isinstance(setting, Setting):
            delta[setting.name] = setting.value
            if setting.name == "rest_target":
                rest_target_changed = True

    if daily_total is None:
        today_end = today_start + in_seconds(days=1)
        daily_total = ActivityEdge.activity_total(session, today_start, today_end)
    delta.update(day_start=day_start, daily_total=daily_total)
    session_start = cache["session_start"]
    rest_start = cache["rest_start"]
    rest_target = delta.get("rest_target") or cache["rest_target"]
    if (
        rest_target_changed
        or Interval(min_activity_start, max_activity_end).overlaps(
            session_start - rest_target, session_start
        )
        or max_activity_end >= rest_start + rest_target
    ):
        delta["session_start"] = ActivityEdge.session_start(session)
    if max_activity_end > rest_start:
        delta["rest_start"] = max_activity_end
    session.commit()
    cache = update_cache(delta)
    elapsed = time_ns() - start
    log.debug(f"database updated with {len(data)}B of events in {elapsed/1e9:.3f}s")
    return cache
