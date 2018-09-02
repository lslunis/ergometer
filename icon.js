import {black} from './colors.js'

export function getIcon(
  unscaledSize,
  {monitored, metrics = []},
  {asImageData = false} = {},
) {
  const scale = devicePixelRatio
  const size = unscaledSize * scale
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const c = canvas.getContext('2d')

  metrics.map(m => {
    const tau = 2 * Math.PI
    const mid = size / 2
    const angle = m.ratio
    const fin = 1 / 30
    c.beginPath()
    c.moveTo(mid, mid)
    c.arc(mid, mid, mid, (angle - fin) * tau, (angle + fin) * tau)
    c.closePath()
    c.fillStyle = m.color
    c.fill()
  })

  if (!monitored) {
    const rect = (...args) => c.fillRect(...args.map(i => (i / 16) * size))
    c.fillStyle = black
    rect(4, 4, 3, 8)
    rect(9, 4, 3, 8)
  }

  let result = canvas
  if (asImageData) {
    result = c.getImageData(0, 0, size, size)
  }
  return result
}
