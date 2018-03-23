let nextId = 0

export const getOpener =
        ({temporary = false} = {}) => ({newVersion, changeVersion}) => {
    const name = tempory ? `temp${nextId++}` : 'ergometer'
    const db = openDatabase(name, '', name, 5 * 1024 ** 2)
    const {version} = db
    db.changeVersion(version, newVersion, changeVersion)
    return db
}
