import * as assert from './assert.mjs';
import {test} from './test.mjs'
import {Model} from './model.mjs'

test(async () => {
    const model = new Model
    await model.transact(async (run) => {
        assert.equals([{1: 1}], await run('select 1'))
    })
})
