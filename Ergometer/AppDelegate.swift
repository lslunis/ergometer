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

class File {
    
    func put(data: String) -> Bool {
        return true
    }
    
    func move(pattern: String, template: String) -> Bool {
        return true
    }
}

class SystemFile: File {
    
    let path: String
    let mode: String
    let errorLog: ErrorLog
    
    init(path: String, mode: String, errorLog: ErrorLog) {
        self.path = path
        self.mode = mode
        self.errorLog = errorLog
    }

    override func put(data: String) -> Bool {
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
    
    override func move(pattern: String, template: String) -> Bool {
        var e: NSError?
        let r = NSRegularExpression(pattern: pattern, options: NSRegularExpressionOptions(0), error: &e)
        if r == nil {
            return errorLog.warn("Invalid pattern <\(pattern)>")
        }
        let s = r!.stringByReplacingMatchesInString(path, options: NSMatchingOptions(0), range: NSMakeRange(0, path.utf16Count), withTemplate: template)
        if rename(path, s) != 0 {
            return errorLog.warn("Couldn't rename <\(path)> to <\(s)>", withErrno: true)
        }
        return true
    }
}

func makeSystemFile(path: String?, mode: String, errorLog: ErrorLog) -> File {
    return path == nil ? File() : SystemFile(path: path!, mode: mode, errorLog: errorLog)
}

class ErrorLog {
    
    var count = 0
    
