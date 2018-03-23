import fs from 'fs'
import util from 'util'

import sqlite3 from 'sqlite3'

const $ = util.promisify

export const getOpener =
        ({temporary = false} = {}) => ({newVersion, changeVersion}) => {
    const filename = 'ergometer.sqlite'
    const db = new sqlite3.Database(temporary ? '' : filename)
    db.on('error', console.error)
    ;(async () => {
        let version = 0
        if (!temporary) {
            try {
                await $(fs.access)(filename)
                version = 1
            }
            catch (e) {}
        }

        const newVersion = await changeVersion(version)
        if (newVersion != 1) console.error(`Unexpected version: ${newVersion}`)
    })()
    return db
}
