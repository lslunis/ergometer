import {Duration} from './duration.js'

function makeMetric([name, target]) {
    return {name, target, value: 0}
}

export class Model {
    constructor() {
        this.transact = Model.connect(1, oldVersion => run => {
            if (oldVersion != 0) {
                die({oldVersion})
            }
        })
        this.idleDelay = Duration.s(15)
        this._monitored = false
    }

    async store(record) {
        if (record.monitored != null) {
            this._monitored = record.monitored
        }
    }

    async monitored() { return this._monitored }

    async collate(time, {history = false} = {}) {

    }
}
