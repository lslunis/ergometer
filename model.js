import {getOutboxInitialState, Outbox} from './outbox.js'
import {Duration, Time} from './time.js'
import {lowerBound, makeObject, mod, switchOnKey, upperBound} from './util.js'

function getInitialState() {
  const initialTarget = target => ({target, mtime: new Time(-Infinity)})
  return {
    outbox: getOutboxInitialState(),
    monitored: true,
    targets: {
      weekly: initialTarget(Duration.hours(40)),
      daily: initialTarget(Duration.hours(8)),
      session: initialTarget(Duration.hours(1)),
      rest: initialTarget(Duration.minutes(5)),
    },
    lastActives: {},
    timelines: {},
    sharedTimeline: [],
    firstWeek: Infinity,
    dailyValues: {},
  }
}

export const idleDelay = Duration.seconds(15)

function timelineLowerBound(timeline, start) {
  return lowerBound(timeline, start.milliseconds, ({end}) => end.milliseconds)
}

function markTimeline(timeline, start, end) {
  const lower = timelineLowerBound(timeline, start)
  const upper = upperBound(
    timeline,
    end.milliseconds,
    ({start}) => start.milliseconds,
  )
  if (lower < upper) {
    start = start.clampHigh(timeline[lower].start)
    end = end.clampLow(timeline[upper - 1].end)
  }
  timeline.splice(lower, upper - lower, {start, end})
}

function clearTimeline(timeline, start) {
  const lower = timelineLowerBound(timeline, start)
  const items = []
  if (lower < timeline.length) {
    const lowerStart = timeline[lower].start
    if (lowerStart.lessThan(start)) {
      items.push({start: lowerStart, end: start})
    }
  }
  timeline.splice(lower, timeline.length - lower, ...items)
}

export class Model {
  constructor(
    time,
    state,
    {verbose = false, onUpdate = () => {}, onPush} = {},
  ) {
    this.verbose = verbose
    this.onUpdate = onUpdate
    this.preloadQueue = []
    this.outbox = this.state = null
    this.loaded = this.load(state, onPush)
    this.update({time, started: true})
  }

  async load(state, onPush) {
    this.state = {...getInitialState(), ...((await state) || {})}
    this.outbox = new Outbox(this.state.outbox, onPush)
    this.preloadQueue.map(f => f())
    this.preloadQueue = null
  }

  addDailyValue(time, value) {
    const {state} = this
    const day = Math.floor(
      time.sinceEpoch.plus(time.zone).minus({hours: 4}).days,
    )
    state.firstWeek = Math.min(state.firstWeek, day - mod(day - 4, 7))
    state.dailyValues[day] = value.plus(state.dailyValues[day] || 0).clampLow(0)
  }

  markTimeline(peer, start, end) {
    if (!this.state.timelines[peer]) {
      this.state.timelines[peer] = []
    }
    markTimeline(this.state.timelines[peer], start, end)
    markTimeline(this.state.sharedTimeline, start, end)
  }

  clearTimeline(peer, start) {
    if (!this.state.timelines[peer]) {
      return
    }
    clearTimeline(this.state.timelines[peer], start)
    clearTimeline(this.state.sharedTimeline, start)
    Object.values(this.state.timelines).map(timeline =>
      timeline
        .slice(timelineLowerBound(timeline, start))
        .map(({start, end}) =>
          markTimeline(this.state.sharedTimeline, start, end),
        ),
    )
  }

  update(event, peer = 0) {
    const {state} = this
    if (!state) {
      this.preloadQueue.push(() => this.update(event, peer))
      return
    }
    if (this.verbose) {
      console.log({...event, peer})
    }
    if (!peer) {
      this.outbox.push(event)
    }
    const setMonitored = monitored => {
      if (!peer) {
        state.monitored = monitored
      }
    }
    switchOnKey(event, {
      started({started}) {
        setMonitored(started)
      },
      monitored({monitored}) {
        setMonitored(monitored)
      },
      target({time, name, target}) {
        const t = state.targets[name]
        if (t.mtime.lessThan(time)) {
          t.mtime = time
          t.target = target
        }
      },
      idleState({time, idleState}) {
        const adjustment =
          idleState == 'idle' ? idleDelay.negate() : Duration.make(0)
        const adjustedTime = time.plus(adjustment)
        const {end} = state.timelines[peer]
        this.clearTimeline(peer, adjustedTime)
        if (state.lastActives[peer] && time.minus(end).lessThan(idleDelay)) {
          if (end.lessThan(adjustedTime)) {
            this.markTimeline(peer, end, adjustedTime)
          }
          this.addDailyValue(end, adjustedTime.minus(end).clampLow(adjustment))
        }
        const isActive = idleState == 'active'
        if (isActive) {
          this.markTimeline(peer, time, time)
        }
        state.lastActives[peer] = isActive
      },
    })
    this.onUpdate()
  }

  getMetrics(time) {
    const values = {
      weekly: Duration.make(0),
      daily: Duration.make(0),
      session: Duration.make(0),
      rest: Duration.make(0),
    }
    return makeObject(
      Object.entries(values).map(([name, value]) => {
        const target = this.state.targets[name].target
        return [
          name,
          {
            name,
            value,
            target,
            advised: true,
            attained: !value.lessThan(target),
          },
        ]
      }),
    )
  }
}
