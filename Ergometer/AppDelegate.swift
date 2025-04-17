import IOKit.hid
import SwiftUI

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
            timeInterval: duration, target: self, selector: #selector(hide), userInfo: nil,
            repeats: false)
    }

    @objc func hide() {
        window.orderOut(nil)
    }
}

func dayFor(_ date: Date) -> String {
    return ISO8601DateFormatter.string(
        // Treat 4 AM local time as midnight.
        from: date - 4 * 3600, timeZone: TimeZone.current,
        formatOptions: [.withFullDate, .withDashSeparatorInDate])
}

struct Targets: Codable, Equatable {
    var day: Double
    var session: Double
    var rest: Double
    var lastUpdated: Double
}

struct Metrics: Codable, Equatable {
    var lastActed: Double
    var lastRested: Double
    var totals: [String: Double]

}

let initialTargets = Targets(day: 6 * 3600, session: 3600, rest: 300, lastUpdated: 0)
let initialRemoteTotals: [String: [String: Double]] = [:]

let computerName = Host.current().localizedName ?? "unknown"
let dataDir = ("~/ergometer/data" as NSString).expandingTildeInPath
let localMetricsName = "metrics.\(computerName).json"
let localMetricsPath = (dataDir as NSString).appendingPathComponent(localMetricsName)

func loadJson<T: Codable>(name: String) -> T {
    let path = (dataDir as NSString).appendingPathComponent(name)
    let data = try! Data(contentsOf: URL(fileURLWithPath: path))
    return try! JSONDecoder().decode(T.self, from: data)
}

class App {
    let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let iohidManager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
    let warningOverlay: Overlay
    let limitOverlay: Overlay

    var targets = initialTargets
    var localMetrics: Metrics
    var remoteTotals = initialRemoteTotals

    var displayTimer: Timer?
    var loadTimer: Timer?
    var flushTimer: Timer?
    var shouldFlushLocalMetrics = false

    @objc func updateDisplayUntilRested() {
        let nowDate = Date()
        let now = nowDate.timeIntervalSince1970
        let today = dayFor(nowDate)
        let (dayRemaining, sessionRemaining, restRemaining) = remaining(today, now)

        if restRemaining > 0 {
            displayTimer?.invalidate()
            displayTimer = Timer.scheduledTimer(
                timeInterval: 6, target: self, selector: #selector(updateDisplayUntilRested),
                userInfo: nil,
                repeats: false)
        }

        statusItem.button!.title =
            ([dayRemaining, sessionRemaining, restRemaining].map {
                String(format: "%.1f", ($0 / 6.0).rounded(.up) / 10.0)
            }.joined(separator: "  "))
    }

    func load(names: [String]) {
        // Reinitialize, otherwise removals won't be respected.
        targets = initialTargets
        remoteTotals = initialRemoteTotals

        for name in names {
            if name == localMetricsName {
                continue  // self.localMetrics is the source of truth
            }

            if name.hasPrefix("targets.") {
                let targets: Targets = loadJson(name: name)
                if targets.lastUpdated > self.targets.lastUpdated {
                    self.targets = targets
                }
            } else if name.hasPrefix("metrics.") {
                let metrics: Metrics = loadJson(name: name)
                remoteTotals[name] = metrics.totals
            }
        }
    }

    @objc func loadDataDir() {
        let names = try! FileManager.default.contentsOfDirectory(atPath: dataDir)
        load(names: names)
    }

    @objc func flushLocalMetrics() {
        if shouldFlushLocalMetrics {
            shouldFlushLocalMetrics = false

            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try! encoder.encode(localMetrics)
            try! data.write(to: URL(fileURLWithPath: localMetricsPath))
        }
    }

    init() {
        let max = 10000
        let window = NSWindow(
            contentRect: .init(x: -max / 2, y: -max / 2, width: max, height: max),
            styleMask: [],
            backing: .buffered,
            defer: false)
        window.isOpaque = false
        window.ignoresMouseEvents = true
        window.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.maximumWindow)))
        window.makeKey()
        warningOverlay = Overlay(window, alpha: 0.1, duration: 1, delay: 10)
        limitOverlay = Overlay(window, alpha: 0.96, duration: 1, delay: 10)

        localMetrics =
            FileManager.default.fileExists(atPath: localMetricsPath)
            ? loadJson(name: localMetricsName)
            : Metrics(lastActed: 0, lastRested: 0, totals: [:])

        IOHIDManagerOpen(iohidManager, IOOptionBits(kIOHIDOptionsTypeNone))
        IOHIDManagerSetDeviceMatching(
            iohidManager, [kIOHIDDeviceUsagePageKey: kHIDPage_GenericDesktop] as CFDictionary)
        IOHIDManagerRegisterInputValueCallback(
            iohidManager,
            {
                (context, _, _, _) in
                let app = Unmanaged<App>.fromOpaque(context!).takeUnretainedValue()
                app.act()
            }, Unmanaged.passUnretained(self).toOpaque())
        IOHIDManagerScheduleWithRunLoop(
            iohidManager, CFRunLoopGetMain(), CFRunLoopMode.defaultMode.rawValue)

        updateDisplayUntilRested()

        loadDataDir()
        loadTimer = Timer.scheduledTimer(
            timeInterval: 300, target: self, selector: #selector(loadDataDir), userInfo: nil,
            repeats: true)

        flushTimer = Timer.scheduledTimer(
            timeInterval: 300, target: self, selector: #selector(flushLocalMetrics), userInfo: nil,
            repeats: true)
    }

    func remaining(_ today: String, _ now: Double) -> (Double, Double, Double) {
        let dayRemaining =
            targets.day - localMetrics.totals[today, default: 0]
            - remoteTotals.reduce(0) { $0 + ($1.value[today] ?? 0) }
        let restRemaining = targets.rest - (now - localMetrics.lastActed)
        let sessionRemaining =
            targets.session - (restRemaining <= 0 ? 0 : now - localMetrics.lastRested)
        return (dayRemaining, sessionRemaining, restRemaining)
    }

    func act() {
        let nowDate = Date()
        let now = nowDate.timeIntervalSince1970
        let sinceLastActed = now - localMetrics.lastActed
        if sinceLastActed < 0.1 {
            return
        }

        let today = dayFor(nowDate)
        let (dayRemaining, sessionRemaining, restRemaining) = remaining(today, now)
        if sinceLastActed < 15 {
            localMetrics.totals[today, default: 0] += sinceLastActed
        }
        if restRemaining <= 0 {
            localMetrics.lastRested = now
        }
        localMetrics.lastActed = now
        shouldFlushLocalMetrics = true

        let intensity = 1 - min(dayRemaining / (5 * 60), sessionRemaining / 60)
        if intensity >= 0 {
            (intensity < 1 ? warningOverlay : limitOverlay).show(now)
        }

        updateDisplayUntilRested()
    }
}

@main
class AppDelegate: NSObject, NSApplicationDelegate {
    var app: App!

    func applicationDidFinishLaunching(_ _: Notification) {
        app = App()
    }

    func applicationWillTerminate(_ _: Notification) {
        app.flushLocalMetrics()
    }
}
