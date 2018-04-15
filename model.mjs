let connect

export function setConnector(connector) {
  console.log(connect)
  connect = connector
  console.log(connect)
}

export class Model {
  constructor() {
    console.log('model')
    this.transact = connect(1, oldVersion => run => {
      if (oldVersion != 0) {
        die({oldVersion})
      }
      run(`
        create table peers(
          id integer primary key autoincrement)`)
      run(`
        create table records(
          id integer primary key autoincrement,
          creator integer,
          ctime real,
          start real,
          stop real,
          k text,
          v text,
          foreign key(creator) references peers(id))`)
      run(`
        create table queue(
          record integer,
          peer integer,
          foreign key(record) references records(id),
          primary key(record, peer)
        ) without rowid`)
    })
  }
}



