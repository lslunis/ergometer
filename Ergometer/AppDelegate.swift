import AppKit
import ApplicationServices
import Cocoa
import CoreGraphics

func any(bools: [Bool]) -> Bool {
    return !bools.filter { $0 }.isEmpty
}

func systemClock() -> NSTimeInterval {
    return NSDate().timeIntervalSince1970
}

class Warn {

    func warn(s: String, withErrno: Bool) -> Bool {
        return false
    }
    
    func with(s: String) -> Bool {
        return warn(s, withErrno: false)
    }
    
    func withErrno(s: String) -> Bool {
        return warn(s, withErrno: true)
    }
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
    let warn: Warn
    
    init(path: String, mode: String) {
        self.path = path
        self.mode = mode
        warn = Warn()
    }
    
    override func put(data: String) -> Bool {
        let f = fopen(path, mode)
        fputs(data, f)
        fclose(f)
        return true
    }
    
    override func move(pattern: String, template: String) -> Bool {
        var e: NSError?
        let r = NSRegularExpression(pattern: pattern, options: NSRegularExpressionOptions(0), error: &e)
        if r == nil {
            return warn.with("Invalid pattern <\(pattern)> or template <\(template)>")
        }
        let s = r!.stringByReplacingMatchesInString(path, options: NSMatchingOptions(0), range: NSMakeRange(0, path.utf16Count), withTemplate: template)
        if rename(path, s) != 0 {
            return warn.withErrno("Couldn't rename <\(path)> to <\(s)>")
        }
        return true
    }
}

