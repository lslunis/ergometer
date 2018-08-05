import {black, white} from './colors.js'

{
  const {style} = document.body
  style.color = black
  style.background = white
}

const port = browser.runtime.connect(
  null,
  {name: 'details'},
)
port.onMessage.addListener(message => {
  // todo
})

function update(event) {
  port.postMessage(event)
}
