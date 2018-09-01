import {colorize} from './colors.js'
import {Model} from './model.js'
import {revive} from './reviver.js'
import {Duration, Time, sleep} from './time.js'
import {getIcon} from './icon.js'

function now() {
  const sinceEpoch = Duration.milliseconds(Date.now()).round('deciseconds')
  const zone = Duration.minutes(-new Date().getTimezoneOffset())
  return new Time(sinceEpoch, zone)
}

function setIcon(data) {
  return browser.browserAction.setIcon({
    imageData: getIcon(16, data, {asImageData: true}),
  })
}

async function flash(name, closeAfter = Duration.seconds(0.5), fragment = '') {
  const {id} = await browser.windows.create({
    url: `${name}.html#${fragment}`,
    type: 'popup',
    state: 'fullscreen',
  })
  await sleep(closeAfter)
  try {
    await browser.windows.remove(id)
  } catch (e) {
    if (e.message != `No window with id: ${id}.`) {
      throw e
    }
  }
}

let ticking
let wasMonitored
let lastFlashed

function tick() {
  if (ticking) {
    return
  }
  ticking = true
  sleep.cancel(tick)
  if (!model.state) {
    return
  }

  const time = now()
  const {monitored} = model.state
  const metrics = colorize(model.getMetrics(time))
  const {session, rest} = metrics
  const advisedMetrics = Object.values(metrics).filter(m => m.advised)
  setIcon({monitored, metrics: advisedMetrics})
  if (monitored) {
    // todo: flash if attained
  } else {
    if (wasMonitored) {
      lastFlashed = time.minus(rest.target)
    }
    if (
      time.minus(lastFlashed).greaterEqual(session.target.plus(rest.target))
    ) {
      flash('unmonitored')
      lastFlashed = time
    }
  }
  wasMonitored = monitored
  send('details', {monitored, metrics})

  const t = model.periodsSinceActive(time)
  if (0.8 <= t && t < 1) {
    model.update({time, idleState: 'active'})
  }

  if (!rest.attained) {
    scheduleTick()
  }
  ticking = false
}

async function scheduleTick() {
  if (await sleep(Duration.seconds(1), tick)) {
    return
  }
  tick()
}

async function load() {
  const results = await browser.storage.local.get('state')
  return revive(results.state)
}

let storeCount = 0
let meanStoreLatency = 0
let maxStoreLatency = 0
const model = new Model(now(), load(), {
  verbose: true,
  idleDelay: Duration.seconds(15),
  keepActivePeriod: Duration.seconds(25),
  async onUpdate() {
    tick()
    const start = performance.now()
    await browser.storage.local.set({state: JSON.stringify(model.state)})
    const latency = performance.now() - start
    storeCount++
    meanStoreLatency =
      (meanStoreLatency * (storeCount - 1) + latency) / storeCount
    maxStoreLatency = Math.max(maxStoreLatency, latency)
    if (!(storeCount % 1000)) {
      console.log({meanStoreLatency, maxStoreLatency})
    }
  },
  onPush() {},
})
model.loaded.then(tick)

function update(event) {
  event.time = now()
  model.update(event)
}
window.ergoUpdate = () => update({name: 'rest', target: Duration.hours(42)})

const ports = new Map()
browser.runtime.onConnect.addListener(port => {
  ports.set(port.name, port)
  port.onMessage.addListener(async event => update(await revive(event)))
  port.onDisconnect.addListener(() => ports.delete(port.name))
  tick()
})

function send(name, message) {
  if (!ports.has(name)) {
    return
  }
  ports.get(name).postMessage(JSON.stringify(message))
}

const idleStateChanged = idleState => update({idleState})
browser.idle.setDetectionInterval(model.idleDelay.seconds)
browser.idle.onStateChanged.addListener(idleStateChanged)
browser.idle.queryState(model.idleDelay.seconds).then(idleStateChanged)

let errorCount = 0
function handleError(error) {
  errorCount++
  browser.browserAction.setBadgeText({text: '' + errorCount})
  browser.browserAction.setBadgeBackgroundColor({color: 'red'})
  throw error
}

addEventListener('error', ({error}) => handleError(error))
addEventListener('unhandledrejection', ({reason}) => handleError(reason))
