import {getOutboxInitialState, Outbox} from './outbox.js'
import {Duration, Time} from './time.js'
import {switchOnKey} from './util.js'

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
    lastIdleStates: {},
    timelines: {},
    sharedTimeline: [],
    firstWeek: Infinity,
    dailyValues: {},
  }
}

export const idleDelay = Duration.seconds(15)

export class Model {
  constructor(time, state, {onUpdate = () => {}, onPush} = {}) {
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

  update(event, peer = 0) {
    const {state} = this
    if (!state) {
      this.preloadQueue.push(() => this.update(event, peer))
      return
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
    })
    this.onUpdate()
  }
}
