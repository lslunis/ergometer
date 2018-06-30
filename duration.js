import assert from './assert.js'

const ds = 100
const s = 10 * ds
const m = 60 * s
const h = 60 * m
const d = 24 * h

export class Duration {
    static ms(n) { return new Duration(n) }
    static ds(n) { return new Duration(n * ds) }
    static s(n) { return new Duration(n * s) }
    static m(n) { return new Duration(n * m) }
    static h(n) { return new Duration(n * h) }
    static d(n) { return new Duration(n * d) }

    constructor(ms) {
        assert(Number.isFinite(ms))
        this.ms = ms
        this.ds = ms / ds
        this.s = ms / s
        this.m = ms / m
        this.h = ms / h
        this.d = ms / d
    }
}
