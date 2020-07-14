import os
import struct
from datetime import datetime
from math import isfinite

import wx
import wx.adv
from ergometer.database import data_format, setting_types
from ergometer.model import Model
from ergometer.time import imprecise_clock, in_seconds, precise_clock
from ergometer.util import clip, init, log, log_exceptions


class Tray(wx.adv.TaskBarIcon):
    def __init__(self, top, model):
        wx.adv.TaskBarIcon.__init__(self)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.show_history)
        self.top = top
        self.model = model
        self.history_step = "1d"
        self.last_set_icon = 0

    def CreatePopupMenu(self):
        menu = wx.Menu()
        items = {}
        if self.model.ready:
            items.update(History=self.show_history, Settings=self.show_settings)
        items.update(Exit=lambda *unused: self.top.Close())
        for label, fn in items.items():
            item = wx.MenuItem(menu, wx.ID_ANY, label)
            menu.Bind(wx.EVT_MENU, fn, id=item.GetId())
            menu.Append(item)
        return menu

    def maybe_set_icon(self, get_icon_with_tooltip):
        now = precise_clock().timestamp()
        if now - self.last_set_icon < 6:
            return
        self.last_set_icon = now
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
                label.SetFont(wx.Font(10,wx.FONTFAMILY_TELETYPE,wx.NORMAL,wx.NORMAL, faceName='Consolas'))
                grid.Add(label, wx.ALIGN_RIGHT if j == 1 else 0)
                labels.append(label)

        button_row = wx.BoxSizer()
        field = wx.TextCtrl(frame)
        field.SetValue(self.history_step)
        button_row.Add(field)

        def view(*unused):
            try:
                step = parse(field, as_duration=True)
                if not step:
                    return
            except ValueError:
                return
            self.history_step = field.GetValue()
            end = precise_clock().timestamp()
            start = end - step * limit
            for labels, time_total in zip(
                label_rows, self.model.activity_totals(start, step, limit)
            ):
                time_label, total_label = labels
                time, total = time_total
                time_label.SetLabel(format_time(time))
                total_label.SetLabel(format_in_minutes(total))

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
            typed_values = []
            for type, field in typed_fields:
                try:
                    value = parse(field, is_duration(type))
                    if value:
                        typed_values.append((type, value))
                except ValueError:
                    # mark all errors before returning
                    has_errors = True
            return None if has_errors else typed_values

        def save(*unused):
            typed_values = get_typed_values()
            if save.waiting:
                if not typed_values:
                    return
                wait()
                timer.Start(1000)
                for ctrl in controls:
                    ctrl.Disable()
            else:
                time = int(imprecise_clock().timestamp())
                for type, value in typed_values:
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
            save.waiting = 5
            timer.Stop()
            save_button.SetLabel("Preview")
            for ctrl in controls:
                ctrl.Enable()

        timer = wx.Timer(frame)
        frame.Bind(wx.EVT_TIMER, wait, timer)

        button_row = wx.BoxSizer()
        save.waiting = 15
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
    return type.name.rpartition("_")[-1] in ["notice", "target"]


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


def compute_opacity(metrics):
    opacity = 0
    return int(255 * opacity)


def compute_rectangles(metrics, size):
    return []


"""
error:red, rest:orange, session:indigo, daily:teal

const red = '#fc003c' // 5.0R-5-20
const orange = '#e53800' // 10.0R-5-18
const teal = '#009d89' // 2.5BG-5-24
const indigo = '#486aff' // 7.5PB-5-20
"""


def create_icon_with_tooltip(metrics):
    size = 32
    bmp = wx.Bitmap(size, size)
    dc = wx.MemoryDC(bmp)
    dc.SetPen(wx.Pen(wx.Colour(), style=wx.PENSTYLE_TRANSPARENT))
    for r, g, b, x, y, w, h in compute_rectangles(metrics, size):
        dc.SetBrush(wx.Brush(wx.Colour(r, g, b)))
        dc.DrawRectangle(x, y, w, h)
    dc.SelectObject(wx.NullBitmap)

    tooltip = " - ".join(
        format_in_minutes(metrics[f"{x}_target"] - metrics[f"{x}_value"])
        for x in ["daily", "session", "rest"]
    )
    return wx.Icon(bmp), tooltip


class OpacitySetter:
    def __init__(self, top):
        self.top = top
        self.opacity = None

    def __call__(self, opacity):
        if opacity != self.opacity:
            self.top.SetTransparent(clip(opacity, low=0, high=254))
            self.opacity = opacity


@log_exceptions
def main():
    @log_exceptions
    def draw(*unused):
        metrics = model.metrics_at(precise_clock().timestamp())
        if metrics is None:
            return
        maybe_set_opacity(compute_opacity(metrics))
        tray.maybe_set_icon(lambda: create_icon_with_tooltip(metrics))

    @log_exceptions
    def exit(*unused):
        log.info("Ergometer exiting")
        model.exit()
        tray.RemoveIcon()
        tray.Destroy()
        top.Destroy()
        log.info("Ergometer exited")

    config = init()

    app = wx.App()
    style = wx.TRANSPARENT_WINDOW | wx.STAY_ON_TOP | wx.FRAME_TOOL_WINDOW | wx.MAXIMIZE
    top = wx.Frame(None, style=style) if os.name == "nt" else wx.Frame(None)
    maybe_set_opacity = OpacitySetter(top)
    maybe_set_opacity(0)
    top.Show()
    model = Model(config, threaded=True)
    tray = Tray(top, model)
    timer = wx.Timer(top)
    top.Bind(wx.EVT_TIMER, draw, timer)
    top.Bind(wx.EVT_CLOSE, exit)
    hz = wx.Display().GetCurrentMode().refresh or 60
    timer.Start(int(1000 / hz))
    app.MainLoop()
