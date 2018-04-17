import {setConnector} from './model.mjs'
import {getConnector} from './websql.mjs'
import {run} from './test.mjs'

setConnector(getConnector({temporary: true}))

import './model.test.mjs'

;(async () => {
    console.log(`${await run()} pass`)
})()
