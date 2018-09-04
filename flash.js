import {getIcon} from './icon.js'
import {revive} from './reviver.js'
import {removeChildren} from './util.js'

const {body} = document
browser.runtime
  .connect(
    null,
    {name: 'flash'},
  )
  .onMessage.addListener(message =>
    requestAnimationFrame(async () => {
      removeChildren(body)
      body.appendChild(getIcon(480, await revive(message)))
    }),
  )
