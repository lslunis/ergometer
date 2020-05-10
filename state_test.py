from .state import *


def test_pause_updater_split_empty():
    with connect("sqlite://") as Session:
        now = 1589137550
        session = Session()
        pause_updater = PauseUpdater(session)
        pause_updater.update(now, 1)
        pauses = session.query(Pause).order_by(Pause.end).all()
        assert pauses == [Pause(start=0, end=now), Pause(start=(now + 1), end=max_time)]


def test_pause_updater_recycle_nonempty_session():
    pass
