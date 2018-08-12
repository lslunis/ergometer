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

  addDailyValue('1970-02-01T03:59:59Z', 12)
  expectDailyValue(30).toEqual(12)
  addDailyValue('1970-02-01T04:00:00Z', 17)
  expectDailyValue(31).toEqual(17)

  addDailyValue('1970-03-01T03:59:59+01:00', 14)
  expectDailyValue(58).toEqual(14)
  addDailyValue('1970-03-01T04:00:00+01:00', 18)
  expectDailyValue(59).toEqual(18)
})

test(async () => {
  const m = await loadModel()
  const addDailyValue = (time, value) =>
    m.addDailyValue(Time.parse(time), Duration.seconds(value))

  addDailyValue('1970-01-05T12:00:00Z', 3)
  expect(m.state.firstWeek).toEqual(4)
  addDailyValue('1970-02-01T12:00:00Z', 5)
  expect(m.state.firstWeek).toEqual(4)
  addDailyValue('1970-01-01T12:00:00Z', 2)
  expect(m.state.firstWeek).toEqual(-3)
})

test(async () => {
  const m = await loadModel()
  const secondsSinceEpoch = seconds => new Time({seconds})
  const markTimeline = (peer, start, end) =>
    m.markTimeline(peer, secondsSinceEpoch(start), secondsSinceEpoch(end))
  const clearTimeline = (peer, start) =>
    m.clearTimeline(peer, secondsSinceEpoch(start))
  const expectTimelineSeconds = timeline =>
    expect(
      timeline.map(({start, end}) => [
        start.sinceEpoch.seconds,
        end.sinceEpoch.seconds,
      ]),
    )
  const expectTimeline = peer => expectTimelineSeconds(m.state.timelines[peer])
  const expectSharedTimeline = () =>
    expectTimelineSeconds(m.state.sharedTimeline)
  const thisPeer = 0
  const otherPeer = 1

  markTimeline(thisPeer, 1, 2)
  expectTimeline(thisPeer).toEqual([[1, 2]])
  expectSharedTimeline().toEqual([[1, 2]])

  markTimeline(otherPeer, 3, 4)
  expectTimeline(thisPeer).toEqual([[1, 2]])
  expectSharedTimeline().toEqual([[1, 2], [3, 4]])

  markTimeline(thisPeer, 2, 3)
  expectTimeline(thisPeer).toEqual([[1, 3]])
  expectSharedTimeline().toEqual([[1, 4]])

  clearTimeline(thisPeer, 2)
  expectTimeline(thisPeer).toEqual([[1, 2]])
  expectSharedTimeline().toEqual([[1, 2], [3, 4]])

  markTimeline(thisPeer, 0, 3)
  expectTimeline(thisPeer).toEqual([[0, 3]])
  expectSharedTimeline().toEqual([[0, 4]])
})
