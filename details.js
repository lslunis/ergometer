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
