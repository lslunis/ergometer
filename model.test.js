import {Model} from './model.js'
import {expect, test} from './test.js'
import {Duration, Time} from './time.js'

function parseTime(time) {
  return new Time({milliseconds: Date.parse(time)})
}

async function loadModel(state) {
  const model = new Model(parseTime('1970-01-01'), state)
  await model.loaded
  return model
}

test(async () => {
  const m = await loadModel()
  expect(m.state.monitored).toEqual(true)
  m.update({monitored: false})
  expect(m.state.monitored).toEqual(false)
  m.update({monitored: true})
  expect(m.state.monitored).toEqual(true)
})

test(async () => {
  const otherPeer = 1
  const m = await loadModel()
  m.update({monitored: false})
  m.update({started: true}, otherPeer)
  expect(m.state.monitored).toEqual(false)
  m.update({monitored: true}, otherPeer)
  expect(m.state.monitored).toEqual(false)
})

test(async () => {
  const m = await loadModel()
  const updateTarget = (time, minutes) =>
    m.update({
      time: parseTime(time),
      name: 'rest',
      target: Duration.make({minutes}),
    })
  const expectTarget = () => expect(m.state.targets.rest.target.minutes)

  expectTarget().toEqual(5)
  updateTarget('2011-11-11T11:11:10Z', 1)
  expectTarget().toEqual(1)
  updateTarget('2011-11-11T11:11:10Z', 2)
  expectTarget().toEqual(1)
  updateTarget('2011-11-11T11:11:12Z', 2)
  expectTarget().toEqual(2)
})
