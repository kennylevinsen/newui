import select, sys, termios, fcntl, signal, os
from pyte import ByteStream
from terminal import Terminal
from document import *

class ByteStream(ByteStream):
    def __init__(self, cb):
        super(ByteStream, self).__init__()
        self.cb = cb

    def dispatch(self, event, *args, **kwargs):
        self.cb(Event(event, args, kwargs))
        if kwargs.get('reset', True):
            self.reset()

class Screen(object):
    'Screen buffer'
    def __init__(self, height, width):
        self.height = height
        self.width = width
        self.lines = [[None for y in range(width)] for i in range(height)]

    def set(self, x, y, val):
        self.lines[y][x] = val

    def get(self, x, y):
        return self.lines[y][x]

    def compile(self, other=None):
        if other is None:
            return self.compile_full()

        if self.height != other.height or self.width != other.width:
            return self.compile()

        changed_coords = []
        for y in range(0, self.height):
            for x in range(0, self.width):
                old_char = other.lines[y][x]
                new_char = self.lines[y][x]
                if old_char != new_char:
                    changed_coords.append((x, y))

        res = []
        prev_x = 0
        prev_y = 0
        for x,y in changed_coords:
            c = self.lines[y][x]
            if y == prev_y and x == prev_x + 1:
                res.append(c)
            else:
                if c is None:
                    c = ' '
                res.append('\x1b[%d;%dH%s' % (y+1, x+1, c))
        return ''.join(res)

    def compile_full(self):
        s = []
        for i,line in enumerate(self.lines):
            l = []
            for c in line:
                if c is None:
                    l.append(' ')
                else:
                    l.append(c)
            s.append('\x1b[%d;1H%s' % (i+1, ''.join(l)))
        return ''.join(s)


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
        styles = ['']
        screen = Screen(height, width)

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
            lx, ly = width-cx, height-cy

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
            lx, ly = width-cx, height-cy
            lstyle = ''.join(styles)

            for c in obj.content:
                if y_off + cy >= height:
                    break
                screen.set(x_off+cx, y_off+cy, lstyle+c+Terminal.reset())
                if x_off + cx == width -1:
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
            p = ''
            if obj.color:
                p += Terminal.fcolor(obj.color, obj.bright)
            if obj.bg_color:
                p += Terminal.bcolor(obj.bg_color, obj.bg_bright)
            styles.append(p)
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
        self.newscreen()

    def updatehook(self, obj):
        self.render(obj)

    def render(self, obj=None):
        if self.document.body is None:
            return
        h, w = self.document.height, self.document.width
        doc = self.renderer.render(h, w)
        sys.stdout.write(doc)
        sys.stdout.flush()

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
        try:
            import signal
            signal.signal(signal.SIGWINCH, lambda s,f: self.rescale())
            signal.signal(signal.SIGCONT, lambda s,f: self.restore())
        except:
            raise

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
