export class ViewModel {
    constructor(model) { this.model = model }

    async summary(time) {
        return {monitored: await this.model.monitored()}
    }

    async details(time) {
        return 'details'
    }
}
