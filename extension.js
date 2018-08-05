import {black, colorize} from './colors.js'
import {idleDelay, Model} from './model.js'
import {Duration, Time, sleep} from './time.js'
import {assert} from './util.js'

async function flash(closeAfter) {
  const {id} = await browser.windows.create({
    url: 'flash.html',
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

function now() {
  const sinceEpoch = Duration.milliseconds(Date.now()).round('deciseconds')
  const zone = Duration.minutes(-new Date().getTimezoneOffset())
  return new Time(sinceEpoch, zone)
}

function setIcon({monitored}) {
  const scale = devicePixelRatio
  const size = 16 * scale
  const c = document.createElement('canvas').getContext('2d')
  if (!monitored) {
    const rect = (...args) => c.fillRect(...args.map(i => i * scale))
    c.fillStyle = black
    rect(4, 4, 3, 8)
    rect(9, 4, 3, 8)
  }
  return browser.browserAction.setIcon({
    imageData: c.getImageData(0, 0, size, size),
  })
}

function update(event) {
  event.time = now()
  model.update(event)
}

function tick() {
  sleep.cancel(tick)
  if (!model.state) {
    return
  }
  const {monitored} = model.state
  const metrics = model.getMetrics(now())
  setIcon({monitored})
  send('details', {monitored, metrics})
  if (!metrics.rest.attained) {
    ;(async () => {
      if (await sleep(Duration.seconds(1), tick)) {
        return
      }
      tick()
    })()
  }
}

const model = new Model(now(), null, {
  verbose: true,
  onUpdate() {
    tick()
  },
})
model.loaded.then(tick)

const ports = new Map()
browser.runtime.onConnect.addListener(port => {
  ports.set(port.name, port)
  port.onMessage.addListener(update)
  port.onDisconnect.addListener(() => ports.delete(port.name))
  tick()
})

function send(name, message) {
  if (!ports.has(name)) {
    return
  }
  ports.get(name).postMessage(message)
}

const idleStateChanged = idleState => update({idleState})
browser.idle.setDetectionInterval(idleDelay.seconds)
browser.idle.onStateChanged.addListener(idleStateChanged)
browser.idle.queryState(idleDelay.seconds).then(idleStateChanged)

let errorCount = 0
function handleError(error) {
  errorCount++
  browser.browserAction.setBadgeText({text: '' + errorCount})
  browser.browserAction.setBadgeBackgroundColor({color: 'red'})
  throw error
}

addEventListener('error', ({error}) => handleError(error))
addEventListener('unhandledrejection', ({reason}) => handleError(reason))
