import {getOutboxInitialState, Outbox} from './outbox.js'
import {expect, test} from './test.js'

function makeOutbox(state = {}) {
  return new Outbox({...getOutboxInitialState(), ...state})
}

test(() => {
  const q = makeOutbox()
  q.push(1)
  expect(q.state.events).toEqual([1])
  ;['broadcast', 'store'].map(method => {
    expect(q.beginSend(method)).toEqual({start: 0, events: [1]})
    q.commitSend(method, 1)
  })
  expect(q.state).toEqual({
    start: 1,
    events: [],
    sendStarts: {broadcast: 1, store: 1},
  })
})

test(() => {
  const q = makeOutbox({events: [1]})
  expect(q.beginSend('store')).toEqual({start: 0, events: [1]})
  q.push(2)
  expect(q.beginSend('store')).toEqual({start: 0, events: [1, 2]})
})

test(() => {
  const q = makeOutbox({events: [1]})
  q.commitSend('store', 1)
  expect(q.beginSend('store')).toEqual(null)
  expect(q.beginSend('broadcast').events).toEqual([1])
})

test(() => {
  const q = makeOutbox({
    events: [1, 2],
    sendStarts: {store: 2},
  })
  q.commitSend('store', 1)
  expect(q.beginSend('store')).toEqual(null)
})
