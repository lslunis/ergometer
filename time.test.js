import {expect, test} from './test.js'
import {Duration, sleep, Time} from './time.js'

test(() => expect(Duration.weeks(1).hours).toEqual(168))
test(() => expect(Duration.days(1).minutes).toEqual(1440))
test(() => expect(Duration.hours(1).seconds).toEqual(3600))
test(() => expect(Duration.minutes(1).deciseconds).toEqual(600))
test(() => expect(Duration.seconds(1).centiseconds).toEqual(100))
test(() => expect(Duration.deciseconds(1).milliseconds).toEqual(100))

test(() =>
  expect(Duration.hours(3).plus({hours: 4})).toEqual(Duration.hours(7)),
)

test(() =>
  expect(Duration.hours(3).minus({hours: 4})).toEqual(Duration.hours(-1)),
)

test(() => expect(Duration.days(5).times(-3)).toEqual(Duration.days(-15)))

test(() => expect(Duration.hours(-30).round('days')).toEqual(Duration.days(-1)))
test(() => expect(Duration.hours(-12).round('days')).toEqual(Duration.days(0)))
test(() => expect(Duration.hours(8).round('days')).toEqual(Duration.days(0)))
test(() => expect(Duration.hours(12).round('days')).toEqual(Duration.days(1)))
test(() => expect(Duration.hours(22).round('days')).toEqual(Duration.days(1)))
test(() => expect(Duration.hours(24).round('days')).toEqual(Duration.days(1)))
test(() => expect(Duration.hours(30).round('days')).toEqual(Duration.days(1)))
test(() => expect(Duration.hours(36).round('days')).toEqual(Duration.days(2)))
test(() => expect(Duration.hours(40).round('days')).toEqual(Duration.days(2)))
test(() => expect(Duration.hours(48).round('days')).toEqual(Duration.days(2)))

test(() =>
  expect(
    Duration.hours(5).strictlyBetween(Duration.hours(4), Duration.hours(6)),
  ).toEqual(true),
)
test(() =>
  expect(Duration.hours(5).strictlyBetween(0, {hours: 5})).toEqual(false),
)
test(() =>
  expect(Duration.hours(5).strictlyBetween({hours: 5}, {hours: 6})).toEqual(
    false,
  ),
)

test(() => expect(Duration.make(0).format()).toEqual('0:00'))
test(() => expect(Duration.seconds(1000).format()).toEqual('0:16'))
test(() => expect(Duration.seconds(1000).format('seconds')).toEqual('0:16:40'))
test(() => expect(Duration.weeks(1).format()).toEqual('168:00'))

test(() => expect(Time.parse('')).toEqual(null))

test(() => expect(Time.parse('2018-01-01').zone).toEqual(Duration.make(0)))

test(() => expect(Time.parse('2018-01-01T01:01:01')).toEqual(null))

test(() =>
  expect(Time.parse('2018-01-01T00:00:00-08:30').zone).toEqual(
    Duration.hours(-8.5),
  ),
)

test(() =>
  expect(Time.parse('2018-01-01T00:00:00+10:00').zone).toEqual(
    Duration.hours(10),
  ),
)

test(() =>
  expect(Time.parse('2018-01-01T00:00:00Z').zone).toEqual(Duration.make(0)),
)

test(async () => {
  const now = Date.now()
  expect(await sleep(Duration.milliseconds(4))).toEqual(false)
})

test(async () => {
  const now = Date.now()
  const object = {}
  const promise = sleep(Duration.milliseconds(30), object)
  sleep.cancel(object)
  expect(await promise).toEqual(true)
})
