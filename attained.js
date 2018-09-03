let colors = location.hash
  .slice(1)
  .split(',')
  .map(c => `#${c}`)

browser.runtime
  .connect(
    null,
    {name: 'attained'},
  )
  .onMessage.addListener(cs => (colors = JSON.parse(cs)))

function draw() {
  document.body.style.background =
    colors[Math.floor(Math.random() * colors.length)]
}

draw()
setInterval(draw, 250)
