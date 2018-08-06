import {Duration, Time} from './time.js'

export async function revive(string) {
  string = await string
  if (!string) {
    return null
  }
  return JSON.parse(string, (_, value) => {
    if (value && typeof value == 'object') {
      if ('duration' in value) {
        return new Duration(value.duration)
      }
      if ('sinceEpoch' in value) {
        return new Time(value.sinceEpoch, value.zone)
      }
    }
    return value
  })
}
