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
  if (!monitored) {
    const rect = (...args) => c.fillRect(...args.map(i => (i / 16) * size))
    c.fillStyle = black
    rect(4, 4, 3, 8)
    rect(9, 4, 3, 8)
  }
  metrics.map((m, i) => {
    const startAngle = -0.5 * Math.PI
    const endAngle = m.value.dividedBy(m.target) * 2 * Math.PI + startAngle
    const center = size / 2
    const radius = (size / 2) * (1 - 0.25 * i)
    c.beginPath()
    c.arc(center, center, radius, startAngle, endAngle)
    c.strokeStyle = m.color
    c.stroke()
  })
  let result = canvas
  if (asImageData) {
    result = c.getImageData(0, 0, size, size)
  }
  return result
}
