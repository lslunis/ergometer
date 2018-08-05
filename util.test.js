import {expect, test} from './test.js'
import {enumerate, range, sha256, switchOnKey, zip} from './util.js'

test(() => expect(enumerate('abc')).toEqual([[0, 'a'], [1, 'b'], [2, 'c']]))

test(() => expect(() => range().next()).toReject())
test(() => expect(range(2)).toEqual([0, 1]))
test(() => expect(range(1, 3)).toEqual([1, 2]))
test(() => expect(range(2, 8, 2)).toEqual([2, 4, 6]))

test(async () =>
  expect(await sha256('')).toEqual(
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  ),
)

const handlers = {
  x() {},
  y({y}) {
    return y
  },
}
test(() => expect(switchOnKey({y: 2}, handlers)).toEqual(2))
test(() => expect(() => switchOnKey({x: 1, y: 2}, handlers)).toReject())
test(() => expect(() => switchOnKey({z: 3}, handlers)).toReject())
test(() => expect(switchOnKey({z: 3}, handlers, ({z}) => z * 2)).toEqual(6))
test(() =>
  expect(switchOnKey({}, {constructor: () => 'c'}, () => 'd')).toEqual('d'),
)
test(() => expect(switchOnKey({constructor: 'c'}, {}, () => 'd')).toEqual('d'))

test(() => expect(zip([], [])).toEqual([]))
test(() => expect(zip([11, 22], [33, 44])).toEqual([[11, 33], [22, 44]]))
test(() =>
  expect(zip([10, 20, 30], [40, 50])).toEqual([
    [10, 40],
    [20, 50],
    [30, undefined],
  ]),
)
test(() =>
  expect(zip([10, 20], [30, 40, 50])).toEqual([
    [10, 30],
    [20, 40],
    [undefined, 50],
  ]),
)
