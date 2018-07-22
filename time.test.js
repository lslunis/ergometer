import {expect, test} from './test.js'
import {Duration, sleep} from './time.js'

test(() => expect(Duration.weeks(1).hours).toEqual(168))
test(() => expect(Duration.days(1).minutes).toEqual(1440))
test(() => expect(Duration.hours(1).seconds).toEqual(3600))
test(() => expect(Duration.minutes(1).deciseconds).toEqual(600))
test(() => expect(Duration.seconds(1).centiseconds).toEqual(100))
test(() => expect(Duration.deciseconds(1).milliseconds).toEqual(100))

test(() =>
  expect(
    Duration.hours(5).between(Duration.hours(4), Duration.hours(6)),
  ).toEqual(true),
)
test(() => expect(Duration.hours(5).between(0, {hours: 5})).toEqual(false))
test(() =>
  expect(Duration.hours(5).between({hours: 5}, {hours: 6})).toEqual(false),
)

test(async () => {
  const now = Date.now()
  expect(await sleep(Duration.milliseconds(4))).toEqual(false)
  const elapsed = Duration.milliseconds(Date.now() - now)
  expect(elapsed.between({milliseconds: 4 - 1}, {milliseconds: 4 + 6})).toEqual(
    true,
  )
})

test(async () => {
  const now = Date.now()
  const object = {}
  const promise = sleep(Duration.milliseconds(30), object)
  sleep.cancel(object)
  expect(await promise).toEqual(true)
  const elapsed = Duration.milliseconds(Date.now() - now)
  expect(elapsed.between({milliseconds: 0 - 1}, {milliseconds: 5})).toEqual(
    true,
  )
})
