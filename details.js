import {black, white} from './colors.js'
import {revive} from './reviver.js'
import {Duration, Time} from './time.js'
import {assert, map, range, removeChildren, zip} from './util.js'

function setColors({style}, color, background) {
  if (color && style.color != color) {
    style.color = color
  }
  if (background && style.background != background) {
    style.background = background
  }
}

setColors(document.body, black, white)

const port = browser.runtime.connect(
  null,
  {name: 'details'},
)
port.onMessage.addListener(message =>
  requestAnimationFrame(async () => draw(await revive(message))),
)

function update(event) {
  port.postMessage(JSON.stringify(event))
}

class Label {
  constructor(name) {
    this.name = name
  }

  create() {
    const node = document.createElement('label')
    node.htmlFor = this.name
    node.textContent = this.name.replace(/^./, c => c.toUpperCase()) + ':'
    return node
  }

  update() {}
}

class Checkbox {
  constructor(name, value) {
    this.name = name
    this.value = value
  }

  create() {
    const node = document.createElement('input')
    node.id = this.name
    node.type = 'checkbox'
    node.addEventListener('change', () => update({monitored: node.checked}))
    this.update(node)
    return node
  }

  update(node) {
    if (node.checked != this.value) {
      node.checked = this.value
    }
  }
}

class TextField {
  constructor(name) {
    this.name = name
  }

  create() {
    const node = document.createElement('input')
    node.id = this.name
    node.type = 'text'
    node.addEventListener('change', () => {
      let target
      const match = node.value.match(/^\d*([.:]?)\d*$/)
      if (match) {
        const [string, separator] = match
        if (separator == ':') {
          target = Duration.parse(string)
        } else {
          const hours = +string
          if (hours) {
            target = Duration.make({hours}).round('minutes')
          }
        }
      }
      if (target && target.strictlyBetween(0, {hours: 1000})) {
        node.setCustomValidity('')
        node.value = ''
        update({name: this.name, target})
      } else {
        node.setCustomValidity('h:mm')
      }
    })

    return node
  }

  update() {}
}

class Text {
  constructor(value, color, background) {
    this.value = value
    this.color = color
    this.background = background
  }

  create() {
    const node = document.createElement('div')
    this.update(node)
    return node
  }

  update(node) {
    if (node.textContent != this.value) {
      node.textContent = this.value
    }
    setColors(node, this.color, this.background)
  }
}

function getHistoryRow(...cells) {
  return cells.map(c => new Text(c))
}

function* getHistoryCells({firstWeek, dailyValues}) {
  if (!Number.isFinite(firstWeek)) {
    return
  }

  yield* getHistoryRow(...'Week All Mon Tue Wed Thu Fri Sat Sun'.split(' '))
  const today = Math.floor(Duration.milliseconds(Date.now()).days)
  for (let week = firstWeek; week <= today; week += 7) {
    const header = new Time(Duration.days(week)).toString().slice(0, 10)
    const days = [
      ...map(range(week, week + 7), d => dailyValues[d] || Duration.make(0)),
    ]
    const sum = Duration.sum(days).toString('h:mm')
    yield* getHistoryRow(header, sum, ...days.map(d => d.toString('h:mm')))
  }
}

function* getMetricCells({monitored, metrics}) {
  yield* [new Label('monitored'), new Checkbox('monitored', monitored)]
  for (const {name, value, color, target} of Object.values(metrics)) {
    const format = 'h:mm:ss'
    yield* [
      new Label(name),
      new TextField(name),
      new Text(value.toString(format), color),
      new Text(target.toString(format)),
    ]
  }
}

let firstDraw = true
let priorFirstWeek

function draw(message) {
  const drawGrid = (id, getCells) => {
    const grid = document.getElementById(id)
    for (const [cell, node] of zip(getCells(message), grid.children)) {
      assert(cell)
      if (node) {
        cell.update(node)
      } else {
        grid.appendChild(cell.create())
      }
    }
  }

  const {firstWeek} = message
  if (priorFirstWeek && firstWeek < priorFirstWeek) {
    removeChildren(document.getElementById('history'))
  }
  priorFirstWeek = firstWeek

  drawGrid('history', getHistoryCells)
  drawGrid('metrics', getMetricCells)

  if (firstDraw) {
    scrollTo(0, document.body.scrollHeight)
    firstDraw = false
  }
}
