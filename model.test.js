import {Model, restAdvised, Metric} from './model.js'
import {expect, test} from './test.js'
import {Duration, Time} from './time.js'
import {makeObject} from './util.js'

async function loadModel() {
  const model = new Model(Time.parse('1970-01-01'), null, {
    idleDelay: Duration.seconds(15),
    onUpdate() {},
    onPush() {},
  })
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
  const otherHost = 1
  const m = await loadModel()
  m.update({monitored: false})
  m.update({started: true}, otherHost)
  expect(m.state.monitored).toEqual(false)
  m.update({monitored: true}, otherHost)
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

function updateIdleState(m, updates) {
  updates.map(args => {
    const [string, host] = typeof args == 'string' ? [args] : args
    const [time, idleState] = string.split(' ')
    m.update({time: Time.parse(time), idleState}, host)
  })
}

async function testDailyValue() {
  const m = await loadModel()
  return {
    m,
    addDailyValue(time, value) {
      m.addDailyValue(Time.parse(time), Duration.seconds(value))
    },
    updateIdleState(...updates) {
      updateIdleState(m, updates)
    },
    expectDailyValue(day) {
      return expect(m.state.dailyValues[day].seconds)
    },
  }
}

test(async () => {
  const {addDailyValue, expectDailyValue} = await testDailyValue()
  addDailyValue('1970-01-01T12:00:00Z', 3)
  expectDailyValue(0).toEqual(3)
  addDailyValue('1970-01-01T12:00:00Z', 2)
  expectDailyValue(0).toEqual(5)
  addDailyValue('1970-01-01T12:00:00Z', -1)
  expectDailyValue(0).toEqual(4)
  addDailyValue('1970-01-01T12:00:00Z', -5)
  expectDailyValue(0).toEqual(0)
})

test(async () => {
  const {addDailyValue, expectDailyValue} = await testDailyValue()
  addDailyValue('1970-01-01T12:00:00Z', -1)
  expectDailyValue(0).toEqual(0)
})

test(async () => {
  const {addDailyValue, expectDailyValue} = await testDailyValue()
  addDailyValue('1970-01-01T03:59:59Z', 2)
  expectDailyValue(-1).toEqual(2)
  addDailyValue('1970-01-01T04:00:00Z', 3)
  expectDailyValue(0).toEqual(3)
})

test(async () => {
  const {addDailyValue, expectDailyValue} = await testDailyValue()
  addDailyValue('1970-01-01T03:59:59+01:00', 4)
  expectDailyValue(-1).toEqual(4)
  addDailyValue('1970-01-01T04:00:00+01:00', 2)
  expectDailyValue(0).toEqual(2)
})

test(async () => {
  const {m, addDailyValue} = await testDailyValue()
  addDailyValue('1970-01-05T12:00:00Z', 10)
  expect(m.state.firstWeek).toEqual(4)
  addDailyValue('1970-02-01T12:00:00Z', 20)
  expect(m.state.firstWeek).toEqual(4)
  addDailyValue('1970-01-01T12:00:00Z', 30)
  expect(m.state.firstWeek).toEqual(-3)
})

test(async () => {
  const {updateIdleState, expectDailyValue} = await testDailyValue()
  updateIdleState(
    '1970-01-01T03:00:00Z active',
    '1970-01-01T04:00:10+01:00 active',
  )
  expectDailyValue(0).toEqual(10)
})

test(async () => {
  const {updateIdleState, expectDailyValue} = await testDailyValue()
  updateIdleState(
    '1970-01-01T04:00:00+01:00 active',
    '1970-01-01T03:00:10Z active',
  )
  expectDailyValue(-1).toEqual(10)
})

async function testTimeline() {
  const m = await loadModel()
  const secondsSinceEpoch = seconds => new Time({seconds})
  const expectTimelineSeconds = timeline =>
    expect(
      timeline.map(({start, end}) => [
        start.sinceEpoch.seconds,
        end.sinceEpoch.seconds,
      ]),
    )
  return {
    markTimeline(host, start, end) {
      m.markTimeline(host, secondsSinceEpoch(start), secondsSinceEpoch(end))
    },
    clearTimeline(host, start) {
      return m.clearTimeline(host, secondsSinceEpoch(start)).seconds
    },
    expectTimeline(host) {
      return expectTimelineSeconds(m.state.timelines[host])
    },
    expectSharedTimeline() {
      return expectTimelineSeconds(m.state.sharedTimeline)
    },
  }
}

test(async () => {
  const {
    markTimeline,
    clearTimeline,
    expectTimeline,
    expectSharedTimeline,
  } = await testTimeline()
  const thisHost = 0
  const otherHost = 1

  markTimeline(thisHost, 1, 2)
  expectTimeline(thisHost).toEqual([[1, 2]])
  expectSharedTimeline().toEqual([[1, 2]])

  markTimeline(otherHost, 3, 4)
  expectTimeline(thisHost).toEqual([[1, 2]])
  expectSharedTimeline().toEqual([[1, 2], [3, 4]])

  markTimeline(thisHost, 2, 3)
  expectTimeline(thisHost).toEqual([[1, 3]])
  expectSharedTimeline().toEqual([[1, 4]])

  expect(clearTimeline(thisHost, 2)).toEqual(1)
  expectTimeline(thisHost).toEqual([[1, 2]])
  expectSharedTimeline().toEqual([[1, 2], [3, 4]])

  markTimeline(thisHost, 0, 3)
  expectTimeline(thisHost).toEqual([[0, 3]])
  expectSharedTimeline().toEqual([[0, 4]])

  expect(clearTimeline(thisHost, 0)).toEqual(3)
  expectTimeline(thisHost).toEqual([[0, 0]])

  markTimeline(thisHost, 1, 2)
  markTimeline(thisHost, 4, 6)
  markTimeline(thisHost, 8, 11)
  expect(clearTimeline(thisHost, 5)).toEqual(4)
})

async function testMetrics(...names) {
  const m = await loadModel()
  m.update({
    time: Time.parse('1970-01-01'),
    name: 'rest',
    target: Duration.minutes(1),
  })
  return {
    m,
    updateIdleState(...updates) {
      updateIdleState(m, updates)
    },
    expectValues(time) {
      return expect(
        makeObject(
          Object.values(m.getMetrics(Time.parse(time)))
            .filter(({name}) => names.includes(name))
            .map(({name, value}) => [name, value.seconds]),
        ),
      )
    },
  }
}

test(async () => {
  const {updateIdleState, expectValues} = await testMetrics('weekly', 'daily')
  updateIdleState(
    '1970-01-01T12:00:00Z active',
    '1970-01-01T12:00:05Z locked',
    '1970-01-07T12:00:00Z active',
    '1970-01-07T12:00:10Z locked',
  )

  expectValues('1970-01-01T03:59:59Z').toEqual({weekly: 0, daily: 0})
  expectValues('1970-01-02T03:59:59Z').toEqual({weekly: 5, daily: 5})
  expectValues('1970-01-02T04:00:00Z').toEqual({weekly: 5, daily: 0})

  expectValues('1970-01-08T03:59:59Z').toEqual({weekly: 15, daily: 10})
  expectValues('1970-01-08T04:00:00Z').toEqual({weekly: 10, daily: 0})

  expectValues('1970-01-14T04:00:00Z').toEqual({weekly: 0, daily: 0})
})

test(async () => {
  const {updateIdleState, expectValues} = await testMetrics(
    'daily',
    'session',
    'rest',
  )
  const otherHost = 1
  expectValues('1970-01-01T12:00:00Z').toEqual({
    daily: 0,
    session: 0,
    rest: Infinity,
  })

  updateIdleState('1970-01-01T12:00:00Z active', '1970-01-01T12:00:10Z active')
  expectValues('1970-01-01T12:00:15Z').toEqual({
    daily: 10,
    session: 15,
    rest: 0,
  })

  updateIdleState('1970-01-01T12:00:20Z idle')
  expectValues('1970-01-01T12:01:04Z').toEqual({
    daily: 5,
    session: 64,
    rest: 59,
  })
  expectValues('1970-01-01T12:01:05Z').toEqual({
    daily: 5,
    session: 0,
    rest: 60,
  })

  updateIdleState(
    '1970-01-01T12:01:15Z active',
    ['1970-01-01T12:01:20Z active', otherHost],
    ['1970-01-01T12:01:25Z locked', otherHost],
    '1970-01-01T12:01:30Z active',
  )
  expectValues('1970-01-01T12:01:30Z').toEqual({
    daily: 10,
    session: 15,
    rest: 0,
  })

  updateIdleState('1970-01-01T12:03:00Z active', '1970-01-01T12:03:00Z locked')
  expectValues('1970-01-01T12:02:55Z').toEqual({
    daily: 10,
    session: 0,
    rest: 0,
  })
  expectValues('1970-01-01T12:03:05Z').toEqual({
    daily: 10,
    session: 5,
    rest: 5,
  })

  updateIdleState('1970-01-01T12:03:10Z active', '1970-01-01T12:03:10Z idle')
  expectValues('1970-01-01T12:03:10Z').toEqual({
    daily: 10,
    session: 0,
    rest: 100,
  })

  updateIdleState('1970-01-01T12:03:15Z active', '1970-01-01T12:03:10Z active')
  expectValues('1970-01-01T12:03:15Z').toEqual({
    daily: 10,
    session: 5,
    rest: 0,
  })
})

test(async () => {
  const {m, updateIdleState, expectValues} = await testMetrics(
    'daily',
    'session',
    'rest',
  )
  updateIdleState('1970-01-01T12:00:00Z active')
  m.update({monitored: false})
  updateIdleState('1970-01-01T12:00:05Z active')
  updateIdleState('1970-01-01T12:00:20Z active')
  expectValues('1970-01-01T12:00:20Z').toEqual({
    daily: 0,
    session: 20,
    rest: 20,
  })
})

test(async () => {
  const expectRestAdvised = metrics =>
    expect(
      restAdvised(
        makeObject(
          Object.entries(metrics).map(([name, value]) => {
            return [
              name,
              new Metric({
                name,
                value: Duration.minutes(value),
                target: Duration.minutes(1),
              }),
            ]
          }),
        ),
      ),
    )

  expectRestAdvised({session: 0, rest: 1}).toEqual(false)

  expectRestAdvised({session: 0, rest: 0.74}).toEqual(false)
  expectRestAdvised({session: 0, rest: 0.75}).toEqual(true)

  expectRestAdvised({session: 0.49, rest: 0.375}).toEqual(false)
  expectRestAdvised({session: 0.5, rest: 0.375}).toEqual(true)

  expectRestAdvised({session: 0.99, rest: 0.001}).toEqual(false)
  expectRestAdvised({session: 1, rest: 0.01}).toEqual(true)

  expectRestAdvised({session: 1, rest: 0}).toEqual(false)
})