func makeSystemFile(path: String?, mode: String) -> File {
    return path == nil ? File() : SystemFile(path: path!, mode: mode)
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

let redForeground = [NSForegroundColorAttributeName: NSColor.redColor()]

func format(i: Int) -> NSAttributedString {
    let style = i < 0 ? redForeground : [:]
    return NSAttributedString(string: String(i), attributes: style)
}

func format(x: Double) -> NSAttributedString {
    return format(Int(round(x)))
}

class Meter {
    
    let app: App
    let name: String
    var actionCost = 0
    var actionLimit: Int
    var firstActed: NSTimeInterval?
    var timeLimit: NSTimeInterval
    var restTime: NSTimeInterval
    
    init(app: App, name: String, actionLimit: Int, timeLimit: NSTimeInterval = 0, restTime: NSTimeInterval = 0) {
        self.app = app
        self.name = name
        self.actionLimit = actionLimit
        self.timeLimit = timeLimit
        self.restTime = restTime
    }
    
    func add(i: Int, now: NSTimeInterval) {
        actionCost += i
        if timeLimit > 0 {
            firstActed = firstActed ?? now
        }
    }
    
    func rest(lastActed: NSTimeInterval, now: NSTimeInterval) -> NSTimeInterval {
        let restLeft = lastActed + restTime - now
        let restNeeded = actionCost != 0 || firstActed != nil
        if restTime > 0 && restLeft <= 0 && restNeeded {
            app.mayGo = true
            app.reset(self)
        }
        return restLeft
    }
    
    func status(lastActed: NSTimeInterval) -> Int {
        let timed = timeLimit != 0
        let activeElapsed = firstActed != nil ? lastActed - firstActed! : 0
        if actionLimit != 0 {
            var value = actionLimit - actionCost
            if timed {
                var timeCost = activeElapsed / timeLimit * Double(actionLimit)
                value -= Int(timeCost)
            }
            return value
        }
        if timed {
            return Int(timeLimit - activeElapsed)
        }
        return actionCost
    }
    
    func expire() {
        if restTime == 0 {
            app.reset(self)
        }
    }
}

class App {
    
    var lastActed = 0.0
    var meters = [Meter]()
    var fadeTime : Float = 3.0
    var fadeValue : CGDisplayBlendFraction = 0.5
    let restDelay = 5.0

    let clock: (() -> NSTimeInterval)
    var errors: [String]
    let id: String
    let state: File
    var metaDowns = [Int]()
    var fadeUntil = 0.0
    var mayGo = false
    var updated = false
    
    func storeState() {
        if updated {
            let parts = ["\(lastActed)"] + map(meters) { "\($0.actionCost) \($0.firstActed ?? 0)" }
            let data = ",".join(parts)
            updated = !state.put(data)
        }
    }
    
    func loadState() {
        
    }



    func configure() {
        meters = [Meter(app: self, name: "s", actionLimit: 0, timeLimit: 120, restTime: 60), Meter(app: self, name: "m", actionLimit: 0, timeLimit: 300, restTime: 900)]
    }

    init(clock: (() -> NSTimeInterval), makeFile: ((path: String?, mode: String) -> File), root: String?, errors: [String]) {
        self.clock = clock
        self.errors = errors
        let s = NSUUID().UUIDString
        self.id = s.substringFromIndex(advance(s.endIndex, -12))
        var statePath: String?
        if root != nil {
            statePath = "\(root!)/state-\(id).txt"
        }
        state = makeFile(path: statePath, mode: "w")
        configure()
        expire()
        tick()
    }
    
    func meta(i: Int) -> Int {
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
    
    func cost(a: Action) -> Int {
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
        let i = cost(a)
        if i != 0 {
            lastActed = now
            updated = true
        }
        map(meters) { $0.add(i, now: now) }
    }
    
    func fade(now: NSTimeInterval, go: Bool) {
        if now < fadeUntil {
            return
        }
        var token = CGDisplayFadeReservationToken(kCGDisplayFadeReservationInvalidToken)
        let status = CGAcquireDisplayFadeReservation(fadeTime, &token)
        if status != CGError(kCGErrorSuccess.value) {
            return
        }
        let red: Float = go ? 0 : 1
        let blue: Float = go ? 1 : 0
        CGDisplayFade(token, 0, CGDisplayBlendFraction(kCGDisplayBlendNormal), fadeValue, red, 0, blue, 0)
        fadeUntil = now + Double(fadeTime)
    }
    
    func tick() -> (ticking: Bool, statusString: NSAttributedString) {
        let now = clock()
        let resting = now - lastActed > restDelay
        let assumedLastActed = resting ? lastActed : now
        
        let restStatuses = map(meters) { $0.rest(assumedLastActed, now: now) }.filter { $0 > 0 }
        let ticking = !restStatuses.isEmpty
        let restStatusStrings = resting && ticking ? [format(minElement(restStatuses))] : []
        
        let meterStatuses = map(meters) { $0.status(assumedLastActed) }
        let shouldStop = any(meterStatuses.map { $0 < 0 })
        let meterStatusStrings = meterStatuses.map(format)
        
        let statusBuffer = NSMutableAttributedString()
        let statusStrings = restStatusStrings + meterStatusStrings
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
    
    func stop() {
        tick()
    }
}

@NSApplicationMain
class AppDelegate: NSObject, NSApplicationDelegate {

    @IBOutlet var item: NSStatusItem!
    
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
        item.button!.attributedTitle = r.statusString
        if timer != nil && !r.ticking {
            timer!.invalidate()
            timer = nil
        }
    }

    func applicationDidFinishLaunching(aNotification: NSNotification) {
        let prompt: String = kAXTrustedCheckOptionPrompt.takeUnretainedValue()
        let trusted = AXIsProcessTrustedWithOptions([prompt: true]) != 0
        if !trusted {
            NSApplication.sharedApplication().terminate(nil)
            return
        }
        
        var root : String? = "~/Library/Application Support/Ergometer".stringByStandardizingPath
        var errors = [String]()
        var e : NSError?
        if !NSFileManager.defaultManager().createDirectoryAtPath(root!, withIntermediateDirectories: true, attributes: nil, error: &e) {
            root = nil
            errors.append(e?.localizedDescription ?? "Unsaved data")
        }
        
        item = NSStatusBar.systemStatusBar().statusItemWithLength(/* NSVariableStatusItemLength */ -1)
        app = App(clock: systemClock, makeFile: makeSystemFile, root: root, errors: errors)
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
