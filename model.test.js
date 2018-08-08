import {Model} from './model.js'
import {expect, test} from './test.js'
import {Duration, Time} from './time.js'

async function loadModel(state) {
  const model = new Model(Time.parse('1970-01-01'), state)
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
      time: Time.parse(time),
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

test(async () => {
  const m = await loadModel()
  const addDailyValue = (time, value) =>
    m.addDailyValue(Time.parse(time), Duration.seconds(value))
  const expectDailyValue = day => expect(m.state.dailyValues[day].seconds)

  addDailyValue('1970-01-01', 3)
  expectDailyValue(-1).toEqual(3)
  addDailyValue('1970-01-01', 2)
  expectDailyValue(-1).toEqual(5)
  addDailyValue('1970-01-01', -1)
  expectDailyValue(-1).toEqual(4)
  addDailyValue('1970-01-01', -5)
  expectDailyValue(-1).toEqual(0)

  addDailyValue('1970-01-02', -1)
  expectDailyValue(0).toEqual(0)
})
