import {initFirebase} from './config.js'
import {Time} from './time.js'
import {assert, enumerate, getRandomBytes} from './util.js'

export function getSynchronizerInitialState() {
  return {
    outbox: {
      start: 0,
      events: [],
    },
    inboxes: {},
  }
}

function log(message) {
  console.log(`${Time.now()} ${message}`)
}

export class Synchronizer {
  constructor(options) {
    Object.assign(this, options)
    this.initialized = false
    this.email = null
    this.user = null
    this.hosts = new Set()
    this.unlisteners = []
    this.sending = false

    initFirebase()
    firebase.auth().onAuthStateChanged(async firebaseUser => {
      this.setUser(firebaseUser)
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
    if (firebaseUser) {
      const {email, emailVerified} = firebaseUser
      this.email = email
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
      this.email = this.user = null
      log('signed out')
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
    log(`host created as ${host} for user ${user}`)
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
          doc
            .data()
            .hosts.filter(h => h != this.state.host && !this.hosts.has(h))
            .map(h => this.onNewHost(h))
        }),
    )
  }

  onNewHost(host) {
    const {user} = this
    let nextId = this.state.inboxes[host] || 0
    log(`listening for events on user ${user}, host ${host}, id >= ${nextId}`)
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
              if (nextId != doc.id) {
                throw Error(
                  `non-contiguous event; expected ${nextId}, got ${doc.id}`,
                )
              }
              nextId++
              this.state.inboxes[host] = nextId
              this.onEvent(doc)
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
        const message = `events [${start}, ${start + events.length})`
        log(`sending ${message}`)
        const batch = firebase.firestore().batch()

        for (const [id, event] of enumerate(events, start)) {
          const eventRef = firebase
            .firestore()
            .collection('events')
            .doc()

          batch.set(eventRef, {
            ...event,
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
