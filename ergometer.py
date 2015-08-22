#!/usr/bin/env python

from __future__ import division, print_function
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, time as dtime, timedelta, tzinfo
from functools import partial, total_ordering
from glob import iglob
from heapq import merge
from itertools import chain, groupby, ifilter, imap, izip, repeat, starmap
import json
import math
import os
from os.path import basename, realpath
import re
import sys
from time import time, sleep
import traceback

class Local(tzinfo):
    def utcoffset(self, dt):
        now = time()
        dt = datetime.utcfromtimestamp(now)
        local_dt = datetime.fromtimestamp(now)
        return dt - local_dt
    def dst(self, dt):
        return timedelta(0)

tz = Local()

def print_exc(*args):
    print(datetime.now(tz).isoformat(' '),
        ''.join(traceback.format_exception(*args)), file=sys.stderr)

sys.excepthook = print_exc


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

def lines_from_file(path):
    with seek_open(path) as lines:
        first = lines.next()
    positions[path] += len(first)
    yield first
    with seek_open(path) as lines:
        for line in lines:
            yield line
        positions[path] = lines.tell()

midnight_offset = timedelta(hours=4)
Key, Meta, Repeat, Move, Click, Scroll, Drag, Error = xrange(8)

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
    return F('{dt:%Y-%m-%d}')

def time_of_day_of(dt):
    return F('{dt:%I:%M:%S %p}')

def minute_of_day_of(dt, res):
    dt = dt - timedelta(minutes=dt.minute % res)
    return F('{dt:%I:%M %p}')

@total_ordering
class Event(object):
    def __init__(self, span, record):
        self.start = record[0][0] * span
        self.stop = self.start + span
        self.cost = cost_of(defaultdict(list, enumerate(record[1:])))
        self.dt = datetime.fromtimestamp(self.start)
        self.day_dt = self.dt - midnight_offset
        self.day_number = self.day_dt.toordinal()

    @property
    def day(self):
        return day_of(self.day_dt)

    @property
    def time_of_day(self):
        return time_of_day_of(self.dt)

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


def events_from_file(after, path):
    version = int(basename(path).split('.')[1])
    events = imap(LineParser(version), lines_from_file(path))
    events = ifilter(lambda e: e.cost > 0, events)
    if after:
        events = ifilter(
            lambda e: after <= datetime.utcfromtimestamp(e.stop), events)
    return events

def has_events(path):
    try:
        return positions[path] < os.path.getsize(path)
    except OSError:
        return False

def new_events(after=None, warn_count=[0]):
    paths = set(iglob('log/*.[1-3].log'))
    warn_count[0] = len(set(iglob('log/*')) - paths)
    new_paths = filter(has_events, paths)
    return merge(*map(partial(events_from_file, after), new_paths))

