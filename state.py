import datetime
from itertools import chain, islice, repeat
import struct

from sqlalchemy import Column, Integer, String, create_engine, event, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


engine = create_engine("sqlite:///state.db")
Session = sessionmaker(bind=engine)


# Override pysqlite's broken transaction handling
# https://docs.sqlalchemy.org/en/13/dialects/sqlite.html#pysqlite-serializable


@event.listens_for(engine, "connect")
def do_connect(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None


@event.listens_for(engine, "begin")
def do_begin(connection):
    connection.execute("BEGIN")


Base = declarative_base()


class HostPosition(Base):
    __tablename__ = "host_positions"
    host = Column(String, primary_key=True)
    position = Column(Integer, nullable=False)

    def __str__(self):
        return f"{self.host}:{self.position}"


class Target(Base):
    __tablename__ = "targets"
    id = Column(Integer, primary_key=True)
    target = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)

    @staticmethod
    def get(session, id):
        if id >= len(Target.names):
            raise ValueError(f"unexpected target id: {id}")
        target = session.query(Target).get(id)
        if target is None:
            target = Target(id=id, time=0)
            session.add(target)
        return target

    @staticmethod
    def as_state(*targets):
        return {f"{t.name}_target": t.target for t in targets}

    @property
    def name(self):
        return Target.names[self.id]

    def update_if_newer(self, target, time):
        if self.time < time:
            self.target = target


class Total(Base):
    __tablename__ = "totals"
    start = Column(Integer, primary_key=True)
    total = Column(Integer, nullable=False)

    @staticmethod
    def get(session, time):
        start = lower_bound_of(time, period=300)
        return session.query(Total).get(start)


class Pause(Base):
    __tablename__ = "pauses"
    end = Column(Integer, primary_key=True)
    span = Column(Integer, nullable=False)

    @staticmethod
    def as_state(session):
        rest_target = Target.get(session, "rest").target
        rests = (
            session.query(Pause)
            .order_by(Pause.end.desc())
            .filter(Pause.span >= rest_target)
        )
        last_rest, prior_rest = islice(chain(rests.limit(2), repeat(None)), 2)
        return dict(
            session_start=prior_rest.end if prior_rest else 0,
            rest_start=last_rest.end - last_rest.span if last_rest else 0,
        )


@retry_on(PositionError)
async def state_updater(state, broker):
    host_positions = initialize_state(state, imprecise_clock(), Session())
    async for args in broker.subscribe(host_positions):
        update_state(state, imprecise_clock(), Session(), *args)


def initialize_state(state, now, session):
    delta = {
        **Target.as_state(*session.query(Target)),
        **Pause.as_state(session),
    }
    host_positions = {
        hp.host: hp.position for hp in session.query(HostPosition)
    }
    session.commit()
    return state, host_positions


def update_state(now, session, host, data, position):
    host_position = session.query(HostPosition).get(host)
    if position != host_position.position:
        raise PositionError(f"expected {host_position}, got {position}")
    host_position.position += len(data)
    for kind, value, time in struct.iter_unpack("<BxxxIQ", data):
        if kind > 4:
            raise ValueError(f"unknown event kind: {kind}")
        is_action = kind == 4
        if is_action:
            Total.get(time).total += value
            if now - time < 3600:
                pass
        else:
            target = Target.get(session, kind)
            target.update_if_newer(value, time)


def merge_state(state, delta):
    if state.get("day") == delta["day"]:
        delta["daily_total"] += state.get("daily_total", 0)
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


def day_of(dt):
    return lower_bound_of(
        dt.timestamp(),
        period=86400,
        offset=dt.utcoffset().total_seconds() + 4 * 3600,
    )


def is_on_day(time, day):
    return day <= time < day + 86400


def imprecise_clock():
    return precise_clock().replace(microsecond=0)


def precise_clock():
    return datetime.datetime.now().astimezone()


def lower_bound_of(value, *, period, offset=0):
    return (value - offset) // period * period + offset
