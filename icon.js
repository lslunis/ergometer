import {black} from './colors.js'

export function getIcon(size, {monitored}, {asImageData = false} = {}) {
  const scale = devicePixelRatio
  const c = document.createElement('canvas').getContext('2d')
  if (!monitored) {
    const rect = (...args) => c.fillRect(...args.map(i => i * scale))
    c.fillStyle = black
    rect(4, 4, 3, 8)
    rect(9, 4, 3, 8)
  }
  let result = c
  if (asImageData) {
    const pixelSize = size * scale
    result = c.getImageData(0, 0, pixelSize, pixelSize)
  }
  return result
}
