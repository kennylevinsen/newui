from __future__ import print_function
import select, signal, sys, termios, fcntl, signal, os
from pyte import ByteStream
from terminal import Terminal
from document import *
from screenbuffer import *
from collections import deque

class ByteStream(ByteStream):
    def __init__(self, cb):
        super(ByteStream, self).__init__()
        self.cb = cb
        self.csi['~'] = 'function_key'
        self.basic['\x7f'] = 'delete'

    def dispatch(self, event, *args, **kwargs):
        self.cb(Event(event, args, kwargs))
        if kwargs.get('reset', True):
            self.reset()


class Renderer(object):
    """
The DOM->Terminal renderer.

It currently traverses the elements, generating a stream of commands on the way. This causes a lot of cursor moves, which is inefficient, and seeing that Terminals are slower than my script (!?), I need to avoid as many commands as possible.

Instead, I have considered having an array per line. Each array represents a character position, and can be set to contain a character + graphics commands.
After rendering to this space, one can identify dirty lines, and generate the command stream from there.

The renderer is still not feature complete, though, which should be of higher priority (It needs to be able to handle blocks in all positions)
"""
    def __init__(self, o):
        self.obj = o
        self.box_stack = []
        self.cur_pos = []
        self.styles = []
        self.screen = None
        self.old_scr = None

    def render(self, height, width, tabstop=4, differential=True):
        obj = self.obj.body
        self.box_stack = [(height, width, 0, 0)]
        self.cur_pos = [(0,0)]
        self.styles = [(None, None)]
        self.screen = ScreenBuffer(height, width)

        self.selector(obj)
        res = self.screen.compile(self.old_scr if differential else None)
        self.old_scr = self.screen
        return res

    def _block(self, obj):
        box_stack = self.box_stack
        cur_pos = self.cur_pos

        height, width, x_off, y_off = box_stack[-1]
        cx, cy = cur_pos[-1]

        height = height if obj.height is None else obj.height
        width = width if obj.width is None else obj.width
        if obj.absolute:
            x_off = obj.pos_x
            y_off = obj.pos_y
        else:
            x_off += cx
            y_off += cy

        x_off += obj.margin_left
        y_off += obj.margin_top
        height -= obj.margin_bottom + obj.margin_top
        width -= obj.margin_left + obj.margin_right

        cur_pos.append((0,0))
        box_stack.append((height, width, x_off, y_off))

        obj.enter(self.selector)

        box_stack.pop()
        cur_pos.pop()

    def _text(self, obj):
        height, width, x_off, y_off = self.box_stack[-1]
        cx, cy = self.cur_pos[-1]
        fstyle, bstyle = self.styles[-1]

        for c in obj.content:
            if cy >= height:
                break
            if cy >= 0:
                self.screen.set(x_off+cx, y_off+cy, c, fstyle, bstyle)
            if cx == width-1:
                cx = 0
                cy += 1
            else:
                cx += 1
        self.cur_pos[-1] = (cx, cy)

    def _newline(self, obj):
        cx, cy = self.cur_pos[-1]
        self.cur_pos[-1] = (0, cy + 1)

    def _tab(self, obj):
        height, width, x_off, y_off = self.box_stack[-1]
        cx, cy = self.cur_pos[-1]
        diff = self.tabstop - (cx % self.tabstop)
        if cx + diff > width:
            cy += 1
            cx = diff
        else:
            cx += diff
        self.cur_pos[-1] = (cx, cy)

    def _style(self, obj):
        f, b = None, None
        if obj.color:
            f = Terminal.fcolor(obj.color, obj.bright)
        if obj.bg_color:
            b = Terminal.bcolor(obj.bg_color, obj.bg_bright)
        self.styles.append((f, b))
        obj.enter(self.selector)
        self.styles.pop()

    def _styleoverride(self, obj):
        height, width, x_off, y_off = self.box_stack[-1]
        if obj.absolute:
            x_off = obj.pos_x
            y_off = obj.pos_y
        x, y = x_off + obj.margin_left, y_off + obj.margin_top

        val, fg, bg, z_index = self.screen.get(x, y)
        if obj.color:
            fg = Terminal.fcolor(obj.color, obj.bright)
        if obj.bg_color:
            bg = Terminal.bcolor(obj.bg_color, obj.bg_bright)

        self.screen.set(x, y, fg=fg, bg=bg, z_index=z_index+10)

    def selector(self, obj):
        try:
            getattr(self, '_'+obj.type)(obj)
        except KeyError:
            return obj.enter(self.selector)

