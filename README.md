# Ergometer

Ergometer is a Mac app intended to prevent or mitigate RSI by monitoring keyboard and mouse activity. If you use it, you'll probably want to fork the code and tweak it first.

## Build

Open `Ergometer.xcodeproj` in Xcode. To build a release version, choose `Product > Archive` in the menu.

## Install

Right-click on the archive you just built and `Open in Finder`, then right-click and `Show Package Contents`, then copy `Products/Applications/Ergometer` to `/Applications`.

## Configure

Create or modify `~/Library/Containers/net.lunis.Ergometer/Data/targets.json` to specify usage targets in seconds, e.g. `{"day": 7200, "session": 900, "rest": 300}` will target two hours per day and fifteen minutes per session with a five-minute rest between sessions.

## Use

Launch Ergometer, right-click on its icon in the Dock, and choose `Open at Login`.

Ergometer creates a system menu bar item that shows the remaining daily, session, and rest time in minutes. When the daily and session targets approach, the screen will begin darkening to suggest that you take a break.

## Notes

`~/Library/Containers/net.lunis.Ergometer/Data/metrics.json` will contain the number of seconds of usage per day (each day begins at 4 AM local time).

The code ignores events from `GWS IDI Device` since those are a particular brand of foot pedals that I happen to own.
