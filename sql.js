import {assert, makePromise} from './util.js'

let nextDatabaseId = 0

export class Database {
  constructor(name) {
    if (name != null) {
      this.name = name
      this.temporary = false
    } else {
      this.name = `tmp${nextDatabaseId++}`
      this.temporary = true
    }

    this.engine = openDatabase(this.name, '', this.name, 5 * 1024 ** 2)
    this.migrationPromise = Promise.resolve()
    if (this.temporary) {
      console.log(this.name, 'opened at version', this.engine.version)
      this.nextStatementId = 0
      this.migrateTo('', _ => async run => {
        const rows = await run(
          `select name from sqlite_master
            where name != '__WebKitDatabaseInfoTable__' and type = 'table'`,
        )
        rows.map(r => run(`drop table "${r.name}"`))
      })
    }
  }

  transactWith(runner, methodName, ...args) {
    const transaction = makePromise()
    this.engine[methodName](
      ...args,
      tx => {
        const statementId = this.nextStatementId++
        const run = (statement, ...args) => {
          const execution = makePromise()
          if (this.temporary) {
            console.log(this.name, statementId, statement, args)
          }
          tx.executeSql(
            statement,
            args,
            (_, resultSet) => execution.resolve([...resultSet.rows]),
            (_, error) => {
              if (this.temporary) {
                console.log(this.name, statementId, error)
              }
              execution.reject(error)
              return true
            },
          )
          return execution.promise
        }
        runner(run)
      },
      error => transaction.reject(error),
      () => transaction.resolve(),
    )
    return transaction.promise
  }

  async migrateTo(newVersion, getMigrator) {
    const {migrationPromise} = this
    const nextMigration = makePromise()
    this.migrationPromise = nextMigration.promise
    try {
      await migrationPromise
      const version = this.engine.version
      const runner = assert(getMigrator(version))
      await this.transactWith(runner, 'changeVersion', version, newVersion)
      if (this.temporary) {
        console.log(this.name, 'migrated to version', this.engine.version)
      }
    } finally {
      nextMigration.resolve()
    }
  }

  read(runner) {
    return this.transactWith(runner, 'readTransaction')
  }

  readWrite(runner) {
    return this.transactWith(runner, 'transaction')
  }
}
