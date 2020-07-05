import os
import sys
from random import randint

import wx
import wx.adv

from .model import Model
from .time import precise_clock
from .util import init, log

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
    def __init__(self):
        wx.adv.TaskBarIcon.__init__(self)
        self.SetIcon(create_icon(Color(255, 0, 0)), "FIXME")
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        item = wx.MenuItem(menu, wx.ID_ANY, "Exit")
        menu.Bind(wx.EVT_MENU, lambda *args: top.Close(), id=item.GetId())
        menu.Append(item)
        return menu

    def on_left_down(self, event):
        r = randint(0, 255)
        g = randint(0, 255)
        b = randint(0, 255)
        self.SetIcon(create_icon(Color(r, g, b)), "FIXME 2")
        top.SetTransparent(randint(0, 254))


def show_settings(settings, push_local_event):
    frame = wx.Frame(top)
    sizer = wx.FlexGridSizer(3, 16, 16)
    frame.SetSizer(sizer)
    for name, value in settings.items():
        name_text = wx.StaticText(frame, label=name.capitalize().replace("_", " "))
        value_text = wx.StaticText(frame, label=str(value))
        sizer.Add(name_text)
        sizer.Add(value_text)
        text_ctrl = wx.TextCtrl(frame)
        sizer.Add(text_ctrl)
        log.info(value_text.GetSize())
    frame.Show()


def draw(*args):
    metrics = model.metrics_at(precise_clock().timestamp())
    log.debug(metrics)


def exit(*args):
    log.info("Ergometer exiting")
    model.exit()
    tray.RemoveIcon()
    tray.Destroy()
    top.Destroy()
    log.info("Ergometer exited")


if __name__ == "__main__":
    init()
    log.setLevel(20)
    app = wx.App()
    style = wx.TRANSPARENT_WINDOW | wx.STAY_ON_TOP | wx.FRAME_TOOL_WINDOW | wx.MAXIMIZE
    top = wx.Frame(None, style=style) if os.name == "nt" else wx.Frame(None)
    top.SetTransparent(0)
    top.Show()
    tray = Tray()
    model = Model()
    settings = {"daily_target": 1800, "session_target": 300}
    show_settings(settings, model.push_local_event)
    timer = wx.Timer(top)
    top.Bind(wx.EVT_TIMER, draw, timer)
    top.Bind(wx.EVT_CLOSE, exit)
    hz = wx.Display().GetCurrentMode().refresh or 60
    hz = 2
    timer.Start(int(1000 / hz))
    app.MainLoop()
