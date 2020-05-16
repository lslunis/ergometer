from datetime import datetime
import struct

from .state import *

now = datetime(year=2020, month=5, day=16)
sample_host = "abcdefghi"


def pack_data(kind, value, dt):
    return struct.pack(data_format, kind.value, value, int(dt.timestamp()))

sample_data = pack_data(Kind.action, 1, now)

def get_sample_state():
    return {"day": day_start_of(now), "daily_total": 0}

def test_host_missing_position_nonzero():
    with connect("sqlite://") as Session:
        session = Session()
        try:
            update_state({}, now, session, sample_host, sample_data, 2 * 16)
            assert False
        except PositionError:
            pass


def test_host_missing_position_zero():
    with connect("sqlite://") as Session:
        session = Session()
        update_state(get_sample_state(), now, session, sample_host, sample_data, 0)
        assert session.query(HostPosition).get(sample_host).position == 16

def test_host_present_position_matches():
    with connect("sqlite://") as Session:
        session = Session()
        session.add(HostPosition(host=sample_host, position=5 * 16))
        update_state(get_sample_state(), now, session, sample_host, sample_data, 5 * 16)
        assert session.query(HostPosition).get(sample_host).position == 6 * 16

def test_host_present_event_repeated():
    with connect("sqlite://") as Session:
        session = Session()
        session.add(HostPosition(host=sample_host, position=5 * 16))
        try:
            update_state({}, now, session, sample_host, sample_data, 3 * 16)
            assert False
        except PositionError:
            pass

def test_host_present_event_skipped():
    with connect("sqlite://") as Session:
        session = Session()
        session.add(HostPosition(host=sample_host, position=2 * 16))
        try:
            update_state({}, now, session, sample_host, sample_data, 3 * 16)
            assert False
        except PositionError:
            pass