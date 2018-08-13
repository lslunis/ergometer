import {getOutboxInitialState, Outbox} from './outbox.js'
import {Duration, Time} from './time.js'
import {
  getLast,
  lowerBound,
  makeObject,
  mod,
  range,
  switchOnKey,
  upperBound,
} from './util.js'

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

function dayOfTime(time) {
  return Math.floor(time.sinceEpoch.plus(time.zone).minus({hours: 4}).days)
}

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

  getDailyValue(day) {
    return this.state.dailyValues[day] || Duration.make(0)
  }

  addDailyValue(time, value) {
    const {state} = this
    const day = dayOfTime(time)
    state.firstWeek = Math.min(state.firstWeek, day - mod(day - 4, 7))
    state.dailyValues[day] = value.plus(this.getDailyValue(day)).clampLow(0)
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
    const metrics = makeObject(
      Object.entries(this.state.targets).map(([name, {target}]) => {
        return [
          name,
          {
            name,
            target,
            advised: true,
            get attained() {
              return this.value.greaterEqual(this.target)
            },
          },
        ]
      }),
    )
    const {weekly, daily, session, rest} = metrics

    const day = dayOfTime(time)
    weekly.value = [...range(day, day - 7, -1)]
      .map(day => this.getDailyValue(day))
      .reduce((a, b) => a.plus(b))
    daily.value = this.getDailyValue(day)

    const {sharedTimeline} = this.state
    const firstSession = {end: -Infinity}

    session.value = Duration.make(0)
    for (let i = sharedTimeline.length - 1; i >= 0; i--) {
      const {start} = sharedTimeline[i]
      const {end: priorEnd} = i ? sharedTimeline[i - 1] : firstSession
      if (start.minus(priorEnd).greaterEqual(rest.target)) {
        session.value = time.minus(start).clampLow(0)
        break
      }
    }

    rest.value = time
      .minus(getLast(sharedTimeline, firstSession).end)
      .clampLow(0)

    const hypotheticalActiveEfficiency = session.target
      .minus(rest.value)
      .dividedBy(rest.target.plus(rest.value))
    const hypotheticalIdleEfficiency = session.value
      .minus(rest.value)
      .dividedBy(rest.target)
    rest.advised = hypotheticalIdleEfficiency >= hypotheticalActiveEfficiency

    return metrics
  }
}
