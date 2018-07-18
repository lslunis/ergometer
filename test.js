export const expect = actual => ({
  toEqual(expected) {
    expected = JSON.stringify(expected)
    actual = JSON.stringify(actual)
    if (expected != actual) {
      throw Error(`${expected} != ${actual}`)
    }
  },
})

const tests = []

export function test(f) {
  tests.push(f)
}

;(async () => {
  await Promise.all([].map(m => import(`./${m}.test.js`)))
  let message = 'some tests fail'
  try {
    await Promise.all(tests.map(f => f()))
    message = `${tests.length} tests pass`
  } finally {
    console.log((document.body.textContent = message))
  }
})()
