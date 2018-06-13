export function equals(expected, actual) {
    expected = JSON.stringify(expected)
    if ('length' in actual) actual = [...actual]
    actual = JSON.stringify(actual)
    if (expected != actual) throw Error(`${expected} != ${actual}`)
}
