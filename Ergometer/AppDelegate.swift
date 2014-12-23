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

enum Action {
    case Key(Int), Meta(Int), Click, Ignored
}

/*
NSString *path = [@"~/Cellar/log/rsi-meter.log" stringByStandardizingPath];
FILE *file = fopen([path UTF8String], "a");
if (!file) {
return;
}

fputs([string UTF8String], file);
fclose(file);
*/

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
    
    var actionCost = 0
    var actionLimit: Int
    var firstActed: NSTimeInterval?
    var timeLimit: NSTimeInterval
    var restTime: NSTimeInterval
    
    init(actionLimit: Int, timeLimit: NSTimeInterval = 0, restTime: NSTimeInterval = 0) {
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
        if restTime > 0 && restLeft <= 0 {
            actionCost = 0
            firstActed = nil
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
            actionCost = 0
            firstActed = nil
        }
    }
}

class App {
    
    var lastActed = 0.0
    var meters = [Meter(actionLimit: 0, timeLimit: 300, restTime: 900)]
    var fadeTime : Float = 3.0
    var fadeValue : CGDisplayBlendFraction = 0.5
    let restDelay = 5.0

    var metaDowns = [Int]()
    var fadeUntil = 0.0
    var clock: (() -> NSTimeInterval)
    
    init(clock: (() -> NSTimeInterval)) {
        self.clock = clock
    }
    
    func configure() {
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
        }
        meters.map { $0.add(i, now: now) }
    }
    
    func fade(now: NSTimeInterval) {
        if now < fadeUntil {
            return
        }
        var token = CGDisplayFadeReservationToken(kCGDisplayFadeReservationInvalidToken)
        let status = CGAcquireDisplayFadeReservation(fadeTime, &token)
        if status != CGError(kCGErrorSuccess.value) {
            return
        }
        CGDisplayFade(token, 0, CGDisplayBlendFraction(kCGDisplayBlendNormal), fadeValue, 0, 0, 0, 0)
        fadeUntil = now + Double(fadeTime)
    }
    
    func tick() -> (ticking: Bool, statusString: NSAttributedString) {
        let now = clock()
        let resting = now - lastActed > restDelay
        let assumedLastActed = resting ? lastActed : now
        
        let restStatuses = meters.map { $0.rest(assumedLastActed, now: now) }.filter { $0 > 0 }
        let ticking = !restStatuses.isEmpty
        let restStatusStrings = resting && ticking ? [format(minElement(restStatuses))] : []
        
        let meterStatuses = meters.map { $0.status(assumedLastActed) }
        let shouldFade = any(meterStatuses.map { $0 < 0 })
        let meterStatusStrings = meterStatuses.map(format)
        
        let statusBuffer = NSMutableAttributedString()
        let statusStrings = restStatusStrings + meterStatusStrings
        for (i, s) in enumerate(statusStrings) {
            if i > 0 {
                statusBuffer.appendAttributedString(NSAttributedString(string: "  "))
            }
            statusBuffer.appendAttributedString(s)
        }
        
        if shouldFade && !resting {
            fade(now)
        }
        
        return (ticking, statusBuffer)
    }
    
    func expire() {
        meters.map { $0.expire() }
    }
}

@NSApplicationMain
class AppDelegate: NSObject, NSApplicationDelegate {

    @IBOutlet var item: NSStatusItem!
    
    var app = App(clock: systemClock)
    var timer : NSTimer!
    
    func act(e: NSEvent!) {
        app.act(makeAction(e))
        if timer == nil {
            timer = NSTimer.scheduledTimerWithTimeInterval(
                1.0, target: self, selector: "tick", userInfo: nil, repeats: true)
        }
    }
    
    func tick() {
        let r = app.tick()
        item.button!.attributedTitle = r.statusString
        if timer != nil && !r.ticking {
            timer.invalidate()
            timer = nil
        }
    }

    func applicationDidFinishLaunching(aNotification: NSNotification) {
        let prompt : String = kAXTrustedCheckOptionPrompt.takeUnretainedValue()
        let trusted = AXIsProcessTrustedWithOptions([prompt: true]) != 0
        if !trusted {
            NSApplication.sharedApplication().terminate(self)
        }
        
        item = NSStatusBar.systemStatusBar().statusItemWithLength(/* NSVariableStatusItemLength */ -1)
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
