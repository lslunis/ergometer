import {makePromise} from './util.mjs'

export function makeTransactor(invoke) {
  let done = false
  const executor = makePromise()
  const rejectors = new Set
  const run = (query, ...args) => {
    const {promise, resolve, reject} = makePromise()
    if (done) {
      reject(Error('Transaction has ended'))
    } else {
      rejectors.add(reject)
      ;(async () => {
        resolve(await invoke(query, ...args))
        rejectors.delete(reject)
        await promise
        if (!rejectors.size) {
          executor.resolve()
          done = true
        }
      })()
    }
    return promise
  }

  return {
    execute(execute) {
      execute(run)
      return executor.promise
    },

    reject(error) {
      for (const reject of rejectors) {
        reject(error)
      }
      executor.reject(error)
      done = true
    },
  }
}
