import express from 'express'

const app = express()
app.use(express.static('.'))
app.listen(1111, 'localhost')
