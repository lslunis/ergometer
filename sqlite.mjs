import fs from 'fs'
import util from 'util'

import sqlite3 from 'sqlite3'

import {die, makePromise} from './util.mjs'
import {makeTransactor} from './transactor.mjs'

const $ = util.promisify

export const getConnector =
        ({temporary = false} = {}) => (newVersion, changeVersionFrom) => {
    const filename = 'ergometer.sqlite'
    const db = new sqlite3.Database(temporary ? '' : filename)
    db.on('error', die)
    const invoke = $(db.all)
    let nextTransaction = Promise.resolve()
    const transact = async (execute) => {
        const currentTransaction = nextTransaction
        const lock = makePromise()
        nextTransaction = lock.promise
        try {
            await currentTransaction
            await invoke('begin')
            const transactor = makeTransactor(async (...args) => {
                try {
                    return await invoke(...args)
                } catch (error) {
                    transactor.reject(error)
                }
            })
            await transactor.execute(execute)
            await invoke('commit')
        } finally {
            lock.resolve()
        }
    }
    ;(async () => {
        let version = 0
        if (!temporary) {
            try {
                await $(fs.access)(filename)
                version = 1
            } catch (e) {}
        }
        if (newVersion != 1) {
            die(`Unexpected version: ${newVersion}`)
        }
        transact(changeVersionFrom(version))
    })()
    return transact
}
