import AppKit
import ApplicationServices
import Cocoa
import CoreGraphics

func any(bools: [Bool]) -> Bool {
    return !bools.filter { $0 }.isEmpty
}

func systemClock() -> Double {
    return NSDate().timeIntervalSince1970
}

func parentDir(path: String) -> String {
    return path.stringByDeletingLastPathComponent
}

class File {
    
    func json() -> JSON {
        return nil
    }
    
    func write(data: String) -> Bool {
        return true
    }
    
    func move(dir: String) -> Bool {
        return true
    }
}

class SystemFile: File {
    
    var path: String
    let mode: String
    let errorLog: ErrorLog
    
    init(path: String, mode: String, errorLog: ErrorLog) {
        self.path = path
        self.mode = mode
        self.errorLog = errorLog
    }

    func makeDir(dir: String) -> Bool {
        var e : NSError?
        let r = NSFileManager.defaultManager().createDirectoryAtPath(dir, withIntermediateDirectories: true, attributes: nil, error: &e)
        if !r {
            errorLog.warn("Couldn't mkdir <\(dir)>", with: e)
        }
        return r
    }

    override func json() -> JSON {
        if let s = NSFileManager.defaultManager().contentsAtPath(path) {
            return JSON(data: s)
        }
        return nil
    }
    
    override func write(data: String) -> Bool {
        if !makeDir(parentDir(path)) {
            return false
        }
        let f = fopen(path, mode)
        if f == nil {
            return errorLog.warn("Couldn't open <\(path)>", withErrno: true)
        }
        if fputs(data, f) == EOF {
            return errorLog.warn("Couldn't write to <\(path)>", withErrno: true)
        }
        if fclose(f) == EOF {
            return errorLog.warn("Couldn't close <\(path)>", withErrno: true)
        }
        return true
    }
    
    override func move(dir: String) -> Bool {
        if !makeDir(dir) {
            return false
        }
        let dest = "/".join([dir, path.lastPathComponent])
        if rename(path, dest) != 0 {
            return errorLog.warn("Couldn't rename <\(path)> to <\(dest)>", withErrno: true)
        }
        path = dest
        return true
    }
}

func makeSystemFile(path: String?, mode: String, errorLog: ErrorLog) -> File {
    return path == nil ? File() : SystemFile(path: path!, mode: mode, errorLog: errorLog)
}

func listDir(dir: String, errorLog: ErrorLog) -> [File] {
    var e: NSError?
    if let files = NSFileManager.defaultManager().contentsOfDirectoryAtPath(dir, error: &e) {
        return files.map { SystemFile(path: "\(dir)/\($0)", mode: "w", errorLog: errorLog) }
    }
    return [File]()
}

func formatDate(date: NSDate) -> String {
    let formatter = NSDateFormatter()
    formatter.dateFormat = "yyyy-MM-dd' 'HH:mm:ss' 'ZZZZZ"
    return formatter.stringFromDate(date)
}

class ErrorLog {
    
    var count = 0
    let root: String?
    let logFile: File?
    
    init(root: String?) {
        if root != nil {
            logFile = SystemFile(path: "\(root!)/error.log", mode: "a", errorLog: ErrorLog(root: nil))
        }
    }
    
    func warn(s: String, withErrno: Bool = false, level: String = "warn") -> Bool {
        if logFile == nil {
            return false
        }
        
        if level == "warn" {
            ++count
        }
        logFile!.write("[\(formatDate(NSDate()))][\(level)] \(s)\n")
        
        return false
    }
    
    func info(s: String) -> Bool {
        return warn(s, withErrno: false, level: "info")
    }
    
    func warn(s: String, with: NSError?) -> Bool {
         return warn(s + (with != nil ? ": " + with!.localizedDescription : ""))
    }
}

enum Action {
    case Key(Int), Meta(Int), Click, Ignored
}

func makeAction(e: NSEvent!) -> Action {
    var t = e.type
    switch t {
    case .KeyDown, .FlagsChanged:
        let flags = e.modifierFlags
        let masks : [NSEventModifierFlags] =
            [.ShiftKeyMask, .ControlKeyMask, .AlternateKeyMask, .CommandKeyMask]
        let i = masks.map { flags.rawValue & $0.rawValue != 0 ? 1 : 0 }.reduce(0, combine: +)
        return t == .KeyDown ? Action.Key(i) : Action.Meta(i)
    case .LeftMouseDown, .RightMouseDown, .OtherMouseDown:
        return Action.Click
    default:
        return Action.Ignored
    }
}

func has(x: Double?) -> Bool {
    return (x ?? 0) != 0
}

func red(s: String) -> NSAttributedString {
    let style = [NSForegroundColorAttributeName: NSColor.redColor()]
    return NSAttributedString(string: s, attributes: style)
}