class System(object):
    """
The system class.

This class manages the entire application, from calling the renderer to dispatching of events.
"""
    def __init__(self):
        self.document = Document()
        self.renderer = Renderer(self.document)
        self.document.updatehook = self.updatehook
        self.oldattrs = None
        self._scroll = 0
        self.bytestream = ByteStream(self.document.event)

        self.document.setdimensions(*self.getdimensions())
        self.setup()
        self.setup_signal()
        self.enable_alternate()

        self.pending = deque([])

        waker, wakew = os.pipe()
        self.waker, self.wakew = os.fdopen(waker,'rb',0), os.fdopen(wakew,'wb',0)


        fl = fcntl.fcntl(waker, fcntl.F_GETFL)
        fcntl.fcntl(waker, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def queue(self, cmd):
        self.pending.append(cmd)
        self.wakew.write(b"\x00")

    def handle_queue(self):
        while len(self.pending):
            o = self.pending.popleft()
            if o == 'restore':
                self.restore()
            elif o == 'rescale':
                self.rescale()

    def updatehook(self, obj):
        self.render(obj)

    def render(self, obj=None, _retry=0, differential=True):
        if self.document.body is None:
            return
        h, w = self.document.height, self.document.width
        doc = self.renderer.render(h, w, differential=differential)
        try:
            sys.stdout.write(doc)
            sys.stdout.flush()
        except:
            if _retry < 3:
                return self.render(obj, _retry+1)

    def getdimensions(self):
        h = bytearray(fcntl.ioctl(0, termios.TIOCGWINSZ, '1234'))
        y,x = (h[1] << 8) + h[0], (h[3] << 8) + h[2]
        return y,x

    def rescale(self):
        if self.document:
            self.document.setdimensions(*self.getdimensions())
            self.document.event(Event('resize', None, None))
            self.render(differential=False)

    def restore(self):
        self.cleanup()
        self.setup()
        self.enable_alternate()
        self.rescale()

    def setup_signal(self):
        signal.signal(signal.SIGWINCH, lambda s,f: self.queue('rescale'))
        signal.signal(signal.SIGCONT, lambda s,f: self.queue('restore'))

    def enable_alternate(self):
        sys.stdout.write('\x1b[?25l')
        sys.stdout.write('\x1b[?1049h')
        sys.stdout.flush()

    def disable_alternate(self):
        sys.stdout.write('\x1b[2J')
        sys.stdout.write('\x1b[?1049l')
        sys.stdout.flush()

    def scroll(self, y):
        self._scroll += y

    def setup(self):
        self.oldattrs = termios.tcgetattr(sys.stdin)
        new_attrs = termios.tcgetattr(sys.stdin)
        new_attrs[3] &= ~(termios.ECHO|termios.ICANON)
        new_attrs[6][termios.VMIN] = 1
        new_attrs[6][termios.VTIME] = 0
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, new_attrs)

        # make things non-blocking
        fl = fcntl.fcntl(sys.stdin.fileno(), fcntl.F_GETFL)
        fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def cleanup(self):
        if self.oldattrs is not None:
            termios.tcsetattr(sys.stdin, termios.TCSANOW, self.oldattrs)
        sys.stdout.write(Terminal.cursor_show())
        sys.stdout.flush()
        self.disable_alternate()

        fl = fcntl.fcntl(sys.stdin.fileno(), fcntl.F_GETFL)
        fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, fl & ~os.O_NONBLOCK)

    def start(self):
        self.render()
        while True:
            try:
                i,o,e = select.select((sys.stdin, self.waker), tuple(), tuple())
            except select.error:
                continue

            for s in i:
                if s == sys.stdin:
                    try:
                        c = os.read(sys.stdin.fileno(), 128)
                    except IOError:
                        continue
                    self.bytestream.feed(c)
                elif s == self.waker or len(self.pending) > 0:
                    self.waker.read(1024)
                    self.handle_queue()

    def getdocument(self):
        return self.document
