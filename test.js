export const expect = actual => ({
  toEqual(expected) {
    expected = JSON.stringify(expected)
    if (actual && typeof actual != 'string' && actual[Symbol.iterator]) {
      actual = [...actual]
    }
    actual = JSON.stringify(actual)
    if (expected != actual) {
      throw Error(`expected ${expected}; got ${actual}`)
    }
  },
  async toReject(expected = {}) {
    try {
      await actual()
    } catch (e) {
      for (const [k, v] of Object.entries(expected)) {
        expect(e[k]).toEqual(v)
      }
      return
    }
    throw Error('Did not throw')
  },
})

const firstTests = []
const otherTests = []

export function test(f, first) {
  ;(first ? firstTests : otherTests).push(f)
}

;(async () => {
  await Promise.all(['util', 'sql'].map(m => import(`./${m}.test.js`)))
  let message = 'some tests fail'
  try {
    let count = 0
    for (const tests of [firstTests, otherTests]) {
      await Promise.all(tests.map(f => f()))
      count += tests.length
    }
    message = `${count} tests pass`
  } finally {
    console.log((document.body.textContent = message))
  }
})()
