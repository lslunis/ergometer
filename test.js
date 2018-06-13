import {setConnector} from './model.js'

const tests = []

export function test(f) {
    tests.push(f)
}

export async function run(getConnector, ...modulePaths) {
    setConnector(getConnector({temporary: true}))
    await Promise.all(['./model.test.js', ...modulePaths].map(m => import(m)))
    await Promise.all(tests.map(f => f()))
    document.body.textContent = `${tests.length} pass`
}
