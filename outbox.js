import {makeObject} from './util.js'

export function getOutboxInitialState() {
  return {
    start: 0,
    events: [],
    sendStarts: {
      broadcast: 0,
      store: 0,
      archive: 0,
    },
  }
}

export class Outbox {
  constructor(state, onPush = () => {}) {
    this.state = state
    this.onPush = onPush
  }

  push(event) {
    this.state.events.push(event)
    this.onPush(
      makeObject(
        Object.entries(this.state.sendStarts).map(([method, start]) => [
          method,
          start - this.state.start,
        ]),
      ),
    )
  }

  beginSend(method) {
    const start = this.state.sendStarts[method]
    const events = this.state.events.slice(start - this.state.start)
    return events.length ? {start, events} : null
  }

  commitSend(method, newStart) {
    const {sendStarts} = this.state
    if (sendStarts[method] < newStart) {
      sendStarts[method] = newStart
    }
    const start = Math.min(...Object.values(sendStarts))
    const deleteCount = start - this.state.start
    if (deleteCount) {
      this.state.events.splice(0, deleteCount)
      this.state.start = start
    }
  }
}