func redIfNegative(x: Double) -> NSAttributedString {
    let s = "\(Int(round(x)))"
    return x < 0 ? red(s) : NSAttributedString(string: s)
}

class Meter {
    
    let app: App
    let name: String
    var actionCost = 0.0
    var timeCosts = [String:Double]()
    var firstActed: Double?
    var actionLimit: Double?
    var timeLimits = [String:Double]()
    var restTime = 0.0
    
    init(app: App, name: String) {
        self.app = app
        self.name = name
    }
    
    func add(x: Double, now: Double) {
        actionCost += x
        firstActed = firstActed ?? now
    }
    
    func rest(lastActed: Double, now: Double) -> Double {
        let restLeft = lastActed + restTime - now
        let restNeeded = actionCost != 0 || firstActed != nil
        if has(restTime) && restLeft <= 0 && restNeeded {
            app.mayGo = true
            app.reset(self)
        }
        return restLeft
    }
    
    func currentTimeCost(lastActed: Double) -> Double {
        return firstActed != nil ? lastActed - firstActed! : 0
    }
    
    func stat (inout statuses: [Double], cost: Double?, limit: Double?) {
        if let n = limit {
            let k = cost ?? 0
            statuses.append(n == 0 ? k : n - k)
        }
    }

    func status(namedMeters: [String:Meter], lastActed: Double) -> [Double] {
        var statuses = [Double]()
        stat(&statuses, cost: actionCost, limit: actionLimit)
        for (name, limit) in timeLimits {
            stat(&statuses, cost: (timeCosts[name] ?? 0) + (namedMeters[name]?.currentTimeCost(lastActed) ?? 0), limit: limit)
        }
        return statuses
    }
    
    func expire() {
        if !has(restTime) {
            app.reset(self)
        }
    }
}

protocol MeterData {
    var name: String { get }
    func copyTo(m: Meter)
}

class MeterConf: MeterData {
    
    let name: String
    let actionLimit: Double?
    let timeLimits: [String:Double]
    let restTime: Double?
    
    init(name: String, actionLimit: Double?, timeLimits: [String:Double], restTime: Double?) {
        self.name = name
        self.actionLimit = actionLimit
        self.timeLimits = timeLimits
        self.restTime = restTime
    }
    
    func copyTo(m: Meter) {
        m.actionLimit = actionLimit
        m.timeLimits = timeLimits
        m.restTime = restTime ?? 0
    }
}

func parseMeterConf(j: JSON) -> MeterConf? {
    if let n = j["name"].string {
        var timeLimits = [String:Double]()
        for (key: String, subJson: JSON) in j["timeLimits"].dictionary ?? [String:JSON]() {
            timeLimits[key] = subJson.doubleValue
        }
        return MeterConf(name: n, actionLimit: j["actionLimit"].double, timeLimits: timeLimits, restTime: j["restTime"].double)
    }
    return nil
}

class MeterState: MeterData {
    
    let name: String
    let actionCost: Double
    let firstActed: Double?
    let timeCosts: [String:Double]
    
    init(name: String, actionCost: Double, firstActed: Double?, timeCosts: [String:Double]) {
        self.name = name
        self.actionCost = actionCost
        self.firstActed = firstActed
        self.timeCosts = timeCosts
    }
    
    func copyTo(m: Meter) {
        m.actionCost = actionCost
        m.firstActed = firstActed
        m.timeCosts = timeCosts
    }
}

func parseMeterState(j: JSON) -> MeterState? {
    if let n = j["name"].string {
        if let ac = j["actionCost"].double {
            if let tc = j["timeCosts"].dictionary {
                var timeCosts = [String:Double]()
                for (key: String, subJson: JSON) in tc {
                    timeCosts[key] = subJson.doubleValue
                }
                return MeterState(name: n, actionCost: ac, firstActed: j["firstActed"].double, timeCosts: timeCosts)
            }
        }
    }
    return nil
}

class App {

    // Serialized state
    var lastActed = 0.0
    var lastExpired = 0.0
    var activationCost = 0.0
    var meters = [Meter]()
    
    // Potential Config
    var fadeTime : Float = 3.0
    var fadeValue : CGDisplayBlendFraction = 0.8
    var stopFade: (t: Float, a: Float, r: Float, g: Float, b: Float) = (t: 5, a: 0.9, r: 1, g: 0, b: 0)
    var goFade: (t: Float, a: Float, r: Float, g: Float, b: Float) = (t: 1, a: 0.2, r: 0, g: 0, b: 1)
    let restDelay = 5.0
    let activationLimit = 10.0
    let activationDelay = 30.0
    
    // Volatile State
    let clock: (() -> Double)
    let errorLog: ErrorLog
    let stopDir: String
    let state: File
    let conf: File
    var metaDowns = [Int]()
    var fadeUntil = 0.0
    var mayGo = false
    var updated = false

