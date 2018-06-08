import {setConnector} from './model.mjs'

const tests = []

export function test(f) {
    tests.push(async () => f())
}

export async function run(getConnector, ...modulePaths) {
    setConnector(getConnector({temporary: true}))
    await Promise.all(['./model.test.mjs', ...modulePaths].map(m => import(m)))
    tests.map(f => f())
    await Promise.all(tests)
    console.log(`${tests.length} pass`)
}
