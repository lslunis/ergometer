export function die(...args) {
  console.error(...args)
  process.exit(1)
}

export function makePromise() {
  let resolve, reject
  const promise = new Promise((resolver, rejector) => {
    resolve = resolver
    reject = rejector
  })
  return {promise, resolve, reject}
}
