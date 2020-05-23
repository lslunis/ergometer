from datetime import datetime, timedelta


def day_start_of(dt):
    start_hour = 4
    if dt.hour < start_hour:
        dt -= timedelta(days=1)
    return int(
        dt.replace(
            hour=start_hour, minute=0, second=0, microsecond=0, fold=0
        ).timestamp()
    )


def is_on_day(time, day_start):
    return day_start <= time < day_start + timedelta(days=1).total_seconds()


def imprecise_clock():
    return precise_clock().replace(microsecond=0)


def precise_clock():
    return datetime.now().astimezone()


# SQLite uses variable length integers, so limit the size that timestamps will take up
max_time = 2 ** 48 - 1