    func setMeters(newList: [MeterData]) {
        var olds = [String:Meter]()
        for m in meters {
            olds[m.name] = m
        }
        var news = [String:MeterData]()
        for m in newList {
            news[m.name] = m
        }
        var keys = [String:Int]()
        for k in olds.keys {
            keys[k] = 1
        }
        for k in news.keys {
            keys[k] = 1
        }
        for k in keys.keys {
            if let n = news[k] {
                if olds[k] == nil {
                    olds[k] = Meter(app: self, name: k)
                }
                n.copyTo(olds[k]!)
            }
            else {
                olds.removeValueForKey(k)
            }
        }
        meters = newList.map { olds[$0.name]! }
    }
    
    func parseMeters(y: JSON, isState: Bool) -> [MeterData]? {
        let yms = y["meters"].array
        if yms == nil {
            return nil
        }
        var meters = [MeterData]()
        for ym in yms! {
            if isState {
                if let m = parseMeterState(ym) {
                    meters.append(m)
                }
                else {
                    return nil
                }
            }
            else {
                if let m = parseMeterConf(ym) {
                    meters.append(m)
                }
                else {
                    return nil
                }
            }
        }
        return meters
    }
    
    func storeState() {
        if updated {
            let m = ",".join(map(meters) {
                let firstActed = $0.firstActed != nil ? "\($0.firstActed!)" : "null"
                let timeCosts = ",".join(map($0.timeCosts) {
                    "\"\($0.0)\":\($0.1)"
                })
                return "{\"name\":\"\($0.name)\",\"actionCost\":\($0.actionCost),\"firstActed\":\(firstActed),\"timeCosts\":{\(timeCosts)}}"
                })
            let data = "{\"meters\":[\(m)],\"lastActed\":\(lastActed),\"lastExpired\":\(lastExpired)}"
            updated = !state.write(data)
        }
    }

    func loadState() -> Bool {
        let y = state.json()
        let m = parseMeters(y, isState: true)
        let r = m != nil
        if r {
            setMeters(m!)
        }
        lastActed = y["lastActed"].double!
        lastExpired = y["lastExpired"].double!
        return r
    }

    func configure() {
        let j = conf.json()
        if let m = parseMeters(j, isState: false) {
            setMeters(m)
        }
    }

    init(clock: (() -> Double), makeFile: ((path: String?, mode: String, errorLog: ErrorLog) -> File), root: String, errorLog: ErrorLog) {
        self.clock = clock
        self.errorLog = errorLog
        conf = makeFile(path: "\(root)/conf.json", mode: "w", errorLog: errorLog)
        var done = false
        stopDir = "\(root)/stop"
        let runDir = "\(root)/run"
        let states = listDir(stopDir, errorLog)
        if states.count > 0 {
            state = states[0]
            if state.move(runDir) {
                if loadState() {
                    done = true
                }
                else {
                    state.move(stopDir)
                }
            }
        }
        if done {
            state = states[0]
        }
        else {
            let s = NSUUID().UUIDString
            let id = s.substringFromIndex(advance(s.endIndex, -12))
            var statePath = "\(runDir)/\(id).txt"
            state = makeFile(path: statePath, mode: "w", errorLog: errorLog)
        }
        configure()
    }
    
    func meta(i: Int) -> Double {
        let d = i - metaDowns.count
        if d > 0 {
            metaDowns += Array(count: d, repeatedValue: 0)
        }
        if i < 1 {
            return 0
        }
        if metaDowns[i - 1] > 0 {
            --metaDowns[i - 1]
            return 0
        }
        if i >= 2 {
            ++metaDowns[i - 2]
        }
        return 1
    }
    
    func cost(a: Action) -> Double {
        switch a {
        case .Meta(let i):
            return meta(i)
        case .Key, .Click:
            return 1
        case .Ignored:
            return 0
        }
    }

    func act(a: Action) {
        let now = clock()
        var x = cost(a)
        if !has(x) {
            return
        }
        if now - lastActed > activationDelay {
            let totalCost = activationCost + x
            if totalCost <= activationLimit {
                activationCost = totalCost
                return
            }
            x = totalCost
            activationCost = 0
        }
        lastActed = now
        updated = true
        map(meters) { $0.add(x, now: now) }
    }
    
    func fade(now: Double, go: Bool) {
        if now < fadeUntil {
            return
        }
        let f = go ? goFade : stopFade
        let success = CGError(kCGErrorSuccess.value)
        var token = CGDisplayFadeReservationToken(kCGDisplayFadeReservationInvalidToken)
        var e = CGAcquireDisplayFadeReservation(f.t, &token)
        if e != success {
            return
        }
        e = CGDisplayFade(token, 0, 0, f.a, f.r, f.g, f.b, 0)
        if e != success {
            errorLog.warn("CGError returned \(e.value)")
        }
        fadeUntil = now + Double(f.t)
    }
    
