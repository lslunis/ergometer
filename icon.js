import {black} from './colors.js'

export function getIcon(
  unscaledSize,
  {monitored, metrics = []},
  {asImageData = false} = {},
) {
  const scale = devicePixelRatio
  const size = unscaledSize * scale
  const mid = size / 2
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const c = canvas.getContext('2d')

  const cone = (radius, start, end, color) => {
    const tau = 2 * Math.PI
    c.beginPath()
    c.moveTo(mid, mid)
    c.arc(mid, mid, radius, start * tau, end * tau)
    c.closePath()
    c.fillStyle = color
    c.fill()
  }

  metrics.map(m => {
    const angle = m.ratio
    const fin = 1 / 30
    cone(mid, angle - fin - 0.25, angle + fin - 0.25, m.color)
  })

  if (!monitored) {
    cone(mid / 4, 0, 1, black)
  }

  let result = canvas
  if (asImageData) {
    result = c.getImageData(0, 0, size, size)
  }
  return result
}
