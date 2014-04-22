from __future__ import print_function
import select, signal, sys, termios, fcntl, signal, os
from pyte import ByteStream
from terminal import Terminal
from document import *
from screenbuffer import *

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
        self.old_scr = None

    def render(self, height, width, tabstop=4):
        obj = self.obj.body
        box_stack = [(height, width, 0, 0)]
        cur_pos = [(0,0)]
        styles = [(None, None)]
        screen = ScreenBuffer(height, width)

        def split_text(t, width, lx):
            parts = []
            l = len(t)
            parts.append(t[:lx])
            while lx < l:
                parts.append(t[lx:lx+width])
                lx += width
            return parts

        def block(obj):
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

            obj.enter(selector)

            box_stack.pop()
            cur_pos.pop()

        def text(obj):
            height, width, x_off, y_off = box_stack[-1]
            cx, cy = cur_pos[-1]
            fstyle, bstyle = styles[-1]

            for c in obj.content:
                if y_off + cy >= height:
                    break
                screen.set(x_off+cx, y_off+cy, c, fstyle, bstyle)
                if x_off + cx == width-1:
                    cx = 0
                    cy += 1
                else:
                    cx += 1
            cur_pos[-1] = (cx, cy)

        def newline(obj):
            cx, cy = cur_pos[-1]
            cur_pos[-1] = (0, cy + 1)

        def tab(obj):
            height, width, x_off, y_off = box_stack[-1]
            cx, cy = cur_pos[-1]
            diff = tabstop - (cx % tabstop)
            if cx + diff > width:
                cy += 1
                cx = diff
            else:
                cx += diff
            cur_pos[-1] = (cx, cy)

        def style(obj):
            f, b = None, None
            if obj.color:
                f = Terminal.fcolor(obj.color, obj.bright)
            if obj.bg_color:
                b = Terminal.bcolor(obj.bg_color, obj.bg_bright)
            styles.append((f, b))
            obj.enter(selector)
            styles.pop()

        def selector(obj):
            if obj.type == 'text':
                return text(obj)
            elif obj.type == 'newline':
                return newline(obj)
            elif obj.type == 'tab':
                return tab(obj)
            elif obj.type == 'block':
                return block(obj)
            elif obj.type == 'style':
                return style(obj)
            return obj.enter(selector)
        selector(obj)
        res = screen.compile(self.old_scr)
        self.old_scr = screen
        return res

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
        self.newscreen()

    def updatehook(self, obj):
        self.render(obj)

    def render(self, obj=None, _retry=0):
        if self.document.body is None:
            return
        h, w = self.document.height, self.document.width
        doc = self.renderer.render(h, w)
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
            self.render()

    def restore(self):
        self.cleanup()
        self.setup()
        self.rescale()
        self.newscreen()

    def setup_signal(self):
        signal.signal(signal.SIGWINCH, lambda s,f: self.rescale())
        signal.signal(signal.SIGCONT, lambda s,f: self.restore())

    def newscreen(self):
        rendering = '\x1b[0m'
        rendering += '\x1b[?25l'
        rendering += '\x1b[1;1H'
        for i in range(self.document.height):
            rendering += ' ' * self.document.width
            if i != self.document.height:
                rendering += '\n\r'
        rendering += '\x1b[1;1H'
        try:
            sys.stdout.write(rendering)
        except:
            pass

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
        # fl = fcntl.fcntl(sys.stdin.fileno(), fcntl.F_GETFL)
        # fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, fl | os.O_NONBLOCK)
        # fl = fcntl.fcntl(sys.stdout.fileno(), fcntl.F_GETFL)
        # fcntl.fcntl(sys.stdout.fileno(), fcntl.F_SETFL, fl | ~os.O_NONBLOCK)

    def cleanup(self):
        self.newscreen()
        if self.oldattrs is not None:
            termios.tcsetattr(sys.stdin, termios.TCSANOW, self.oldattrs)
        sys.stdout.write(Terminal.cursor_show())
        sys.stdout.flush()

    def start(self):
        self.render()
        while True:
            c = sys.stdin.read(1)
            self.bytestream.feed(c)
            # allow monitoring of other tasks
            # try:
            #     i,o,e = select.select([sys.stdin], tuple(), tuple())
            #     for s in i:
            #         if s == sys.stdin:
            #             try:
            #                 c = os.read(sys.stdin.fileno(), 1024)
            #                 self.bytestream.feed(c)
            #             except IOError:
            #                 pass
            # except select.error:
            #     pass

    def getdocument(self):
        return self.document
