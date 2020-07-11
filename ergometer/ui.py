import os
from random import randint

import wx
import wx.adv
from ergometer.database import setting_types
from ergometer.model import Model
from ergometer.time import precise_clock
from ergometer.util import init, log, log_exceptions

Color = wx.Colour


"""
error:red, rest:orange, session:indigo, daily:teal

const red = '#fc003c' // 5.0R-5-20
const orange = '#e53800' // 10.0R-5-18
const teal = '#009d89' // 2.5BG-5-24
const indigo = '#486aff' // 7.5PB-5-20
"""


def create_icon(fill_color):
    size = 32
    bmp = wx.Bitmap(size, size)
    dc = wx.MemoryDC(bmp)
    dc.SetBrush(wx.Brush(fill_color))
    dc.SetPen(wx.Pen(Color(), style=wx.PENSTYLE_TRANSPARENT))
    dc.DrawRectangle(0, 0, size, size)
    dc.SelectObject(wx.NullBitmap)
    return wx.Icon(bmp)


class Tray(wx.adv.TaskBarIcon):
    def __init__(self, top):
        wx.adv.TaskBarIcon.__init__(self)
        self.SetIcon(create_icon(Color(255, 0, 0)), "FIXME")
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
        self.top = top

    def CreatePopupMenu(self):
        menu = wx.Menu()
        item = wx.MenuItem(menu, wx.ID_ANY, "Exit")
        menu.Bind(wx.EVT_MENU, lambda *args: self.top.Close(), id=item.GetId())
        menu.Append(item)
        return menu

    def on_left_down(self, event):
        r = randint(0, 255)
        g = randint(0, 255)
        b = randint(0, 255)
        self.SetIcon(create_icon(Color(r, g, b)), "FIXME 2")
        self.top.SetTransparent(randint(0, 254))


settings_shown = False


def show_settings(settings, push_local_event, top):
    global settings_shown
    if settings_shown:
        return
    settings_shown = True

    frame = wx.Frame(top)
    sizer = wx.FlexGridSizer(3, 16, 16)
    frame.SetSizer(sizer)

    def add_label(text):
        label = wx.StaticText(frame, label=text)
        sizer.Add(label)

    controls = []
    for type, value in settings:
        add_label(type.name.capitalize().replace("_", " "))
        add_label(str(value))

        field = wx.TextCtrl(frame)
        sizer.Add(field)
        controls.append(field)

    def save(*args):
        if save.waiting:
            wait()
            timer.Start(1000)
            for ctrl in controls:
                ctrl.Disable()
        else:
            log.debug("save")

    def wait(*args):
        if save.waiting > 0:
            save_button.SetLabel(f"Save ({save.waiting})")
            save.waiting -= 1
        else:
            timer.Stop()
            save_button.Enable()
            save_button.SetLabel("Save")

    def cancel(*args):
        save.waiting = 5
        timer.Stop()
        save_button.SetLabel("Preview")
        for ctrl in controls:
            ctrl.Enable()

    timer = wx.Timer(frame)
    frame.Bind(wx.EVT_TIMER, wait, timer)

    save.waiting = 5
    save_button = wx.Button(frame, label="Preview")
    save_button.Bind(wx.EVT_BUTTON, save)
    sizer.Add(save_button)
    controls.append(save_button)

    cancel_button = wx.Button(frame, label="Cancel")
    cancel_button.Bind(wx.EVT_BUTTON, cancel)
    sizer.Add(cancel_button)

    frame.Show()


def get_settings(metrics):
    return [(type, metrics[type.name]) for type in setting_types]


@log_exceptions
def main():
    @log_exceptions
    def draw(*args):
        metrics = model.metrics_at(precise_clock().timestamp())
        if metrics is None:
            return
        show_settings(get_settings(metrics), model.push_local_event, top)

    @log_exceptions
    def exit(*args):
        log.info("Ergometer exiting")
        model.exit()
        tray.RemoveIcon()
        tray.Destroy()
        top.Destroy()
        log.info("Ergometer exited")

    config = init()

    # log.setLevel(20)
    app = wx.App()
    style = wx.TRANSPARENT_WINDOW | wx.STAY_ON_TOP | wx.FRAME_TOOL_WINDOW | wx.MAXIMIZE
    top = wx.Frame(None, style=style) if os.name == "nt" else wx.Frame(None)
    top.SetTransparent(0)
    top.Show()
    tray = Tray(top)
    model = Model(config, threaded=True)
    timer = wx.Timer(top)
    top.Bind(wx.EVT_TIMER, draw, timer)
    top.Bind(wx.EVT_CLOSE, exit)
    hz = wx.Display().GetCurrentMode().refresh or 60
    hz = 2
    timer.Start(int(1000 / hz))
    app.MainLoop()
