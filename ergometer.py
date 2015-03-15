#!/usr/bin/env python

from __future__ import division, print_function
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from functools import total_ordering
from heapq import merge
from itertools import chain, groupby, ifilter, imap, izip, repeat, starmap
from os.path import basename, realpath
import math
import os
import sys

def F(*args, **kwds):
    if not args:
        raise TypeError('F() takes at least 1 argument (0 given)')
    caller = sys._getframe(1)
    names = {}
    names.update(caller.f_globals)
    names.update(caller.f_locals)
    names.update(kwds)
    return args[0].format(*args[1:], **names)

flatten = chain.from_iterable

def flatmap(f, it):
    return flatten(imap(f, it))

positions = defaultdict(int)

@contextmanager
def seek_open(path):
    with open(path) as f:
        f.seek(positions[path])
        yield f

def lines_from_file_(path):
    with seek_open(path) as lines:
        first = lines.next()
    positions[path] = len(first)
    yield first
    with seek_open(path) as lines:
        for line in lines:
            yield line
        positions[path] = lines.tell()

def lines_from_file(path):
    with open(path, 'rb') as f:
        for line in f:
            yield line

midnight_offset = timedelta(hours=4)
Key, Meta, Repeat, Move, Click, Scroll, Drag, Error, Offset, Status = xrange(10)
Start = object()

meta_downs = defaultdict(int)

def meta_cost(m, k):
    if m < 1:
        return 0
    d = k - meta_downs[m - 1]
    if d < 0:
        meta_downs[m - 1] += d
        return 0
    meta_downs[m - 1] = 0
    if m >= 2:
        meta_downs[m - 2] += d
    return d

def cost_of(a):
    meta = starmap(meta_cost, reversed(list(enumerate(a[Meta]))))
    return sum(chain(a[Key], meta, a[Click]))

def day_of(dt):
    return F('{dt:%Y-%m-%d %a}')

def time_of_day_of(dt):
    return F('{dt:%I:%M:%S %p}')

@total_ordering
class Event(object):
    def __init__(self, span, record):
        self.start = record[0][0] * span
        self.stop = self.start + span
        self.cost = cost_of(defaultdict(list, enumerate(record[1:])))
        self.start_dt = datetime.fromtimestamp(self.start)
        self.start_date = (self.start_dt - midnight_offset).date()
        self.day_number = self.start_date.toordinal()

    @property
    def day(self):
        return day_of(self.start_date)

    @property
    def time_of_day(self):
        return time_of_day_of(self.start_dt)

    def __lt__(self, rhs):
        return self.start < rhs.start

    def __eq__(self, rhs):
        return self.start == rhs.start

def LineParser(version):
    span = {1: 60, 2: 10, 3: 1}[version]
    def smoothed_events(line):
        return Event(span, [[int(s) if s else 0 for s in g.split(' ')]
            for g in line.split(',')])
    return smoothed_events

def events_from_file(path):
    version = int(basename(path).split('.')[1])
    return imap(LineParser(version), lines_from_file(path))

def print_day(events):
    events = list(events)
    day = events[0].day
    k = sum(e.cost for e in events)
    lk = math.log(k or 1, 2)
    print(F('{day}\t{k}\t{lk}'))


def intervals_in_timedelta(td, interval):
    return int(td.total_seconds() // interval.total_seconds())


def print_tsv_row(label, cells):
    print('\t'.join(map(str, (label,) + tuple(cells))))


def print_raw_data():
    start_day = date(2015, 3, 7)
    events = ifilter(
        lambda e: e.day_number >= start_day.toordinal(),
        merge(*map(events_from_file, os.listdir('.')))
    )
    rows = defaultdict(lambda: defaultdict(int))
    for e in events:
        rows[e.time_of_day][e.day] += e.cost
    today = (datetime.now() - midnight_offset).date()
    days = [
        start_day + timedelta(days=i)
        for i in xrange((today - start_day).days + 1)
    ]
    print_tsv_row('Time', days)
    step = timedelta(seconds=10)
    for i in xrange(intervals_in_timedelta(timedelta(days=1), step)):
        t = time_of_day_of(datetime(2000, 1, 1) + midnight_offset + step * i)
        cells = [rows[t][day_of(day)] for day in days]
        print_tsv_row(t, cells)


def print_cost_per_day():
    pairs = groupby(merge(*map(events_from_file, os.listdir('.'))), lambda e: e.day_number)
    for _, events in pairs:
        print_day(events)


def main():
    os.chdir(realpath(__file__ + '/../../log'))
    if '-k' in sys.argv:
        print_cost_per_day()
    elif '-r' in sys.argv:
        print_raw_data()


if __name__ == '__main__':
    main()
