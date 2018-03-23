import {setOpener} from './model.mjs'
import {getOpener} from './sqlite.mjs'
import {tests} from './test.mjs'
setOpener(getOpener({temporary: true}))

import './model.test.mjs'

;(async () => {
    await Promise.all(tests)
    console.log(`${tests.length} pass`)
})()
