import {setConnector} from './model.mjs'
import {getConnector} from './websql.mjs'
import {run} from './test.mjs'

;(async () => {
    setConnector(getConnector({temporary: true}))
    await import('./model.test.mjs')
    console.log(`${await run()} pass`)
})()
