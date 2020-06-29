from random import randint

import wx
import wx.adv

Color = wx.Colour


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
        menu.Bind(wx.EVT_MENU, exit, id=item.GetId())
        menu.Append(item)
        return menu

    def on_left_down(self, event):
        r = randint(0, 255)
        g = randint(0, 255)
        b = randint(0, 255)
        self.SetIcon(create_icon(Color(r, g, b)), "FIXME 2")


def exit(*args):
    tray.RemoveIcon()
    tray.Destroy()
    frame.Destroy()


app = wx.App()
frame = wx.Frame(
    None,
    style=wx.TRANSPARENT_WINDOW | wx.STAY_ON_TOP | wx.FRAME_TOOL_WINDOW | wx.MAXIMIZE,
)
frame.SetTransparent(128)
frame.Show()
tray = Tray()
frame.Bind(wx.EVT_CLOSE, exit)

app.MainLoop()
