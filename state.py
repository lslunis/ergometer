import struct
import time as timelib

from sqlalchemy import Column, Integer, String, create_engine, event, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


engine = create_engine("sqlite:///myfile.db")
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


class Target(Base):
    __tablename__ = "targets"
    name = Column(String, primary_key=True)
    target = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)

    @staticmethod
    def is_name(name):
        return

    def update_if_newer(target, time):
        if self.time < time:
            self.target = target


class Total(Base):
    __tablename__ = "totals"
    start = Column(Integer, primary_key=True)
    total = Column(Integer, nullable=False)

    @staticmethod
    def get(session, time):
        span = 300
        start = time // span * span
        return session.query(Total).get(start)


class Gap(Base):
    __tablename__ = "gaps"
    start = Column(Integer, primary_key=True)
    span = Column(Integer, nullable=False)


@retry_on(PositionError)
async def update_state(broker):
    async for host, data, position in broker.subscribe(
        {hp.host: hp.position for hp in Session().query(HostPosition).all()}
    ):
        session = Session()
        host_position = session.query(HostPosition).get(host)
        if position != host_position.position:
            raise PositionError(
                f"expected offset {host}:{expected_offset}, got {offset}",
            )
        host_position.position += len(data)
        now = timelib.time()
        for name, value, time in struct.iter_unpack("<xxxiq", data):
            if Target.is_name(name):
                target = session.query(Target).get(name)
                target.update_if_newer(value, time)
            else:
                Total.get(time) += value
                if now - time < 3600:
                    pass

def get_rest_start(session):
    return session.query(func.max(Gap.start)).scalar()