    func tick() -> NSAttributedString {
        let now = clock()
        let resting = now - lastActed > restDelay
        let assumedLastActed = resting ? lastActed : now
        let errorStatusStringGroup = errorLog.count > 0 ? [red("\(errorLog.count)")] : []
        
        expire(now)
        let restStatuses = map(meters) { $0.rest(assumedLastActed, now: now) }.filter { $0 > 0 }
        let restStatusStringGroup = resting && !restStatuses.isEmpty ? [redIfNegative(minElement(restStatuses))] : []
        
        var namedMeters = [String:Meter]()
        for m in meters {
            namedMeters[m.name] = m
        }
        let meterStatusGroups = map(meters) { $0.status(namedMeters, lastActed: assumedLastActed) }
        let shouldStop = any(meterStatusGroups.map { any($0.map { $0 < 0 }) })
        let meterStatusStringGroups = meterStatusGroups.map({ $0.map(redIfNegative) })
        
        let statusBuffer = NSMutableAttributedString()
        let statusStringGroups = ([errorStatusStringGroup] + [restStatusStringGroup] + meterStatusStringGroups).filter { !$0.isEmpty }
        for (groupIndex, statusStringGroup) in enumerate(statusStringGroups) {
            if groupIndex > 0 {
                statusBuffer.appendAttributedString(NSAttributedString(string: "  ·  "))
            }
            for (i, s) in enumerate(statusStringGroup) {
                if i > 0 {
                    statusBuffer.appendAttributedString(NSAttributedString(string: "  "))
                }
                statusBuffer.appendAttributedString(s)
            }
        }
        
        if shouldStop && !resting {
            fade(now, go: false)
        }
        if mayGo {
            mayGo = false
            if !shouldStop {
                fade(now, go: true)
            }
        }
        
        storeState()

        return statusBuffer
    }
    
    func expire(now: Double) {
        let calendar = NSCalendar.currentCalendar()
        let flags: NSCalendarUnit = .DayCalendarUnit | .MonthCalendarUnit | .YearCalendarUnit | .HourCalendarUnit
        var expireDate = NSDate(timeIntervalSince1970: now)
        let components = calendar.components(flags, fromDate: expireDate)
        let expireHour = 4
        if components.hour < expireHour {
            expireDate = calendar.dateByAddingUnit(.DayCalendarUnit, value: -1, toDate: expireDate, options: NSCalendarOptions())!
        }
        expireDate = calendar.dateBySettingHour(expireHour, minute: 0, second: 0, ofDate: expireDate, options: NSCalendarOptions())!
        
        let lastExpirable = expireDate.timeIntervalSince1970
        if lastExpired < lastExpirable {
            lastExpired = now
            map(meters) { $0.expire() }
        }
    }
    
    func reset(source: Meter) {
        let n = source.name
        let t = source.currentTimeCost(lastActed)
        for m in meters {
            let tt = m.timeCosts[n] ?? 0
            m.timeCosts[n] = tt + t
        }
        source.actionCost = 0
        source.firstActed = nil
        source.timeCosts = [:]
        updated = true
    }
    
    func terminate() {
        tick()
        state.move(stopDir)
    }
}

@NSApplicationMain
class AppDelegate: NSObject, NSApplicationDelegate {
    
    var item: NSStatusItem?
    var app: App?
    
    func act(e: NSEvent!) {
        app?.act(makeAction(e))
    }
    
    func tick() {
        if let s = app?.tick() {
            item!.button!.attributedTitle = s
        }
    }
    
    func applicationDidFinishLaunching(aNotification: NSNotification) {
        item = NSStatusBar.systemStatusBar().statusItemWithLength(/* NSVariableStatusItemLength */ -1)
        let prompt: String = kAXTrustedCheckOptionPrompt.takeUnretainedValue()
        let trusted = AXIsProcessTrustedWithOptions([prompt: true]) != 0
        if item == nil || !trusted {
            NSApplication.sharedApplication().terminate(nil)
            return
        }
        
        let root = "~/Library/Application Support/Ergometer".stringByStandardizingPath
        let errorLog = ErrorLog(root: root)
        app = App(clock: systemClock, makeFile: makeSystemFile, root: root, errorLog: errorLog)
        NSTimer.scheduledTimerWithTimeInterval(1, target: self, selector: "tick", userInfo: nil, repeats: true)
        let mask : NSEventMask =
            .KeyDownMask |
            .FlagsChangedMask |
            .LeftMouseDownMask |
            .RightMouseDownMask |
            .OtherMouseDownMask
        NSEvent.addGlobalMonitorForEventsMatchingMask(mask, handler: act)
    }

    func applicationWillTerminate(aNotification: NSNotification) {
        app?.terminate()
    }
}
