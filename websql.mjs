import {makePromise} from './util.mjs'
import {makeTransactor} from './transactor.mjs'

let nextId = 0

export const getConnector =
        ({temporary = false} = {}) => (newVersion, changeVersionFrom) => {
    const name = tempory ? `temp${nextId++}` : 'ergometer'
    const db = openDatabase(name, '', name, 5 * 1024 ** 2)
    
    const transactWith = runTransaction => execute => {
      let tx
      const transactor = makeTransactor((query, ...args) => {
        const {resolve, promise} = makePromise()
        tx.executeSql(query, args, (tx, resultSet) => {
          resolve(resultSet.rows)
        })
        return promise
      })
      runTransaction(t => tx = t, error => transactor.reject(error))
      return transactor.execute(execute)
    }

    if (db.version != newVersion) {
      transactWith((...args) => {
        db.changeVersion(db.version, newVersion, ...args)
      })(changeVersionFrom(db.version))
    }

    return transactWith(db.transaction.bind(db))
}
