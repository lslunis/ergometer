import IOKit.hid
import SwiftUI

@main
class AppDelegate: NSObject, NSApplicationDelegate {
    var app: App!
    
    func applicationDidFinishLaunching(_ _: Notification) {
        app = App()
    }
    
    func applicationWillTerminate(_ _: Notification) {
        app!.terminate()
    }
}

let listen: IOHIDValueCallback = {
    (context, _, _, _) in
    let app = Unmanaged<App>.fromOpaque(context!).takeUnretainedValue()
    app.act()
}

class App {
    let alert = NSAlert()
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let manager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
    var warningOverlay: Overlay
    var limitOverlay: Overlay
    var targets: Targets?
    var metrics: Metrics?
    var timer: Timer?
    var dirty = false
    var lastFlushed = 0.0
    var failed = false
    
    init() {
        alert.alertStyle = .critical
        alert.messageText = "Fatal error"
        let max = 10000
        let window = NSWindow(contentRect: .init(x: -max / 2, y: -max / 2, width: max, height: max),
                              styleMask: [],
                              backing: .buffered,
                              defer: false)
        window.isOpaque = false
        window.ignoresMouseEvents = true
        window.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.maximumWindow)))
        window.makeKey()
        warningOverlay = Overlay(window, alpha: 0.1, duration: 1, delay: 10)
        limitOverlay = Overlay(window, alpha: 0.96, duration: 1, delay: 10)
        IOHIDManagerOpen(manager, IOOptionBits(kIOHIDOptionsTypeNone))
        IOHIDManagerSetDeviceMatching(manager, [kIOHIDDeviceUsagePageKey: kHIDPage_GenericDesktop] as CFDictionary)
        IOHIDManagerRegisterInputValueCallback(manager, listen, Unmanaged.passUnretained(self).toOpaque())
        IOHIDManagerScheduleWithRunLoop(manager, CFRunLoopGetMain(), CFRunLoopMode.defaultMode.rawValue)
        do {
            self.targets = try Targets()
            self.metrics = try Metrics()
        } catch {
            fail("\(error)")
        }
        tick()
    }
    
    func act() {
        let nowDate = Date()
        let now = nowDate.timeIntervalSince1970
        let sinceLastActed = now - metrics!.lastActed
        if sinceLastActed < 0.1 {
            return
        }
        
        let today = dayFor(nowDate)
        let (dayRemaining, sessionRemaining, restRemaining) = remaining(today, now)
        if sinceLastActed < 15 {
            metrics!.totals[today, default: 0] += sinceLastActed
        }
        if restRemaining <= 0 {
            metrics!.lastRested = now
        }
        metrics!.lastActed = now
        dirty = true
        
        let intensity = 1 - min(dayRemaining / (5 * 60), sessionRemaining / 60)
        if intensity >= 0 {
            (intensity < 1 ? warningOverlay : limitOverlay).show(now)
        }
        tick()
    }
    
    @objc func tick() {
        let nowDate = Date()
        let now = nowDate.timeIntervalSince1970
        let today = dayFor(nowDate)
        let (dayRemaining, sessionRemaining, restRemaining) = remaining(today, now)
        if restRemaining > 0 {
            if timer != nil {
                timer!.invalidate()
            }
            timer = Timer.scheduledTimer(
                timeInterval: 6, target: self, selector: #selector(tick), userInfo: nil, repeats: false)
        }
        do {
            if lastFlushed + 15 < now {
                try flush()
                lastFlushed = now
            }
            try display([dayRemaining, sessionRemaining, restRemaining].map {
                String(format: "%.1f", max(0, $0 / 6.0).rounded(.up) / 10.0)
            }.joined(separator: "  "))
        } catch {
            fail("\(error)")
        }
        
    }
    
    func remaining(_ today: String, _ now: Double) -> (Double, Double, Double) {
        let dayRemaining = targets!.day - (metrics!.totals[today] ?? 0)
        let restRemaining = targets!.rest - (now - metrics!.lastActed)
        let sessionRemaining = targets!.session - (restRemaining <= 0 ? 0 : now - metrics!.lastRested)
        return (dayRemaining, sessionRemaining, restRemaining)
    }
    
    func display(_ message: String) throws {
        guard let button = item.button else {
            throw AppError.statusItemButtonIsNil
        }
        button.title = message
    }
    
    func flush() throws {
        if dirty {
            try metrics!.flush()
            dirty = false
        }
    }
    
    func fail(_ message: String) {
        failed = true
        alert.informativeText = message
        alert.runModal()
        NSApplication.shared.terminate(nil)
    }
    
    func terminate() {
        if !failed {
            do {
                try flush()
            } catch {
                fail("\(error)")
            }
        }
    }
}

class Overlay {
    var window: NSWindow
    var alpha: CGFloat
    var duration: Double
    var delay: Double
    var showUntil = 0.0
    var timer: Timer?
    
    init(_ window: NSWindow, alpha: CGFloat, duration: Double, delay: Double) {
        self.window = window
        self.alpha = alpha
        self.duration = duration
        self.delay = delay
    }
    
    func show(_ now: Double) {
        if now < showUntil + delay {
            return
        }
        window.backgroundColor = NSColor(red: 0, green: 0, blue: 0, alpha: alpha)
        window.orderFrontRegardless()
        showUntil = now + duration
        timer = Timer.scheduledTimer(
            timeInterval: duration, target: self, selector: #selector(hide), userInfo: nil, repeats: false)
    }
    
    @objc func hide() {
        window.orderOut(nil)
    }
}

struct Targets {
    var file: URL
    var day = 8 * 3600.0
    var session = 3600.0
    var rest = 5 * 60.0
    
    init() throws {
        let (file, exists) = try fileFor("targets")
        self.file = file
        if (exists) {
            let json = try JSONSerialization.jsonObject(with: try Data(contentsOf: file)) as! [String: Any]
            self.day = json["day"] as! Double
            self.session = json["session"] as! Double
            self.rest = json["rest"] as! Double
        }
    }
}

struct Metrics {
    let file: URL
    var totals = [String: Double]()
    var lastRested = 0.0
    var lastActed = 0.0
    
    init() throws {
        let (file, exists) = try fileFor("metrics")
        self.file = file
        if (exists) {
            let json = try JSONSerialization.jsonObject(with: try Data(contentsOf: file)) as! [String: Any]
            self.totals = json["totals"] as! [String: Double]
            self.lastRested = json["lastRested"] as! Double
            self.lastActed = json["lastActed"] as! Double
        }
    }
    
    func flush() throws {
        let data = try JSONSerialization.data(
            withJSONObject: [
                "totals": totals,
                "lastRested": lastRested,
                "lastActed": lastActed,
            ],
            options: [.prettyPrinted, .sortedKeys])
        try data.write(to: file, options: .atomic)
    }
}

func dayFor(_ date: Date) -> String {
    return ISO8601DateFormatter.string(
        from: date - 4 * 3600, timeZone: TimeZone.current,
        formatOptions: [.withFullDate, .withDashSeparatorInDate])
}

func fileFor(_ name: String) throws -> (URL, Bool) {
    let path = "\(name).json"
    return (URL(fileURLWithPath: path), FileManager.default.fileExists(atPath: path))
}

enum AppError: Error {
    case statusItemButtonIsNil
}
