import os
import struct
from datetime import datetime
from itertools import zip_longest
from math import ceil, exp, isfinite

import wx
import wx.adv

from ergometer.database import data_format, setting_types
from ergometer.model import Model
from ergometer.time import (
    day_start_of,
    imprecise_clock,
    in_seconds,
    min_time,
    precise_clock,
)
from ergometer.util import clip, init, lerp, log, log_exceptions

is_windows = os.name == "nt"


class Controller:
    def __init__(self, top, model):
        top.Bind(wx.EVT_LEFT_DCLICK, self.show_history)
        top.Bind(wx.EVT_CONTEXT_MENU, self.show_menu)
        self.top = top
        self.model = model
        self.history_step = "1d"
        self.last_animated = min_time

    def show_menu(self, *unused):
        menu = wx.Menu()
        items = {}
        if self.model.ready:
            items.update(History=self.show_history, Settings=self.show_settings)
        items.update(Exit=lambda *unused: self.top.Close())
        for label, fn in items.items():
            item = wx.MenuItem(menu, wx.ID_ANY, label)
            menu.Bind(wx.EVT_MENU, fn, id=item.GetId())
            menu.Append(item)
        self.top.PopupMenu(menu)

    def maybe_animate(self, get_icon_with_tooltip):
        now = precise_clock().timestamp()
        if now - self.last_animated < 6:
            return
        self.last_animated = now
        self.SetIcon(*get_icon_with_tooltip())

    def show_history(self, *unused):
        if not self.model.ready:
            return
        frame = wx.Frame(self.top)
        limit = 50
        grid = wx.FlexGridSizer(2, 10, 20)
        label_rows = []
        for i in range(limit):
            labels = []
            label_rows.append(labels)
            for j in range(2):
                label = wx.StaticText(frame)
                label.SetFont(
                    wx.Font(
                        10,
                        wx.FONTFAMILY_TELETYPE,
                        wx.NORMAL,
                        wx.NORMAL,
                        faceName="Consolas",
                    )
                )
                grid.Add(label, wx.ALIGN_RIGHT if j == 1 else 0)
                labels.append(label)

        def view(*unused):
            try:
                step = parse(field, as_duration=True)
                if not step:
                    return
            except ValueError:
                return
            self.history_step = field.GetValue()
            now_dt = precise_clock()
            day_end = day_start_of(now_dt) + in_seconds(days=1)
            end = ceil((now_dt.timestamp() - day_end) / step) * step + day_end
            start = end - step * limit
            for labels, time_total in zip_longest(
                label_rows, self.model.activity_totals(start, step, limit)
            ):
                time_label, total_label = labels
                time, total = time_total
                time_label.SetLabel(format_time(time))
                total_label.SetLabel(format_in_minutes(total))

        button_row = wx.BoxSizer()
        field = wx.TextCtrl(frame, style=wx.TE_PROCESS_ENTER)
        field.Bind(wx.EVT_TEXT_ENTER, view)
        field.SetValue(self.history_step)
        button_row.Add(field)
        view_button = wx.Button(frame, label="View")
        view_button.Bind(wx.EVT_BUTTON, view)
        button_row.Add(view_button)
        column = wx.BoxSizer(wx.VERTICAL)
        column.AddMany([grid, button_row])

        view()
        frame.SetSizerAndFit(column)
        show_in_corner(frame)

    def show_settings(self, *unused):
        if not self.model.ready:
            return
        frame = wx.Frame(self.top)
        grid = wx.FlexGridSizer(3, 16, 16)

        def add_label(text):
            grid.Add(wx.StaticText(frame, label=text))

        controls = []
        typed_fields = []
        metrics = self.model.metrics_at(precise_clock().timestamp())
        settings = [(type, metrics[type.name]) for type in setting_types]
        for type, value in settings:
            add_label(type.name.capitalize().replace("_", " "))
            add_label(format_duration(value) if is_duration(type) else str(value))

            field = wx.TextCtrl(frame)
            grid.Add(field)
            controls.append(field)
            typed_fields.append((type, field))

        def get_typed_values():
            has_errors = False
            typed_values = {}
            for type, field in typed_fields:
                try:
                    value = parse(field, is_duration(type))
                    if value:
                        typed_values[type] = value
                except ValueError:
                    # mark all errors before returning
                    has_errors = True
            return None if has_errors else typed_values

        def save(*unused):
            typed_values = get_typed_values()
            if save.waiting:
                if not typed_values:
                    return
                for type in typed_values:
                    if type.name.endswith("_target"):
                        save.waiting = 2
                        break
                wait()
                timer.Start(1000)
                for ctrl in controls:
                    ctrl.Disable()
            else:
                time = int(imprecise_clock().timestamp())
                for type, value in typed_values.items():
                    self.model.push_local_event(
                        struct.pack(data_format, type.value, value, time)
                    )
                frame.Close()

        def wait(*unused):
            if save.waiting > 0:
                save_button.SetLabel(f"Save ({save.waiting})")
                save.waiting -= 1
            else:
                timer.Stop()
                save_button.Enable()
                save_button.SetLabel("Save")

        def revise(*unused):
            save.waiting = 1
            timer.Stop()
            save_button.SetLabel("Preview")
            for ctrl in controls:
                ctrl.Enable()

        timer = wx.Timer(frame)
        frame.Bind(wx.EVT_TIMER, wait, timer)

        button_row = wx.BoxSizer()
        save.waiting = 1
        save_button = wx.Button(frame, label="Preview")
        save_button.Bind(wx.EVT_BUTTON, save)
        button_row.Add(save_button)
        controls.append(save_button)

        revise_button = wx.Button(frame, label="Revise")
        revise_button.Bind(wx.EVT_BUTTON, revise)
        button_row.Add(revise_button)

        column = wx.BoxSizer(wx.VERTICAL)
        column.AddMany(
            [
                grid,
                wx.StaticText(
                    frame, label="You have a flare-up next week. Are you surprised?"
                ),
                button_row,
            ]
        )
        frame.SetSizerAndFit(column)
        show_in_corner(frame)


