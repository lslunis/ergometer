export const black = '#222' // N1
const gray = '#888' // N5
export const white = '#fff' // N10

const pink = '#fa006c' // 10.0RP-5-20
const red = '#fc003c' // 5.0R-5-20
const orange = '#e53800' // 10.0R-5-18
const teal = '#009d89' // 2.5BG-5-24
const blue = '#008afb' // 10.0B-5-18
const indigo = '#486aff' // 7.5PB-5-20

const metricColors = {
  weekly: [indigo, orange],
  daily: [blue, red],
  session: [teal, pink],
  rest: [black, gray],
}

export function colorize(metrics) {
  Object.entries(metrics).map(([name, metric]) => {
    const index = +metric[name == 'rest' ? 'suggested' : 'attained']
    metric.color = metricColors[name][index]
  })
  return metrics
}
