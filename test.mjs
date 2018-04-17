const tests = []

export async function test(fn) {
    tests.push(async () => fn())
}

export async function run() {
    for (const test of tests) {
        test()
    }
    await Promise.all(tests)
    return tests.length
}
