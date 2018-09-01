const [_, color, value] = location.hash.match(/^#([0-9a-f]{6}),(\d\d?\.\d)$/i)
const {body} = document
body.style.backgroundColor = '#' + color
body.textContent = value
