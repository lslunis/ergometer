function log(message, isError) {
  console[isError ? 'error' : 'log'](message)
  const p = document.createElement('p')
  p.textContent = message
  if (isError) {
    p.style.color = 'red'
  }
  document.body.appendChild(p)
}

function logError(message) {
  log(message, true)
}

let rejectEnabled = true

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
    if (!rejectEnabled) {
      return
    }
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

expect.noReject = () => {
  rejectEnabled = false
}

const tests = []

export function test(f) {
  tests.push(f)
}

;(async () => {
  addEventListener('error', ({error}) => logError(error))
  addEventListener('unhandledrejection', ({reason}) => logError(reason))
  await Promise.all(
    ['model', 'time', 'util'].map(m => import(`./${m}.test.js`)),
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
    log(`${passCount} tests pass`)
  } else {
    logError(`${failCount} tests fail`)
  }
  if (!rejectEnabled) {
    logError('Rejection expectations are disabled')
  }
})()
