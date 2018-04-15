export const tests = []

export async function test(fn) {
    tests.push(async () => fn())
}
