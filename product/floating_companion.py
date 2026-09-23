"""A real topmost WinForms desktop companion, owned by the app UI thread."""
import json
import logging
import threading
import time


def dock_position(bounds, size, point, edge, hidden=False):
    left, top, right, bottom = bounds
    width, height = size
    x, y = point
    x = max(left, min(x, right-width))
    y = max(top, min(y, bottom-height))
    if edge == 'left': x = left-width+18 if hidden else left
    elif edge == 'right': x = right-18 if hidden else right-width
    elif edge == 'top': y = top-height+18 if hidden else top
    elif edge == 'bottom': y = bottom-18 if hidden else bottom-height
    return x, y


class FloatingCompanion:
    def __init__(self, window, service, root):
        from System import Action
        from System.Drawing import Bitmap, Color, Font, Point, Size
        from System.Windows.Forms import (Form, FormBorderStyle, FormStartPosition,
                                         Timer, ContextMenuStrip)
        self.window, self.service, self.root = window, service, root
        self.Action, self.Point, self.Size, self.Color = Action, Point, Size, Color
        self.form = Form()
        f = self.form
        f.Text = '萤 In Work · 桌面小萤'
        f.FormBorderStyle = getattr(FormBorderStyle, 'None')
        f.StartPosition = FormStartPosition.Manual
        f.ShowInTaskbar = False
        f.TopMost = True
        f.BackColor = Color.Magenta
        f.TransparencyKey = Color.Magenta
        f.ClientSize = Size(104, 132)
        self.logo = Bitmap(str(root/'frontend/assets/ying.png'))
        self.font = Font('Microsoft YaHei UI', 10)
        self.menu = ContextMenuStrip()
        self.menu.Font = Font('Microsoft YaHei UI', 11)
        self.callbacks = []
        def add(label, callback):
            item = self.menu.Items.Add(label)
            handler = lambda *_: callback()
            self.callbacks.append(handler)
            item.Click += handler
        add('打开工作台', lambda: self.command('home'))
        self.menu.Items.Add('-')
        add('开始 / 暂停陪伴', self.toggle_camera)
        add('专注守护', lambda: self.command('focus'))
        add('眼周观察', lambda: self.command('dark_circle'))
        add('舌象观察', lambda: self.command('tongue'))
        add('皮肤观察', lambda: self.command('acne'))
        add('眼部米字操', lambda: self.command('eye'))
        add('颈部十字操', lambda: self.command('neck'))
        add('真实手势对战', lambda: self.command('game'))
        add('偏好设置', lambda: self.command('settings'))
        self.menu.Items.Add('-')
        add('隐藏桌面小萤', lambda: self.service.update_settings({'floating_window': False}))
        add('退出萤 In Work', lambda: self.background(self.window.destroy))
        f.ContextMenuStrip = self.menu
        self.edge, self.tucked = None, False
        self.anchor = (0, 0)
        self.drag_start = None
        self.dragged = False
        self.last_hover = time.monotonic()
        self.hovering = False
        self.mood = '•ᴗ•'
        self.path = service.data_dir/'floating_position.json'
        self.restore_position()
        f.Paint += self.paint
        f.MouseEnter += self.enter
        f.MouseLeave += self.leave
        f.MouseDown += self.down
        f.MouseMove += self.move
        f.MouseUp += self.up
        f.MouseDoubleClick += self.double_click
        self.timer = Timer()
        self.timer.Interval = 250
        self.timer.Tick += self.tick
        self.timer.Start()
        if service.settings['floating_window']:
            self.show()

    @staticmethod
    def background(fn):
        def run():
            try: fn()
            except Exception: logging.exception('Floating companion action failed')
        threading.Thread(target=run, daemon=True).start()

    def bounds(self):
        from System.Windows.Forms import Screen
        area = Screen.FromControl(self.form).WorkingArea
        return area.Left, area.Top, area.Right, area.Bottom

    def restore_position(self):
        from System.Windows.Forms import Screen
        a = Screen.PrimaryScreen.WorkingArea
        x, y = a.Right-135, a.Top+180
        try:
            saved = json.loads(self.path.read_text('utf-8'))
            candidate = self.Point(int(saved['x']), int(saved['y']))
            screen = Screen.FromPoint(candidate).WorkingArea
            x = max(screen.Left, min(candidate.X, screen.Right-self.form.Width))
            y = max(screen.Top, min(candidate.Y, screen.Bottom-self.form.Height))
            self.edge = saved.get('edge') if saved.get('edge') in ('left','right','top','bottom') else None
        except (OSError, ValueError, KeyError, TypeError): pass
        self.form.Location = self.Point(x, y)
        self.anchor = (x, y)

    def paint(self, sender, event):
        from System.Drawing import Rectangle, SolidBrush
        from System.Drawing.Drawing2D import InterpolationMode, SmoothingMode
        g = event.Graphics
        g.InterpolationMode = InterpolationMode.HighQualityBicubic
        g.SmoothingMode = SmoothingMode.AntiAlias
        g.DrawImage(self.logo, Rectangle(6, 0, 92, 114))
        brush = SolidBrush(self.Color.FromArgb(250, 239, 213))
        ink = SolidBrush(self.Color.FromArgb(109, 67, 40))
        try:
            g.FillEllipse(brush, 17, 104, 70, 27)
            g.DrawString(self.mood, self.font, ink, 25.0, 106.0)
        finally:
            brush.Dispose(); ink.Dispose()
        if self.tucked:
            tab = SolidBrush(self.Color.FromArgb(221, 110, 62))
            try:
                if self.edge=='left': g.FillRectangle(tab, self.form.Width-18, 0, 18, self.form.Height)
                elif self.edge=='right': g.FillRectangle(tab, 0, 0, 18, self.form.Height)
                elif self.edge=='top': g.FillRectangle(tab, 0, self.form.Height-18, self.form.Width, 18)
                elif self.edge=='bottom': g.FillRectangle(tab, 0, 0, self.form.Width, 18)
            finally: tab.Dispose()

    def command(self, command):
        def run():
            self.window.show()
            self.window.restore()
            self.window.evaluate_js('window.dispatchEvent(new CustomEvent("ying-command",{detail:'+json.dumps(command)+'}))')
        self.background(run)

    def toggle_camera(self):
        def run():
            try:
                if self.service.camera.running: self.service.stop_camera()
                else: self.service.start_camera()
            except Exception as exc:
                self.service.notify('error', str(exc))
        self.background(run)

    def show(self):
        self.untuck()
        if not self.form.Visible:
            self.form.Show()

    def untuck(self):
        if self.tucked:
            x, y = dock_position(self.bounds(), (self.form.Width, self.form.Height), self.anchor, self.edge)
            self.form.Location = self.Point(x, y)
            self.tucked = False
            self.form.Invalidate()
        self.last_hover = time.monotonic()

    def enter(self, *_):
        self.hovering = True
        self.untuck()

    def leave(self, *_):
        self.hovering = False
        self.last_hover = time.monotonic()

    def down(self, sender, e):
        from System.Windows.Forms import MouseButtons
        if e.Button == MouseButtons.Left:
            self.untuck()
            point = self.form.PointToScreen(e.Location)
            self.drag_start = (point.X, point.Y, self.form.Left, self.form.Top)
            self.dragged = False
            self.form.Capture = True

    def move(self, sender, e):
        if self.drag_start:
            px, py, x, y = self.drag_start
            point = self.form.PointToScreen(e.Location)
            dx, dy = point.X-px, point.Y-py
            if abs(dx)+abs(dy)>5: self.dragged=True
            if self.dragged:
                self.form.Location = self.Point(x+dx, y+dy)

    def up(self, *_):
        if not self.drag_start: return
        self.drag_start = None
        self.form.Capture = False
        if not self.dragged:
            return
        l,t,r,b = self.bounds()
        f=self.form
        distances={'left':max(0,f.Left-l), 'right':max(0,r-f.Right), 'top':max(0,f.Top-t), 'bottom':max(0,b-f.Bottom)}
        edge=min(distances,key=distances.get)
        self.edge=edge if distances[edge]<32 else None
        self.anchor=dock_position((l,t,r,b),(f.Width,f.Height),(f.Left,f.Top),self.edge)
        f.Location=self.Point(*self.anchor)
        self.last_hover=time.monotonic()
        self.path.write_text(json.dumps({'x':self.anchor[0],'y':self.anchor[1],'edge':self.edge}),'utf-8')

    def double_click(self, sender, e):
        from System.Windows.Forms import MouseButtons
        if e.Button == MouseButtons.Left and not self.dragged:
            self.command('home')

    def tick(self, *_):
        if not self.service.settings['floating_window']:
            if self.form.Visible: self.form.Hide()
            return
        if not self.form.Visible: self.show()
        r=self.service.latest_emotion
        mood={'happy':'^ᴗ^','calm':'•ᴗ•','tired':'－ω－','low':'˘ω˘','unknown':'•ω•'}.get((r or {}).get('mood'),'•ω•')
        if not self.service.camera.running: mood='z Z'
        elif not r or r.get('confidence',0)<.6: mood='•ω•'
        if mood!=self.mood:
            self.mood=mood; self.form.Invalidate()
        now=time.monotonic()
        if self.menu.Visible or self.drag_start:
            self.last_hover=now
            return
        if not self.hovering and self.edge and not self.tucked and now-self.last_hover>1.2:
            self.form.Location=self.Point(*dock_position(self.bounds(),(self.form.Width,self.form.Height),self.anchor,self.edge,True))
            self.tucked=True
            self.form.Invalidate()

    def self_test(self):
        """Explicit --smoke-test only: native click semantics and edge docking."""
        from System.Windows.Forms import MouseButtons, MouseEventArgs
        saved = (self.form.Location, self.anchor, self.edge, self.tucked, self.hovering)
        checks = {'topmost': bool(self.form.TopMost), 'menu_items': self.menu.Items.Count}
        original_command = self.command
        commands = []
        self.command = commands.append
        try:
            self.enter()
            checks['no_hover_tooltip'] = not hasattr(self, 'tooltip')
            click = MouseEventArgs(MouseButtons.Left, 1, 30, 40, 0)
            self.down(self.form, click)
            self.up(self.form, click)
            checks['single_click_does_not_open'] = not commands
            self.double_click(self.form, MouseEventArgs(MouseButtons.Left, 2, 30, 40, 0))
            checks['left_double_click_opens'] = commands == ['home']
            self.double_click(self.form, MouseEventArgs(MouseButtons.Right, 2, 30, 40, 0))
            checks['right_click_menu_only'] = commands == ['home'] and self.form.ContextMenuStrip is not None
            self.down(self.form, MouseEventArgs(MouseButtons.Left, 1, 30, 40, 0))
            before = (self.form.Left,self.form.Top)
            self.move(self.form, MouseEventArgs(MouseButtons.Left, 0, 60, 55, 0))
            checks['drag_moves'] = (self.form.Left,self.form.Top) == (before[0]+30,before[1]+15)
            self.drag_start = None
            self.form.Capture = False
            for edge in ('left','right','top','bottom'):
                self.edge = edge
                self.hovering = False
                self.tucked = False
                bounds = self.bounds()
                self.anchor = dock_position(bounds,(self.form.Width,self.form.Height),saved[1],edge)
                self.form.Location = self.Point(*self.anchor)
                self.last_hover = time.monotonic()-3
                self.tick()
                expected = dock_position(bounds,(self.form.Width,self.form.Height),self.anchor,edge,True)
                checks[edge+'_hide'] = self.tucked and (self.form.Left,self.form.Top)==expected
                self.form.Refresh()
                self.untuck()
                checks[edge+'_reveal'] = not self.tucked and (self.form.Left,self.form.Top)==self.anchor
        finally:
            self.command = original_command
            self.form.Location, self.anchor, self.edge, self.tucked, self.hovering = saved
            self.last_hover = time.monotonic()
            self.form.Invalidate()
        return checks

    def close(self):
        self.timer.Stop()
        self.form.Close()
        self.logo.Dispose()
        self.font.Dispose()
