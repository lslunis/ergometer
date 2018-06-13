import {makePromise} from './util.js'
import {makeTransactor} from './transactor.js'

let nextId = 0

export const getConnector =
        ({temporary = false} = {}) => (newVersion, changeVersionFrom) => {
    const name = temporary ? `temp${nextId++}` : 'ergometer'
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
      runTransaction(t => {
        tx = t
        transactor.begin()
      }, error => transactor.fail(error))
      transactor.execute(execute)
      return transactor.executorPromise
    }

    if (db.version != newVersion) {
      transactWith(
        db.changeVersion.bind(db, db.version, newVersion)
      )(changeVersionFrom(db.version))
    }

    return transactWith(db.transaction.bind(db))
}
