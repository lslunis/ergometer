import wx
import wx.adv

Color = wx.Colour
size = 32

app = wx.App()

frame = wx.Frame(None, title="HELLO FRAME")
frame.Show()

fill_color = Color(255, 0, 0)

bmp = wx.Bitmap(size, size)
dc = wx.MemoryDC(bmp)
dc.SetBrush(wx.Brush(fill_color))
dc.SetPen(wx.Pen(Color(), style = wx.PENSTYLE_TRANSPARENT))
dc.DrawRectangle(0, 0, size, size)
dc.SelectObject(wx.NullBitmap)

icon = wx.Icon(bmp)
taskbaricon = wx.adv.TaskBarIcon()
taskbaricon.SetIcon(icon, "HELLO TOOLTIP")

app.MainLoop()
