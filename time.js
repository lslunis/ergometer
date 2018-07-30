import {assert, makePromise} from './util.js'

const unitToFactor = new Map()

export class Duration {
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
    this.duration = duration
  }

  between(low, high) {
    return (
      Duration.make(low).duration < this.duration &&
      this.duration < Duration.make(high).duration
    )
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
  constructor(sinceEpoch) {
    this.sinceEpoch = Duration.make(sinceEpoch)
  }

  toString() {
    return `[Time: ${this.sinceEpoch.milliseconds} ms since Unix epoch]`
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
  clearTimeout(object[sleepSymbol].timeoutId)
  finish(object, {canceled: true})
}
