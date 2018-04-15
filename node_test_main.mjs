import {setConnector} from './model.mjs'
import {getConnector} from './sqlite.mjs'
import {tests} from './test.mjs'

console.log('setConnector')
setConnector(getConnector({temporary: true}))

import './model.test.mjs'

;(async () => {
  for (const test of tests) {
    test()
  }
  await Promise.all(tests)
  console.log(`${tests.length} pass`)
})()
