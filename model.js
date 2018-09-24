import {getSynchronizerInitialState} from './synchronizer.js'
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
    ...getSynchronizerInitialState(),
  }
}

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
  let cleared = Duration.sum(
    timeline.slice(lower).map(({start, end}) => end.minus(start)),
  )
  const newSpans = []
  if (lower < timeline.length) {
    const lowerStart = timeline[lower].start
    if (lowerStart.lessEqual(start)) {
      newSpans.push({start: lowerStart, end: start})
      cleared = cleared.minus(start.minus(lowerStart))
    }
  }
  timeline.splice(lower, timeline.length - lower, ...newSpans)
  return cleared
}

export function restAdvised({session, rest}) {
  const restBenefit = session.value.dividedBy(session.target) * 0.75
  const restCost = rest.target.minus(rest.value).dividedBy(rest.target) - 0.25
  return !rest.attained && !!rest.ratio && restBenefit >= restCost
}

export class Metric {
  constructor({name, value, target} = {}) {
    this.name = name
    this.value = value
    this.target = target
    this.advised = true
  }

  get attained() {
    return this.value.greaterEqual(this.target)
  }

  get ratio() {
    return this.value.dividedBy(this.target)
  }
}

export class Model {
  constructor(time, state, options) {
    Object.assign(this, options)
    this.preloadQueue = []
    this.synchronizer = this.state = null
    this.loaded = this.load(state)
    this.update({time, started: true})
  }

  async load(state) {
    this.state = {...getInitialState(), ...((await state) || {})}
    this.synchronizer = this.makeSynchronizer({
      state: this.state,
      onStateChanged: () => {
        this.onStateChanged()
      },
      onEvent: event => {
        this.update(event)
      },
    })
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

  markTimeline(host, start, end) {
    if (!this.state.timelines[host]) {
      this.state.timelines[host] = []
    }
    markTimeline(this.state.timelines[host], start, end)
    markTimeline(this.state.sharedTimeline, start, end)
  }

  clearTimeline(host, start) {
    if (!this.state.timelines[host]) {
      return Duration.make(0)
    }
    const cleared = clearTimeline(this.state.timelines[host], start)
    clearTimeline(this.state.sharedTimeline, start)
    Object.values(this.state.timelines).map(timeline =>
      timeline
        .slice(timelineLowerBound(timeline, start))
        .map(({start, end}) =>
          markTimeline(this.state.sharedTimeline, start, end),
        ),
    )
    return cleared
  }

  periodsSinceActive(time, host = 0) {
    return this.state.lastActives[host]
      ? time
          .minus(getLast(this.state.timelines[host]).end)
          .dividedBy(this.idleDelay)
      : Infinity
  }

  update(event) {
    const {host = 0} = event
    const {state} = this
    if (!state) {
      this.preloadQueue.push(() => this.update(event))
      return
    }
    const getId = () => event.id || this.synchronizer.nextId
    const log = this.verbose
      ? message =>
          console.log(
            `${event.time} <${host || 'local'} ${getId()}> ${message}`,
          )
      : () => {}
    if (!host) {
      this.synchronizer.update(event)
    }
    const setMonitored = monitored => {
      if (!host) {
        state.monitored = monitored
      }
    }
    switchOnKey(event, {
      started({started}) {
        log('started')
        setMonitored(started)
      },
      monitored({monitored}) {
        log(monitored ? 'monitored' : 'unmonitored')
        setMonitored(monitored)
      },
      target({time, name, target}) {
        let message = `${name} target = ${target}`
        const t = state.targets[name]
        if (t.mtime.lessThan(time)) {
          t.mtime = time
          t.target = target
        } else {
          message += ` -- overwritten at ${t.mtime}`
        }
        log(message)
      },
      idleState: ({time, idleState}) => {
        const {monitored} = state
        log(`${idleState} ${monitored ? '' : '(unmonitored)'}`)
        if (!monitored) {
          return
        }
        const adjustment =
          idleState == 'idle' ? this.idleDelay.negate() : Duration.make(0)
        const adjustedTime = time.plus(adjustment)
        let delta = Duration.make(0)
        if (this.periodsSinceActive(time, host) < 1) {
          const {end} = getLast(state.timelines[host])
          const markDelta = adjustedTime.minus(end)
          if (markDelta.greaterThan(0)) {
            this.markTimeline(host, end, adjustedTime)
            delta = delta.plus(markDelta)
          }
        }
        delta = delta
          .minus(this.clearTimeline(host, adjustedTime))
          .clampLow(adjustment)
        this.addDailyValue(time, delta)
        const isActive = idleState == 'active'
        if (isActive) {
          this.markTimeline(host, time, time)
        }
        state.lastActives[host] = isActive
      },
    })
    this.onStateChanged()
  }

  *reversedIdleTimeline(time) {
    for (let i = this.state.sharedTimeline.length - 1; i >= 0; i--) {
      const {start, end} = this.state.sharedTimeline[i]
      yield [end, time]
      time = start
    }
    yield [new Time(-Infinity), time]
  }

  getMetrics(time) {
    const metrics = makeObject(
      Object.entries(this.state.targets).map(([name, {target}]) => {
        return [name, new Metric({name, target})]
      }),
    )
    const {weekly, daily, session, rest} = metrics

    const day = dayOfTime(time)
    weekly.value = Duration.sum(
      [...range(day, day - 7, -1)].map(day => this.getDailyValue(day)),
    )
    daily.value = this.getDailyValue(day)

    if (this.periodsSinceActive(time) < 1) {
      rest.value = Duration.make(0)
    }
    for (const [start, end] of this.reversedIdleTimeline(time)) {
      const span = end.minus(start)
      if (!rest.value) {
        rest.value = span.clampLow(0)
      }
      if (span.greaterEqual(rest.target)) {
        session.value = time.minus(end).clampLow(0)
        break
      }
    }

    rest.advised = restAdvised(metrics)

    return metrics
  }
}