    func warn(s: String, withErrno: Bool = false) -> Bool {
        return false
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

func redUnlessPositive(x: Double) -> NSAttributedString {
    let s = "\(Int(round(x)))"
    return x > 0 ? NSAttributedString(string: s) : red(s)
}

class Meter {
    
    let app: App
    let name: String
    var actionCost = 0.0
    var actionLimit: Double?
    var firstActed: Double?
    var timeLimit: Double?
    var restTime: Double = 0
    
    init(app: App, name: String) {
        self.app = app
        self.name = name
    }
    
    func add(x: Double, now: Double) {
        actionCost += x
        if has(timeLimit) {
            firstActed = firstActed ?? now
        }
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
    
    func status(lastActed: Double) -> Double {
        let timed = has(timeLimit)
        let activeElapsed = firstActed != nil ? lastActed - firstActed! : 0
        if has(actionLimit) {
            var value = actionLimit! - actionCost
            if timed {
                var timeCost = activeElapsed / timeLimit! * actionLimit!
                value -= timeCost
            }
            return value
        }
        if timed {
            return timeLimit! - activeElapsed
        }
        return actionCost
    }
    
    func expire() {
        if has(restTime) {
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
    let timeLimit: Double?
    let restTime: Double?
    
    init(name: String, actionLimit: Double?, timeLimit: Double?, restTime: Double?) {
        self.name = name
        self.actionLimit = actionLimit
        self.timeLimit = timeLimit
        self.restTime = restTime
    }
    
    func copyTo(m: Meter) {
        m.actionLimit = actionLimit
        m.timeLimit = timeLimit
        m.restTime = restTime ?? 0
    }
}

class MeterState: MeterData {
    
    let name: String
    let actionCost: Double
    let firstActed: Double
    
    init(name: String, actionCost: Double, firstActed: Double) {
        self.name = name
        self.actionCost = actionCost
        self.firstActed = firstActed
    }
    
    func copyTo(m: Meter) {
        m.actionCost = actionCost
        m.firstActed = firstActed
    }
}

class App {
    
    var lastActed = 0.0
    var meters = [Meter]()
    var fadeTime : Float = 3.0
    var fadeValue : CGDisplayBlendFraction = 0.5
    let restDelay = 5.0

    let clock: (() -> Double)
    let errorLog: ErrorLog
    let id: String
    let state: File
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
    
    func storeState() {
        if updated {
            let parts = map(meters) { "\($0.name) \($0.actionCost) \($0.firstActed ?? 0)" } + ["\(lastActed)"]
            let data = ",".join(parts)
            updated = !state.put(data)
        }
    }
    
    func loadState() -> Bool {
        let data = ""
        var parts = split(data) { $0 == "," }.map { split($0) { $0 == " " } }
        lastActed = (parts.removeLast()[0] as NSString).doubleValue
        return true
    }

    func configure() {
        setMeters([MeterConf(name: "s", actionLimit: nil, timeLimit: 45, restTime: 45), MeterConf(name: "m", actionLimit: nil, timeLimit: 420, restTime: 900)])
    }

    init(clock: (() -> Double), makeFile: ((path: String?, mode: String, errorLog: ErrorLog) -> File), root: String?, errorLog: ErrorLog) {
        self.clock = clock
        self.errorLog = errorLog
        let s = NSUUID().UUIDString
        id = s.substringFromIndex(advance(s.endIndex, -12))
        var statePath: String?
        if root != nil {
            statePath = "\(root!)/state/\(id).txt"
        }
        state = makeFile(path: statePath, mode: "w", errorLog: errorLog)
        configure()
        expire()
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
        let x = cost(a)
        if !has(x) {
            return
        }
        lastActed = now
        updated = true
        map(meters) { $0.add(x, now: now) }
    }
    
    func fade(now: Double, go: Bool) {
        if now < fadeUntil {
            return
        }
        let success = CGError(kCGErrorSuccess.value)
        var token = CGDisplayFadeReservationToken(kCGDisplayFadeReservationInvalidToken)
        var e = CGAcquireDisplayFadeReservation(fadeTime, &token)
        if e != success {
            return
        }
        let red: Float = go ? 0 : 1
        let blue: Float = go ? 1 : 0
        e = CGDisplayFade(token, 0, CGDisplayBlendFraction(kCGDisplayBlendNormal), fadeValue, red, 0, blue, 0)
        if e != success {
            errorLog.warn("CGError returned \(e.value)")
        }
        fadeUntil = now + Double(fadeTime)
    }
    
    func tick() -> (ticking: Bool, statusString: NSAttributedString) {
        let now = clock()
        let resting = now - lastActed > restDelay
        let assumedLastActed = resting ? lastActed : now
        let errorStatusStrings = errorLog.count > 0 ? [red("\(errorLog.count)")] : []
        
        let restStatuses = map(meters) { $0.rest(assumedLastActed, now: now) }.filter { $0 > 0 }
        let ticking = !restStatuses.isEmpty
        let restStatusStrings = resting && ticking ? [redUnlessPositive(minElement(restStatuses))] : []
        
        let meterStatuses = map(meters) { $0.status(assumedLastActed) }
        let shouldStop = any(meterStatuses.map { $0 < 0 })
        let meterStatusStrings = meterStatuses.map(redUnlessPositive)
        
        let statusBuffer = NSMutableAttributedString()
        let statusStrings = errorStatusStrings + restStatusStrings + meterStatusStrings
        for (i, s) in enumerate(statusStrings) {
            if i > 0 {
                statusBuffer.appendAttributedString(NSAttributedString(string: "  "))
            }
            statusBuffer.appendAttributedString(s)
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

        return (ticking, statusBuffer)
    }
    
    func expire() {
        map(meters) { $0.expire() }
    }
    
    func reset(m: Meter) {
        m.actionCost = 0
        m.firstActed = nil
        updated = true
    }
}

@NSApplicationMain
class AppDelegate: NSObject, NSApplicationDelegate {
    
    var item: NSStatusItem?
    var app: App?
    var timer: NSTimer?
    
    func act(e: NSEvent!) {
        if app == nil {
            return
        }
        app!.act(makeAction(e))
        if timer == nil {
            timer = NSTimer.scheduledTimerWithTimeInterval(
                1.0, target: self, selector: "tick", userInfo: nil, repeats: true)
        }
    }
    
    func tick() {
        if app == nil {
            return
        }
        let r = app!.tick()
        item!.button!.attributedTitle = r.statusString
        if timer != nil && !r.ticking {
            timer!.invalidate()
            timer = nil
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
        
        let errorLog = ErrorLog()
        var root : String? = "~/Library/Application Support/Ergometer".stringByStandardizingPath
        var e : NSError?
        if !NSFileManager.defaultManager().createDirectoryAtPath(root!, withIntermediateDirectories: true, attributes: nil, error: &e) {
            root = nil
            errorLog.warn("Couldn't create <\(root)>" + (e != nil ? ": " + e!.localizedDescription : ""))
        }
        
        app = App(clock: systemClock, makeFile: makeSystemFile, root: root, errorLog: errorLog)
        tick()
        let mask : NSEventMask =
            .KeyDownMask |
            .FlagsChangedMask |
            .LeftMouseDownMask |
            .RightMouseDownMask |
            .OtherMouseDownMask
        NSEvent.addGlobalMonitorForEventsMatchingMask(mask, handler: act)
    }

    func applicationWillTerminate(aNotification: NSNotification) {
        tick()
    }
}
