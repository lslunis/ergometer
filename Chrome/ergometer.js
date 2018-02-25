'use strict'

const ceilingToFixed = (x, n) =>
    (Math.ceil(x * 10**n) / 10**n).toFixed(n)

const getRandomBytes = n =>
    Array.from(crypto.getRandomValues(new Uint8Array(n)))
        .map(byte => byte.toString(16).padStart(2, '0'))
        .join('')

function getTime() {
    const date = new Date
    return {
        time: Math.round(date.getTime() / 1e3),
        zone: -date.getTimezoneOffset() / 60,
    }
}

const checkErrorUnless = (pred) => () => {
    const error = chrome.runtime.lastError
    if (error && !pred(error.message)) {
        console.error(error)
    }
    return error
}

const checkError = checkErrorUnless(s => false)

function store(area, items) {
    chrome.storage[area].set(items, checkError)
}

function removeHost(key) {
    if (!/[0-9a-f]{16}$/.test(key)) {
        console.error(`Cannot remove host from ${JSON.stringify(key)}`)
        return key
    }
    return key.slice(0, -hostLength)
}

const dateFromTime = (time, zone) =>
    Math.floor((time + (zone - 4) * 3600) / 86400)

function addDurationByDate(durationsByDate, date, delta) {
    const duration = durationsByDate[date] || 0
    durationsByDate[date] = duration + delta
}

class EventLog {
    constructor() {
        this.nextId = null
        this.queuedRecords = []
        chrome.storage.local.get({nextId: 0}, items => {
            this.nextId = checkError() ? 0 : items.nextId
            this.flush(...this.queuedRecords)
            this.queuedRecords = null
        })

        this.time = 0
        this.zone = null
        this.state = null
    }

    isStateRequired(state) {
        switch (this.state) {
            case null:
                return true
            case 'active':
                return state != 'idle'
            default:
                return state != 'active'
        }
    }

    put(data) {
        const {time, zone, state} = data
        let record = [time - this.time]
        const zoneRequired = this.zone != zone

        if (this.isStateRequired(state) || zoneRequired) {
            const stateIndex =
                ['active', 'idle', 'locked', 'exited'].indexOf(state)
            record.push(stateIndex < 0 ? state : stateIndex)
        }

        if (zoneRequired) {
            record.push(zone)
        }

        if (record.length == 1) {
            record = record[0]
        }

        if (this.nextId != null) {
            this.flush(record)
        }
        else {
            this.queuedRecords.push(record)
        }

        Object.assign(this, data)
    }

    flush(...records) {
        const items = {}
        for (const record of records) {
            items[this.nextId++] = record
        }
        items.nextId = this.nextId
        store('local', items)
    }
}

class SummaryLog {
    constructor() {
        this.durationsByDate = {}
        this.host = null
        this.queued = true
        chrome.storage.local.get('host', items => {
            let host = checkError() ? null : items.host
            if (host == null) {
                host = getRandomBytes(hostLength / 2)
                chrome.storage.local.set({host}, checkError)
            }
            this.host = host

            chrome.storage.sync.get(null, items => {
                if (checkError()) {
                    items = {}
                }
                const queuedDates = Object.keys(this.durationsByDate)
                for (const key in items) {
                    if (key.endsWith(this.host)) {
                        this.add(removeHost(key), items[key])
                    }
                }
                this.flush(...queuedDates)
                this.queued = false
            })
        })
    }

    add(date, delta) {
        addDurationByDate(this.durationsByDate, date, delta)
    }

    get(time, zone) {
        return this.durationsByDate[dateFromTime(time, zone)] || 0
    }

    update(time, zone, delta) {
        const date = dateFromTime(time, zone)
        this.add(date, delta)
        if (!this.queued) {
            this.flush(date)
        }
    }

    flush(...dates) {
        const items = {}
        for (const date of dates) {
            items[date + this.host] = this.durationsByDate[date]
        }
        store('sync', items)
    }
}

const maxDelay = 60

function saveMiniSession({time, zone}, delay = 0) {
    if (miniSessionStart != null) {
        const delta = time - miniSessionStart
        if (delta < 0 || delta >= delay) {
            summaryLog.update(time, zone, delta)
            miniSessionStart = time
        }
    }
}

function setBadge(text = '', color = '') {
    if (typeof text != 'string') {
        text = ceilingToFixed(text, 1)
    }
    chrome.browserAction.setBadgeText({text})

    if (color) {
        chrome.browserAction.setBadgeBackgroundColor({color})
    }
}

function setIcon(summary) {
    const scale = devicePixelRatio
    const size = 16 * scale
    const c = document.createElement('canvas').getContext('2d')
    c.textBaseline = 'top'
    c.textAlign = 'center'
    c.fillText(summary, size / 2, 0)
    chrome.browserAction.setIcon(
        {imageData: c.getImageData(0, 0, size, size)}, checkError)
}

function flash(color, value) {
    chrome.windows.create({
        url: `flash.html${color},${value}`, type: 'popup', focused: true,
        top: 0, left: 0, width: 3e3, height: 2e3,
    }, win => setTimeout(() =>
        chrome.windows.remove(
            win.id,
            checkErrorUnless(s => s == `No window with id: ${win.id}.`)),
    500))
}

function resume({time, zone}, state = '') {
    const resuming = !['exited', 'suspended'].includes(state) && tickTime != null && tickTime.time + 5 < time
    if (resuming) {
        stateChanged('suspended', tickTime)
        chrome.idle.queryState(idleDelay, stateChanged)
    }
    return resuming
}