def intervals_in_timedelta(td, interval):
    return int(td.total_seconds() // interval.total_seconds())

def print_tsv_row(*cells):
    print('\t'.join(map(str, cells)))

def today():
    return (datetime.now() - midnight_offset).date()

def this_monday_of(daynum):
    return int((daynum - 1) // 7 * 7 + 1)

def print_calendar():
    res = 5
    step = timedelta(minutes=res)

    start_number = this_monday_of(today().toordinal())
    stop_number = start_number + 7
    start_day = date.fromordinal(start_number)
    days = [start_day + timedelta(days=i)
        for i in xrange(stop_number - start_number + 1)]

    rows = defaultdict(lambda: defaultdict(int))
    events = ifilter(
        lambda e: start_number <= e.day_number <= stop_number,
        new_events())
    for e in events:
        rows[minute_of_day_of(e.dt, res)][e.day] += e.cost

    print_tsv_row('', *(chr(ord('A') + i) for i in xrange(len(days))))
    for i in xrange(intervals_in_timedelta(timedelta(hours=6), step)):
        t = minute_of_day_of(datetime(2000, 1, 1, 7) + step * i, res)
        cells = [rows[t][day_of(day)] for day in days]
        print_tsv_row(t, *cells)

class IntervalGrouper(object):
    def __init__(self, gap):
        self.gap = gap
        self.start = None
        self.stop = 0

    def __call__(self, e):
        if e.start - self.stop >= self.gap:
            self.start = e.start
        self.stop = e.stop
        return self.start

def identity(x):
    return x

def day_from_daynum(daynum):
    return day_of(date.fromordinal(daynum))

def total_cost_of(events):
    return sum(e.cost for e in events)

def interval_length(events):
    events = list(events)
    return events[-1].stop - events[0].start

def total_span_of(events, gap=15):
    grouped_events = groupby(events, IntervalGrouper(gap))
    return sum(interval_length(events) for _, events in grouped_events)

def formatted_total_span_of(*args, **kwds):
    return format_time(total_span_of(*args, **kwds))

def summarize(events, *args):
    return [total_cost_of(events), formatted_total_span_of(events)]

def span_ratios_of(events, *args):
    spans = [total_span_of(events, gap) for gap in xrange(5, 35 + 1, 5)]
    return [format(spans[i + 1] / (span or 1), '.3')
        for i, span in enumerate(spans[:-1])]

def value_sorter(value_of, format_value):
    def get_columns(events, *args):
        pairs = groupby(events, lambda e: e.day_number)
        values = sorted((value_of(es) for i, es in pairs), reverse=True)
        values += [0] * (7 - len(values))
        return map(format_value, values)
    return get_columns

def print_rows(get_columns, daynum_for_row=identity):
    daynum_to_value = defaultdict(list)
    pairs = groupby(new_events(), lambda e: daynum_for_row(e.day_number))
    first_daynum = None
    for daynum, events in pairs:
        events = list(events)
        if first_daynum is None:
            first_daynum = daynum
        daynum_to_value[daynum] = events

    daynums = xrange(first_daynum, today().toordinal() + 1)
    for daynum, _ in groupby(imap(daynum_for_row, daynums)):
        day = day_from_daynum(daynum)
        columns = get_columns(daynum_to_value[daynum], daynum, daynum_to_value)
        print_tsv_row(day, *columns)

def print_weeks(value_of, format_value):
    print_rows(value_sorter(value_of, format_value), this_monday_of)

min_opt = partial(min, key=lambda x: float('inf') if x is None else x)

class Status(namedtuple('Status', 'a t')):

    @staticmethod
    def min(xs):
        return Status(*map(min_opt, zip(*xs)))

    def better_than(x, y):
        xa = x.a or 0
        xt = x.t or 0
        return xa > 0 and xt > 0 and (xa > (y.a or 0) or xt > (y.t or 0))

def black(s):
    return [s, []]

spacer = black('  ')

def red(s):
    return [s, [1, 0, 0, 1]]

def red_if_negative(x):
    s = str(int(round(x)))
    return red(s) if x < 0 else black(s)

def format_time(t):
    s = format(datetime.utcfromtimestamp(t), '%H:%M:%S')
    return s[:-4].lstrip('0:') + s[-4:]

def gray(s):
    return [s, [.7, .7, .7, 1]]

def gray_time(t):
    return gray(format_time(t))

def red_time_if_negative(t):
    s = format_time(t)
    return red(s) if t < 0 else black(s)

def format_status(s):
    b = []
    if s.a:
        b.append(red_if_negative(s.a))
    if s.t:
        b.append(red_time_if_negative(s.t))
    return b

def load_json(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}

def copy_dict_to_object(d, o):
    for k, v in d.items():
        k = re.sub(r'([A-Z])', r'_\1', k).lower()
        setattr(o, k, v)

def last_expirable_before(now):
    dt = datetime.utcfromtimestamp(now)
    expire_hour = int(
        (midnight_offset + tz.utcoffset(dt)).total_seconds() // 3600)
    if dt.hour < expire_hour:
        dt -= timedelta(days=1)
    return datetime.combine(dt.date(), dtime(hour=expire_hour))

class Meter(object):

    action_cost = 0
    first_acted = None

    def __init__(self, app):
        self.app = app
        self.time_costs = defaultdict(int)

    def configure(self, c):
        self.action_limit = None
        self.time_limits = {}
        self.rest_time = None
        copy_dict_to_object(c, self)

    def add(self, x, now):
        self.action_cost += x
        if self.first_acted is None:
            self.first_acted = now

    def rest(self, last_acted, now):
        remaining_rest = last_acted + (self.rest_time or 0) - now
        if self.rest_time and remaining_rest <= 0:
            self.app.reset(self)
        return remaining_rest

    def current_time_cost(self, last_acted):
        if self.first_acted is not None:
            return last_acted - self.first_acted
        else:
            return 0

    def status(self, now):
        stat = lambda cost, limit: limit - cost if limit else None
        a = stat(self.action_cost, self.action_limit)
        ts = []
        for name, limit in self.time_limits.items():
            m = self.app.named_meters.get(name)
            k = m.current_time_cost(now) if m else 0
            ts.append(stat(self.time_costs[name] + k, limit))
        return Status(a, min(ts) if ts else None)

    def expire(self):
        if not self.rest_time:
            self.app.reset(self)

class App(object):

    rest_delay = 15
    activation_delay = 15
    activation_gap = 5
    last_acted = 0
    last_preacted = 0
    activation_cost = 0
    activation_limit = 0

    last_configured = 0
    prior_exhausted = False
    prior_min_status = Status(None, None)

    def __init__(self, now, host):
        self.warn_path = F('{host}.error.log')
        sys.stderr = open(self.warn_path, 'a', buffering=1)
        self.fades = {}
        self.last_faded = defaultdict(int)
        self._meters = []
        self.named_meters = {}
        self.host = host
        self.positions_path = F('{host}.positions.json')
        positions.update(load_json(self.positions_path))
        self.last_expired = last_expirable_before(now)

    def get_meters(self):
        return self._meters

    def set_meters(self, confs):
        self._meters = []
        for c in confs:
            m = self.named_meters.get(c['name'], Meter(self))
            m.configure(c)
            self._meters.append(m)
        self.named_meters = dict((m.name, m) for m in self._meters)

    meters = property(get_meters, set_meters)

    def configure(self, now):
        p = 'conf.json'
        last_modified = os.stat(p).st_mtime
        if last_modified <= self.last_configured:
            return
        copy_dict_to_object(load_json(p), self)
        self.last_configured = now

    def update_preact(self, now):
        if now - self.last_preacted > self.activation_delay:
            self.activation_limit = self.activation_cost + self.activation_gap

    def act(self, e):
        self.rest(e.start)
        self.update_preact(e.start)
        self.last_preacted = e.stop
        self.activation_cost += e.cost
        if self.activation_cost <= self.activation_limit:
            return
        self.last_acted = e.stop
        for m in self.meters:
            m.add(self.activation_cost, e.start)
        self.activation_cost = self.activation_limit = 0

    def reset(self, source):
        n = source.name
        t = source.current_time_cost(self.last_acted)
        for m in self.meters:
            m.time_costs[n] += t
        source.action_cost = 0
        source.first_acted = None
        source.time_costs.clear()

    def expire(self, now):
        if self.last_expired < last_expirable_before(now):
            self.last_expired = datetime.utcfromtimestamp(now)
            for m in self.meters:
                m.expire()
            if all(not m.action_cost for m in self.meters):
                with open(self.positions_path, 'w') as f:
                    json.dump(positions, f, indent=4, sort_keys=True)

    def dispatch(self, cmd, *args):
        args = [[cmd]] + list(args)
        print('\v'.join('\t'.join(str(x) for x in xs) for xs in args))
        sys.stdout.flush()

    def fade(self, now, kind):
        if kind not in self.fades:
            return
        self.dispatch('fade', self.fades[kind])
        self.last_faded[kind] = now

    def status(self, colored_strings):
        strings, colors = zip(*colored_strings)
        self.dispatch('status', strings, *colors)

    def rest(self, now):
        return [m.rest(self.last_acted, now) for m in self.meters]

    def update(self, now):
        self.expire(now)
        remaining_rests = self.rest(now)
        statuses = [m.status(now) for m in self.meters]
        restless_status = Status.min(
            s for m, s in zip(self.meters, statuses) if not m.rest_time)
        min_status = Status.min(statuses)
        return remaining_rests, restless_status, min_status

    def tick(self, now, warn_count=0):
        try:
            warn_count += os.path.getsize(self.warn_path)
        except OSError:
            pass

        remaining_rests, restless_status, min_status = self.update(now)

        needed_rest = None
        future = deepcopy(self)
        for remaining_rest in sorted(r for r in remaining_rests if r > 0):
            future_min_status = future.update(now + remaining_rest)[2]
            if future_min_status.better_than(min_status):
                needed_rest = remaining_rest
                break

        remaining = min_opt(min_status.a, min_status.t)
        exhausted = remaining is not None and remaining <= 0
        cheated = exhausted and self.last_faded['stop'] < self.last_acted
        if self.prior_exhausted < exhausted or cheated:
            self.fade(now, 'stop')
        self.prior_exhausted = exhausted

        if min_status.better_than(self.prior_min_status):
            self.fade(now, 'go')
        self.prior_min_status = min_status

        min_status = Status(*(None if x == y else x
            for x, y in zip(min_status, restless_status)))

        colored_strings = []
        self.update_preact(now)
        warn = [red(warn_count)] if warn_count else []
        preact = self.activation_limit - self.activation_cost
        preact = [gray(preact)] if preact else []
        resting = now - self.last_acted > self.rest_delay
        showing_rest = needed_rest and (exhausted or resting)
        rest = [gray_time(needed_rest)] if showing_rest else []
        stop = [red('STOP')] if exhausted else format_status(min_status)
        status_strings = warn + preact + rest + stop + format_status(
            restless_status)
        for i, s in enumerate(status_strings):
            if i > 0:
                colored_strings.append(spacer)
            colored_strings.append(s)

        self.status(colored_strings)

def serve(host, *args):
    now = time()
    a = App(now, host)
    last_preinit_expired = a.last_expired
    while True:
        try:
            a.configure(now)
            warn_count = [0]
            for e in new_events(last_preinit_expired, warn_count):
                a.act(e)
            a.tick(now, warn_count[0])
        except Exception:
            print_exc(*sys.exc_info())
        sleep(1)
        now = time()

def main():
    os.chdir(realpath(__file__ + '/../..'))
    commands = dict(
        c=[print_calendar],
        d=[print_rows, summarize],
        g=[print_rows, span_ratios_of],
        k=[print_weeks, total_cost_of, identity],
        t=[print_weeks, total_span_of, format_time],
        w=[print_rows, summarize, this_monday_of],
        _=[serve])
    for c, f in commands.items():
        if c == sys.argv[1]:
            try:
                f[0](*(f[1:] + sys.argv[2:]))
            except KeyboardInterrupt:
                pass

if __name__ == '__main__':
    main()
