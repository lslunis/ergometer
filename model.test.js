import * as assert from './assert.js';
import {test} from './test.js'
import {Model} from './model.js'

test(async () => {
    const model = new Model
    await model.transact(async (run) => {
        assert.equals([{1: 1}], await run('select 1'))
    })
})

test(async () => {
    const model = new Model
    const status = await model.status()
    assert.equals({
        monitoring: true,
        metrics: [
            {name: 'daily', target: 0, value: 0},
            {name: 'session', target: 0, value: 0},
            {name: 'rest', target: 0, value: 0},
        ],
    }, status)
})
