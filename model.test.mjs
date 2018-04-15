import assert from 'assert'

import {test} from './test.mjs'
import {Model} from './model.mjs'

console.log('model.test.mjs')

test(async () => {
  const model = new Model
  await model.transact(async (run) => {
    assert.equal(await run('select 1'), 1)
  })
})
