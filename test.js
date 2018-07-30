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

const tests = []

export function test(f) {
  tests.push(f)
}

;(async () => {
  await Promise.all(
    ['util', 'time', 'outbox'].map(m => import(`./${m}.test.js`)),
  )
  let runningCount = tests.length
  let passCount = 0
  await new Promise(resolve => {
    tests.map(async f => {
      try {
        await f()
        passCount++
      } finally {
        if (!--runningCount) {
          resolve()
        }
      }
    })
  })
  const failCount = tests.length - passCount
  let message
  if (!failCount) {
    message = `${passCount} tests pass`
    console.log(message)
  } else {
    message = `${failCount} tests fail`
    console.error(message)
    document.body.style.color = 'red'
  }
  document.body.textContent = message
})()
