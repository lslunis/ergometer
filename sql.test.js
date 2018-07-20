import {Database} from './sql.js'
import {expect, test} from './test.js'
import {makePromise} from './util.js'

test(async () => {
  const db = new Database()
  db.migrateTo('1', v => run => expect(v).toEqual(''))
  await db.migrateTo('2', v => run => expect(v).toEqual('1'))
})

test(async () => {
  const finishedFirst = makePromise()
  await new Database().read(async run => {
    expect(await run('select 1')).toEqual([{1: 1}])
    finishedFirst.resolve('run')
  })
  finishedFirst.resolve('read')
  expect(await finishedFirst.promise).toEqual('run')
})

test(async () => {
  const db = new Database()
  await db.migrateTo('1', _ => run =>
    run('create table xs (x integer primary key)'),
  )
  db.readWrite(run => run('insert into xs values (42)'))
  await db.read(async run =>
    expect(await run('select * from xs')).toEqual([{x: 42}]),
  )
})

test(() =>
  expect(() =>
    new Database().read(run =>
      expect(() => run('select * from nothing')).toReject({code: 5}),
    ),
  ).toReject({code: 0}),
)
