import {black, white} from './colors.js'
import {assert, zip} from './util.js'

{
  const {style} = document.documentElement
  style.color = black
  style.background = white
}

const port = browser.runtime.connect(
  null,
  {name: 'details'},
)
port.onMessage.addListener(message =>
  requestAnimationFrame(() => draw(message)),
)

function update(event) {
  port.postMessage(event)
}

class Cell {
  update() {}
}

class Label extends Cell {
  constructor(name) {
    super()
    this.name = name
  }

  create() {
    const node = document.createElement('label')
    node.for = this.name
    node.textContent = this.name.replace(/^./, c => c.toUpperCase()) + ':'
    return node
  }
}

function* getMetricCells({monitored, metrics}) {
  yield new Label('monitored')
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
