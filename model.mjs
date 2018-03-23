export function setOpener(){}

`
create table records(
    id integer primary key autoincrement,
    t1 real unique on conflict rollback,
    t2 real unique on conflict rollback,
    k text,
    v text)

create table queue(
    rid integer
    foreign key(rid) references records(id),
    primary key(rid, peer)) without rowid
`