def show_in_corner(frame):
    dx, dy, dw, dh = wx.ClientDisplayRect()
    fw, fh = frame.GetSize()
    fx = dx + dw - fw
    fy = dy + dh - fh
    frame.SetPosition((fx, fy))
    frame.Raise()
    frame.Show()


def parse(field, as_duration):
    def mark_error():
        field.SetBackgroundColour("pink")
        field.Refresh()

    field.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
    field.Refresh()
    string = field.GetValue()
    if not string:
        return
    if as_duration:
        suffix = string[-1].lower()
        if suffix not in suffix_to_unit:
            mark_error()
            raise ValueError(f"invalid duration: {suffix}")
        string = string[:-1]
    else:
        suffix = None

    try:
        value = float(string)
    except ValueError:
        mark_error()
        raise
    if not (isfinite(value) and value > 0):
        mark_error()
        raise ValueError(f"expected a positive finite number: {value}")
    if suffix:
        value = in_seconds_using_suffix(value, suffix)
    return value


def is_duration(type):
    return type.name.rpartition("_")[-1] in ["target"]


suffix_to_unit = dict(w="weeks", d="days", h="hours", m="minutes", s="seconds")


def format_duration(value, suffix=None, spec=".9g"):
    f = lambda suffix: format(from_seconds_using_suffix(value, suffix), spec) + suffix
    return f(suffix) if suffix else min(map(f, suffix_to_unit), key=len)


def format_time(time):
    return datetime.fromtimestamp(time).isoformat(" ")


def format_in_minutes(duration):
    return format_duration(duration, "m", spec=".1f")


def in_seconds_using_suffix(value, suffix):
    unit = suffix_to_unit[suffix]
    return in_seconds(**{unit: value})


def from_seconds_using_suffix(value, suffix):
    return value / in_seconds_using_suffix(1, suffix)


def compute_fade(m):
    m = {"session_value": m["session_value"] - m["rest_value"], **m}
    fade = 0
    fade_min = m["fade_min"]
    fade_max = m["fade_max"]
    for kind in ["daily", "session", "rest"]:
        is_rest = kind == "rest"
        value = m[f"{kind}_value"]
        target = m[f"{kind}_target"]
        notice = target * m[f"{kind}_notice"]
        if value < notice:
            f = 0
        elif value < target:
            f = fade_min if is_rest else lerp(value, notice, target, 0, fade_max)
        else:
            f = 0 if is_rest else fade_max
        fade = max(fade, f)
    if fade > fade_min:
        k = m["unfade_multiplier"]
        fade = clip(
            fade + k - k * exp(m["unfade_rate"] * m["rest_value"]),
            low=fade_min,
            high=fade_max,
        )
    return ceil(255 * fade)


