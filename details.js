import {black, white} from './colors.js'
import {revive} from './reviver.js'
import {assert, zip} from './util.js'

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
  port.postMessage(event)
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
      /* FIXME
      Target on change
      \d*([.:]?)\d*
      null if falsy, otherwise duration hours and round to minutes
      or duration parse
      not null and strictly between zero and 1000 hours, clear error message,
        clear value, update name, target
      update({name: this.name, target})
      otherwise, element set custom validity error message: h:mm
      */
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

function* getMetricCells({monitored, metrics}) {
  yield* [new Label('monitored'), new Checkbox('monitored', monitored)]
  for (const {name, value, color, target} of Object.values(metrics)) {
    yield* [
      new Label(name),
      new TextField(name),
      new Text(value.format('seconds'), color),
      new Text(target.format()),
    ]
  }
}

function draw(message) {
  const metricGrid = document.getElementById('metrics')
  const metricNodes = metricGrid.children
  for (const [cell, node] of zip(getMetricCells(message), metricNodes)) {
    assert(cell)
    if (node) {
      cell.update(node)
    } else {
      metricGrid.appendChild(cell.create())
    }
  }
}
