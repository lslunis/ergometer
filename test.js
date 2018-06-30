import {Model} from './model.js'

const tests = []

export function test(f) {
    tests.push(f)
}

export async function run(getConnector, ...modulePaths) {
    Model.connect = getConnector({temporary: true})
    await Promise.all(['./model.test.js', ...modulePaths].map(m => import(m)))
    await Promise.all(tests.map(f => f()))
}
