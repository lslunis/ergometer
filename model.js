let connect

export function setConnector(connector) {
    connect = connector
}

function makeMetric(name) {
    return {name, target: 0, value: 0}
}

export class Model {
    constructor() {
        this.transact = connect(1, oldVersion => run => {
            if (oldVersion != 0) {
                die({oldVersion})
            }
        })
    }

    async status() {
        return {
            monitoring: true,
            metrics: ['daily', 'session', 'rest'].map(makeMetric),
        }
    }
}
