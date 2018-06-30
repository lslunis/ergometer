import assert from './assert.js'
import {makePromise} from './util.js'
import {Duration} from './duration.js'
import {Model} from './model.js'
import {ViewModel} from './view_model.js'
import {getConnector} from './websql.js'

async function flash(closeAfter) {
    const {id} = await browser.windows.create({url: 'flash.html', type: 'popup', state: 'fullscreen'})
    setTimeout(async () => {
        try {
            await browser.windows.remove(id)
        } catch (e) {
            if (e.message != `No window with id: ${id}.`) {
                throw e
            }
        }
    }, closeAfter.ms)
}

function clock() {
    const ds = ms => Math.round(Duration.ms(ms).ds)
    return {
        monotime: ds(performance.timeOrigin + performance.now()),
        time: ds(Date.now()),
        tz: -new Date().getTimezoneOffset(),
    }
}

browser.browserAction.onClicked.addListener(async () => {
    store({monitored: !await model.monitored()})
})

async function setIcon({monitored}) {
    const scale = devicePixelRatio
    const size = 16 * scale
    const c = document.createElement('canvas').getContext('2d')
    const black = '#212121'
    if (!monitored) {
        const rect = (...args) => c.fillRect(...args.map(i => i * scale))
        c.fillStyle = black
        rect(4, 4, 7, 12)
        rect(9, 4, 12, 12)
    }
    return browser.browserAction.setIcon({imageData: c.getImageData(0, 0, size, size)})
}

Model.connect = getConnector()
const model = new Model
const viewModel = new ViewModel(model)

const initialized = makePromise()

async function store(record) {
    await initialized.promise
    await model.store({...clock(), ...record})
    return tickSoon()
}

async function tick() {
    const {monitored} = await viewModel.summary(clock())
    initialized.resolve()
    setIcon({monitored})
}

let tickLoop
let lastTick = -Infinity
async function tickSoon() {
    if (tickLoop) {
        clearTimeout(tickLoop)
    }
    const normalDelay = 1000
    const earlyDelay = normalDelay - Math.max(0, Date.now() - lastTick)
    if (earlyDelay > 0) {
        tickLoop = setTimeout(tickSoon, earlyDelay)
        return
    }
    lastTick = Date.now()
    if (await tick()) {
        tickLoop = setTimeout(tickSoon, normalDelay)
    }
}

tickSoon()
store({started: true})
const idleStateChanged = idleState => store({idleState})
browser.idle.setDetectionInterval(model.idleDelay.s)
browser.idle.onStateChanged.addListener(idleStateChanged)
browser.idle.queryState(model.idleDelay.s).then(idleStateChanged)

// TODO: Turn this into a UI.
function setTarget(name, targetMinutes) {
    const target = Duration.m(targetMinutes)
    assert(Number.isInteger(target.m) && 0 < target.d && target.d < 1)
    store({name, target: target.ds})
}

async function details() {
    console.log(JSON.stringify(await viewModel.details(clock()), null, 1))
}
