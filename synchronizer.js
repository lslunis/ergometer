import {initFirebase} from './config.js'
import {Duration, Time} from './time.js'
import {assert, enumerate, getRandomBytes, makeObject} from './util.js'

export function getSynchronizerInitialState() {
  return {
    outbox: {
      start: 0,
      events: [],
    },
    inboxes: {},
  }
}

function declassify(value) {
  if (Array.isArray(value)) {
    return value.map(declassify)
  }
  if (value && typeof value == 'object') {
    return makeObject(Object.entries(value).map(([k, v]) => [k, declassify(v)]))
  }
  return value
}

function classify(value) {
  if (Array.isArray(value)) {
    return value.map(classify)
  }
  if (value && typeof value == 'object') {
    if ('duration' in value) {
      return new Duration(value.duration)
    }
    if ('sinceEpoch' in value) {
      return new Time(classify(value.sinceEpoch), classify(value.zone))
    }
    return makeObject(Object.entries(value).map(([k, v]) => [k, classify(v)]))
  }
  return value
}

function log(message) {
  console.log(`${Time.now()} ${message}`)
}

export class Synchronizer {
  constructor(options) {
    Object.assign(this, options)
    this.initialized = false
    this.authenticated = false
    this.user = null
    this.hosts = new Set()
    this.unlisteners = []
    this.sending = false

    initFirebase()
    firebase.auth().onAuthStateChanged(async firebaseUser => {
      await this.setUser(firebaseUser)
      if (!this.state.host) {
        await this.createHost()
      }
      this.listenForNewHosts()
    })
  }

  setAuthenticated(authenticated) {
    if (authenticated) {
      log('signing in')
      firebase.auth().signInWithPopup(new firebase.auth.GoogleAuthProvider())
    } else {
      this.unlisteners.map(u => u())
      this.unlisteners = []
      log('signing out')
      firebase.auth().signOut()
    }
  }

  async setUser(firebaseUser) {
    this.authenticated = !!firebaseUser
    if (firebaseUser) {
      const {email, emailVerified} = firebaseUser
      log(`signed in as ${email} ${emailVerified ? '' : '(unverified)'}`)

      if (emailVerified) {
        try {
          const aliasDoc = await firebase
            .firestore()
            .collection('aliases')
            .doc(email)
            .get()

          this.user = aliasDoc.exists ? aliasDoc.data().user : null
        } catch (e) {
          this.user = null
          throw e
        }
        log(`user: ${this.user}`)
        this.send()
      } else {
        this.user = null
      }
    } else {
      log('signed out')
      this.user = null
    }
  }

  async createHost() {
    const {user} = this
    if (!user) {
      return
    }

    log(`creating this host for user ${user}`)
    const userDocRef = firebase
      .firestore()
      .collection('users')
      .doc(user)
    const host = getRandomBytes(12)

    await firebase.firestore().runTransaction(async tx => {
      const userDoc = await tx.get(userDocRef)
      assert(userDoc.exists)
      const {hosts = []} = userDoc.data()
      hosts.push(host)
      tx.update(userDocRef, {hosts})
    })
    this.state.host = host
    log(`host ${host} created for user ${user}`)
    this.onStateChanged()
    this.send()
  }

  listenForNewHosts() {
    const {user} = this
    if (!user) {
      return
    }

    log(`listening for new hosts on user ${user}`)
    this.unlisteners.push(
      firebase
        .firestore()
        .collection('users')
        .doc(this.user)
        .onSnapshot(doc => {
          ;(doc.data().hosts || [])
            .filter(h => h != this.state.host && !this.hosts.has(h))
            .map(h => this.onNewHost(h))
        }),
    )
  }

  onNewHost(host) {
    this.hosts.add(host)
    const {user} = this
    const prefix = `user ${user}, host ${host}`
    let nextId = this.state.inboxes[host] || 0
    log(`listening for events on ${prefix}, id >= ${nextId}`)
    this.unlisteners.push(
      firebase
        .firestore()
        .collection('events')
        .where('user', '==', user)
        .where('host', '==', host)
        .where('id', '>=', nextId)
        .orderBy('id')
        .onSnapshot(snapshot =>
          snapshot
            .docChanges()
            .filter(({type}) => type == 'added')
            .map(({doc}) => {
              const event = doc.data()
              const {id} = event
              if (id < nextId) {
                log(`ignoring duplicate ${prefix}, id ${id}`)
                return
              }
              if (id != nextId) {
                throw Error(`expected ${prefix}, id ${nextId}; got ${id}`)
              }
              nextId++
              this.state.inboxes[host] = nextId
              this.onEvent(classify(event))
            }),
        ),
    )
  }

  get nextId() {
    const {start, events} = this.state.outbox
    return start + events.length
  }

  update(event) {
    this.state.outbox.events.push(event)
    this.send()
  }

  async send() {
    if (this.sending || !this.state.host) {
      return
    }
    try {
      this.sending = true

      while (this.user && this.state.outbox.events.length) {
        const batchLimit = 20
        const {start} = this.state.outbox
        const events = this.state.outbox.events.slice(0, batchLimit)
        const message =
          events.length == 1
            ? `event ${start}`
            : `events ${start}-${start + events.length - 1}`
        log(`sending ${message}`)
        const batch = firebase.firestore().batch()

        for (const [id, event] of enumerate(events, start)) {
          const eventRef = firebase
            .firestore()
            .collection('events')
            .doc()

          batch.set(eventRef, {
            ...declassify(event),
            user: this.user,
            host: this.state.host,
            id,
          })
        }

        await batch.commit()
        const deleteCount = events.length
        this.state.outbox.start += deleteCount
        this.state.outbox.events.splice(0, deleteCount)
        log(`sent ${message}`)
        this.onStateChanged()
      }
    } finally {
      this.sending = false
    }
  }
}
