import {assert, makePromise} from './util.js'

const unitToFactor = new Map()

export class Duration {
  static make(value) {
    if (value instanceof Duration) return value
    if (value == 0) return new Duration(0)

    const [[unit, unitValue]] = Object.entries(value)
    return Duration[unit](unitValue)
  }

  constructor(value) {
    this.value = value
  }

  between(low, high) {
    return (
      Duration.make(low).value < this.value &&
      this.value < Duration.make(high).value
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
        return this.value / factor
      },
    })
  }
}

export class Time {
  constructor(value) {
    this.value = value
  }

  toString() {
    return `[Time: ${this.value.milliseconds} ms since Unix epoch]`
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