function tick({time, zone} = getTime(), state = '') {
    if (resume(state)) {
        return
    }
    const {sessionLimit, restLimit} = settings
    const minutesSince = start => (time - start) / 60
    const restSpent = minutesSince(restStart)
    const restRemaining = restLimit - restSpent
    const becameRested = !active && restRemaining <= 0 && sessionStart != null

    if (active) {
        saveMiniSession({time, zone}, maxDelay)
    }
    else if (restSpent >= 1) {
        saveMiniSession({time: restStart, zone})
        miniSessionStart = null
    }

    if (becameRested) {
        clearInterval(tickLoop)
        tickLoop = null
        sessionStart = null
    }

    const summary = ceilingToFixed(summaryLog.get(time, zone) / 3600, 1)
    if (summary != lastSummary) {
        setIcon(summary)
    }

    store('local',
        {tickTime: {time, zone}, sessionStart, miniSessionStart, restStart})

    if (!drawable) {
        setBadge()
        return
    }

    let exhausted = false
    if (sessionStart == null) {
        setBadge(sessionLimit, blue)
    }
    else {
        const sessionSpent = minutesSince(sessionStart)
        const sessionRemaining = sessionLimit - sessionSpent
        exhausted = sessionRemaining <= 0
        const activeEfficiency =
            (sessionLimit - restSpent) / (restLimit + restSpent)
        const idleEfficiency = (sessionSpent - restSpent) / restLimit

        if (active && exhausted) {
            setBadge(Math.abs(sessionRemaining), red)
        }
        else if (!exhausted && (active || activeEfficiency > idleEfficiency)) {
            setBadge(sessionRemaining, blue)
        }
        else {
            setBadge(restRemaining, gray)
        }
    }

    if (active && exhausted && lastWarned + idleDelay + 3 <= time) {
        flash(red, summary)
        lastWarned = time
    }

    if (becameRested) {
        flash(blue, summary)
    }
}

function stateChanged(state, {time, zone} = getTime()) {
    if (resume(state)) {
        return
    }
    active = state == 'active'
    eventLog.put({time, zone, state})
    const stateStart = state == 'idle' ? time - idleDelay : time

    if (active && miniSessionStart == null) {
        miniSessionStart = stateStart
    }

    if (active && sessionStart == null) {
        sessionStart = stateStart
    }

    if (active) {
        restStart = null
    }
    else if (restStart == null) {
        restStart = stateStart
    }

    if (sessionStart != null && !tickLoop) {
        tickLoop = setInterval(tick, 1e3)
    }

    tick({time, zone}, state)
}

function getNewValues(changes) {
    const newValues = {}
    for (const key in changes) {
        newValues[key] = changes[key].newValue
    }
    return newValues
}

function updateSettings(newSettings) {
    for (const key in newSettings) {
        if (settings.hasOwnProperty(key)) {
            settings[key] = newSettings[key]
        }
    }
}

function setSessionLimit(n) {
    store('sync', {sessionLimit: n})
}

const matchIso = t => new Date(t).toISOString().match(/^(\+0)?(.*)T(.*)\./)

const formatDate = date => matchIso(date * 86400e3)[2]

const formatDuration = duration => matchIso(duration * 1e3)[3]

function printSummary() {
    chrome.storage.sync.get(null, items => {
        if (checkError()) {
            return
        }

        let minDate = Infinity
        let maxDate = -Infinity
        const durationsByDate = {}
        for (const key in items) {
            if (key.length > hostLength) {
                const date = removeHost(key)
                minDate = Math.min(minDate, date)
                maxDate = Math.max(maxDate, date)
                addDurationByDate(durationsByDate, date, items[key])
            }
        }

        const lines = [
            `${formatDate(minDate)} through ${formatDate(maxDate)}:`,
            '',
        ]
        for (let date = minDate; date <= maxDate; ++date) {
            lines.push(date in durationsByDate
                ? formatDuration(durationsByDate[date])
                : '')
        }
        console.log(lines.join('\n'))
    })
}

const eventLog = new EventLog
const summaryLog = new SummaryLog
const hostLength = 32
const idleDelay = 15
const red = '#F44336'
const blue = '#2196F3'
const gray = '#757575'
const settings = {sessionLimit: 15, restLimit: 5}
const initialState = {
    tickTime: null,
    sessionStart: null,
    miniSessionStart: null,
    restStart: 0,
}
let tickLoop = null
let drawable = true
let lastSummary = ''
let lastWarned = 0
let active = false
let tickTime
let sessionStart
let miniSessionStart
let restStart

chrome.storage.local.get(initialState, items => {
    ;({tickTime, sessionStart, miniSessionStart, restStart} =
            checkError() ? initialState : items)

    if (tickTime != null) {
        stateChanged('exited', tickTime)
    }

    chrome.browserAction.onClicked.addListener(() => {
        drawable = !drawable
        tick()
    })

    chrome.idle.setDetectionInterval(idleDelay)
    chrome.idle.onStateChanged.addListener(stateChanged)
    chrome.idle.queryState(idleDelay, stateChanged)
})

chrome.storage.sync.get(Object.assign({}, settings), items => {
    updateSettings(checkError() ? {} : items)
})

chrome.storage.onChanged.addListener((changes, area) => {
    if (area == 'sync') {
        updateSettings(getNewValues(changes))
    }
})
