import {assert, makePromise} from './util.js'

const unitToFactor = new Map()

export class Duration {
  static parse(duration) {
    const match = duration.match(/^([+-]?)(\d+)(?::(\d\d))?$/)
    if (!match) {
      return null
    }
    const [_, sign, hours, minutes = 0] = match
    return Duration.make({hours})
      .plus({minutes})
      .times(sign == '-' ? -1 : 1)
  }

  static make(duration) {
    if (duration instanceof Duration) {
      return duration
    }
    if ([-Infinity, 0, Infinity].includes(duration)) {
      return new Duration(duration)
    }
    const [[unit, unitValue]] = Object.entries(duration)
    return Duration[unit](unitValue)
  }

  constructor(duration) {
    this.duration = +duration
    assert(!Number.isNaN(this.duration))
  }

  negate() {
    return new Duration(-this.duration)
  }

  plus(other) {
    return new Duration(this.duration + Duration.make(other).duration)
  }

  minus(other) {
    return new Duration(this.duration - Duration.make(other).duration)
  }

  times(scalar) {
    return new Duration(this.duration * scalar)
  }

  dividedBy(other) {
    return this.duration / Duration.make(other).duration
  }

  clampLow(other) {
    return new Duration(Math.max(this.duration, Duration.make(other).duration))
  }

  clampHigh(other) {
    return new Duration(Math.min(this.duration, Duration.make(other).duration))
  }

  round(unit) {
    return Duration[unit](Math.round(this[unit]))
  }

  lessThan(other) {
    return this.duration < Duration.make(other).duration
  }

  greaterEqual(other) {
    return !this.lessThan(other)
  }

  strictlyBetween(low, high) {
    return Duration.make(low).lessThan(this) && this.lessThan(high)
  }

  format(...units) {
    // TODO: negative, infinity
    units = ['hours', 'minutes', ...units]
    let remainder = this
    const values = units.map(unit => {
      const value = Math.floor(remainder[unit])
      remainder = remainder.minus({[unit]: value})
      return '' + value
    })
    return values.map((v, i) => (!i ? v : v.padStart(2, 0))).join(':')
  }

  toJSON() {
    const {duration} = this
    return {
      duration: Number.isFinite(duration) ? duration : '' + duration,
    }
  }

  toString() {
    return `[Duration: ${this.milliseconds} ms]`
  }

  valueOf() {
    throw Error(`${this} cannot be unambiguously converted to a primitive`)
  }
}

{
  const unitToIncrementalFactor = {
    milliseconds: 10,
    centiseconds: 10,
    deciseconds: 10,
    seconds: 60,
    minutes: 60,
    hours: 24,
    days: 7,
    weeks: 1,
  }
  const units = Object.keys(unitToIncrementalFactor)
  const incrementalFactors = Object.values(unitToIncrementalFactor)
  let factor = 1

  for (const [i, unit] of units.entries()) {
    if (i > 0) factor *= incrementalFactors[i - 1]
    unitToFactor.set(unit, factor)
  }

  for (const [unit, factor] of unitToFactor) {
    Duration[unit] = value => new Duration(value * factor)
    Object.defineProperty(Duration.prototype, unit, {
      get() {
        return this.duration / factor
      },
    })
  }
}

export class Time {
  static parse(time) {
    const pattern = '^0000-00-00(?:T00:00:00(?:Z|([+-]00:00)))?$'
    const match = time.match(RegExp(pattern.replace(/0/g, '\\d')))
    if (!match) {
      return null
    }
    const [_, zone = '0'] = match
    return new Time({milliseconds: Date.parse(time)}, Duration.parse(zone))
  }

  constructor(sinceEpoch, zone) {
    this.sinceEpoch = Duration.make(sinceEpoch)
    this.zone = zone
  }

  plus(duration) {
    return new Time(this.sinceEpoch.plus(duration), this.zone)
  }

  minus(time) {
    return this.sinceEpoch.minus(time.sinceEpoch)
  }

  clampLow(other) {
    return new Time(this.sinceEpoch.clampLow(other.sinceEpoch), this.zone)
  }

  clampHigh(other) {
    return new Time(this.sinceEpoch.clampHigh(other.sinceEpoch), this.zone)
  }

  lessThan(time) {
    return this.sinceEpoch.lessThan(time.sinceEpoch)
  }

  get milliseconds() {
    return this.sinceEpoch.milliseconds
  }

  toString() {
    return `[Time: ${this.milliseconds} ms since Unix epoch]`
  }

  valueOf() {
    throw Error(`${this} cannot be unambiguously converted to a primitive`)
  }
}

const sleepSymbol = Symbol()

function finish(object, {canceled = false} = {}) {
  object[sleepSymbol].resolve(canceled)
  object[sleepSymbol] = null
}

export function sleep(delay, object = {}) {
  assert(!object[sleepSymbol])
  const {promise, resolve} = makePromise()
  object[sleepSymbol] = {
    resolve,
    timeoutId: setTimeout(() => finish(object), delay.milliseconds),
  }
  return promise
}

sleep.cancel = object => {
  if (!object[sleepSymbol]) {
    return
  }
  clearTimeout(object[sleepSymbol].timeoutId)
  finish(object, {canceled: true})
}