def compute_rectangles(m, n):
    # http://pteromys.melonisland.net/munsell/
    # set value to 8, render interpolated, take screenshot of chroma/hue grid
    # use MS Paint eyedropper tool to choose max chroma for several hues
    black = (28, 28, 28)
    white = (255, 255, 255)
    lime = (15, 231, 20)
    blue = (35, 216, 253)
    yellow = (239, 196, 15)
    background = (0, 0, n, n, *white)
    if not m:
        return [background]
    dv = m["daily_value"]
    dt = m["daily_target"]
    sv = m["session_value"]
    st = m["session_target"]
    rv = m["rest_value"]
    rt = m["rest_target"]
    srt = st + rt
    rectangles = [
        background,
        (0, sv / srt * n, n, (st - sv) / srt * n, *lime),
        (0, st / srt * n, n, (rt - rv) / srt * n, *yellow),
    ]
    k = 1
    w = n / 2
    g = n / 4
    b = (n - k * w - (k - 1) * g) / 2
    v = dv / dt * k
    for i in range(int(v), k - int(v)):
        x = b + (w + g) * i
        y = clip(v - i, low=0) * n
        rectangles.append((x, y, w, n - y, *blue))
    return rectangles


def compute_tooltip(metrics):
    return (
        " - ".join(
            format_in_minutes(metrics[f"{x}_target"] - metrics[f"{x}_value"])
            for x in ["daily", "session", "rest"]
        )
        if metrics
        else "Ergometer"
    )


def create_icon_with_tooltip(metrics=None):
    size = 32
    bmp = wx.Bitmap(size, size)
    dc = wx.MemoryDC(bmp)
    dc.SetPen(wx.Pen(wx.Colour(), style=wx.PENSTYLE_TRANSPARENT))
    for x, y, w, h, r, g, b in compute_rectangles(metrics, size):
        dc.SetBrush(wx.Brush(wx.Colour(r, g, b)))
        dc.DrawRectangle(x, y, w, h)
    dc.SelectObject(wx.NullBitmap)

    return wx.Icon(bmp), compute_tooltip(metrics)


class Fader:
    def __init__(self, top):
        self.top = top
        self.fade = None

    def __call__(self, fade):
        if fade != self.fade:
            fade = clip(fade, low=0, high=254)
            log.info(f"fade {fade}")
            self.top.SetTransparent(
                fade
            ) if is_windows else self.top.SetBackgroundColour(
                wx.Colour(fade, fade, fade)
            )
            self.fade = fade


def make_frame(parent, style):
    return wx.Frame(parent, style=style) if is_windows else wx.Frame(parent)


@log_exceptions
def main():
    @log_exceptions
    def draw(*unused):
        metrics = model.metrics_at(precise_clock().timestamp())
        if metrics is None:
            return
        maybe_fade(compute_fade(metrics))

    @log_exceptions
    def exit(*unused):
        log.info("Ergometer exiting")
        model.exit()
        top.Destroy()
        log.info("Ergometer exited")

    config = init()

    app = wx.App()
    top = make_frame(None, wx.RESIZE_BORDER | wx.STAY_ON_TOP | wx.FRAME_TOOL_WINDOW)
    model = Model(config, threaded=True)
    controller = Controller(top, model)
    top.Show()
    overlay = make_frame(
        top, wx.TRANSPARENT_WINDOW | wx.STAY_ON_TOP | wx.FRAME_TOOL_WINDOW | wx.MAXIMIZE
    )
    maybe_fade = Fader(overlay)
    maybe_fade(0)
    overlay.Show()

    timer = wx.Timer(top)
    top.Bind(wx.EVT_TIMER, draw, timer)
    top.Bind(wx.EVT_CLOSE, exit)
    hz = wx.Display().GetCurrentMode().refresh or 60
    timer.Start(int(1000 / hz))
    app.MainLoop()
