import {makePromise} from './util.mjs'

export function makeTransactor(invoke) {
    let done = false
    const beginning = makePromise()
    const executor = makePromise()
    const rejectors = new Set
    const run = (query, ...args) => {
        const {promise, resolve, reject} = makePromise()
        if (done) {
            reject(Error('Transaction has ended'))
        } else {
            rejectors.add(reject)
            ;(async () => {
                await beginning.promise
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
        begin: beginning.resolve,
        executorPromise: executor.promise,
        
        execute(execute) {
            execute(run)
        },

        fail(error) {
            for (const reject of rejectors) {
                reject(error)
            }
            executor.reject(error)
            done = true
        },
    }
}
