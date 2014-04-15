from terminal import Terminal
from document import *
import select,sys,termios,fcntl,signal,pyte,pprint,os,time

class ByteStream(pyte.ByteStream):
    def __init__(self, cb):
        super(ByteStream, self).__init__()
        self.cb = cb

    def dispatch(self, event, *args, **kwargs):
        self.cb(Event(event, args, kwargs))
        if kwargs.get('reset', True):
            self.reset()


class Renderer(object):
    def __init__(self, o):
        self.obj = o
        self.doc = ''
        self.box_stack = []
        self.cur_pos = []

    def render(self, height, width, tabstop=4, obj=None):
        self.doc = '\x1b[2J'
        obj = self.obj.body
        self.box_stack = [(height, width, 0, 0)]
        self.cur_pos = [(0,0)]
        self.wrapping = [('', '')]

        def split_text(t, width, lx):
            parts = []
            l = len(t)
            parts.append(t[:lx])
            while lx < l:
                parts.append(t[lx:lx+width])
                lx += width
            return parts

        def block(obj):
            height, width, x_off, y_off = self.box_stack[-1]
            cx, cy = self.cur_pos[-1]
            lx, ly = width-cx, height-cy

            height = height if obj.height is None else obj.height
            width = width if obj.width is None else obj.width
            if obj.absolute:
                x_off = obj.pos_x
                y_off = obj.pos_y
            else:
                x_off = cx
                y_off = cy

            x_off += obj.margin_left
            y_off += obj.margin_top
            height -= obj.margin_bottom + obj.margin_top
            width -= obj.margin_left + obj.margin_right

            self.cur_pos.append((0,0))
            self.box_stack.append((height, width, x_off, y_off))

            obj.enter(selector)

            self.box_stack.pop()
            self.cur_pos.pop()

        def text(obj):
            height, width, x_off, y_off = self.box_stack[-1]
            cx, cy = self.cur_pos[-1]
            lx, ly = width-cx, height-cy
            prefix, postfix = self.wrapping[-1]

            parts = split_text(obj.content, width, lx)
            for i in parts:
                if cx >= width or cy >= height:
                    break
                self.doc += '%s\x1b[%d;%dH%s%s' % (prefix, y_off+cy+1, x_off+cx+1, i, postfix)
                if len(i) == width:
                    cx = 0
                    cy += 1
                else:
                    cx += len(i)
            self.cur_pos[-1] = (cx, cy)


        def newline(obj):
            cx, cy = self.cur_pos[-1]
            self.cur_pos[-1] = (0, cy + 1)

        def tab(obj):
            height, width, x_off, y_off = self.box_stack[-1]
            cx, cy = self.cur_pos[-1]
            diff = tabstop - (cx % tabstop)
            # diff = tabstop - (len(self.doc[-1]) % tabstop)
            if cx + diff > width:
                cy += 1
                cx = diff
            else:
                cx += diff
            self.cur_pos[-1] = (cx, cy)

        def style(obj):
            post, pre = self.wrapping[-1]
            p = ''
            if obj.color:
                p += Terminal.fcolor(obj.color, obj.bright)
            if obj.bg_color:
                p += Terminal.bcolor(obj.bg_color, obj.bg_bright)
            if post == '':
                self.wrapping.append((p, Terminal.reset()))
            else:
                self.wrapping.append((p, Terminal.reset()+post))
            obj.enter(selector)
            self.wrapping.pop()


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
        return self.doc

class System(object):
    def __init__(self):
        self.document = Document()
        self.renderer = Renderer(self.document)
        self.document.updatehook = self.updatehook
        self.oldattrs = None
        self._scroll = 0
        self.bytestream = ByteStream(self.document.event)

        self.document.setdimensions(*self.getdimensions())
        self.setup()
        time.sleep(0.1)
        self.newscreen()

    def updatehook(self, obj):
        self.render(obj)

    def render(self, obj=None):
        if self.document.body is None:
            return
        h, w = self.document.height, self.document.width
        self.renderer.render(h, w, obj=obj)
        # pprint.pprint(self.renderer.doc)
        try:
            sys.stdout.write(self.renderer.doc)
            sys.stdout.flush()
        except:
            pass

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

class TestView(object):
    def __init__(self, document):
        self.document = document
        self.top = document.top()
        self.block = Block()
        self.block.height = 100
        self.block.width = 100
        # self.block.attach(Text('Hello'))
        ba = Block()
        bb = Block()
        ba.attach([Text('Hello World'), Newline(), Text('You\'re beautiful')])
        bb.attach([Text('I am your father'), Newline(), Text('Yes'), Newline(), Text('I am')])

        ba.absolute = True
        bb.absolute = True
        ba.pos_x = 5
        ba.pos_y = 2
        bb.pos_x = 30
        bb.pos_y = 1
        self.block.attach(ba)
        self.block.attach(bb)
        self.document.attach(self.block)

class View(object):
    def __init__(self, document):
        self.document = document
        self.top = document.top()

        self.block = Block()
        self.gutter = Block()
        self.editor = Block()
        self.bottom = Block()
        self.block.attach(self.gutter)
        self.block.attach(self.editor)
        self.block.attach(self.bottom)

        self.gutter.width = 5
        self.editor.margin_left = 6
        self.editor.margin_bottom = 1
        self.gutter.margin_bottom = 1

        self.gutter.attach(Node())

        self.bottom.absolute = True
        self.bottom.height = 1
        self.bottom.pos_y = self.document.height
        self.bottom.attach(Text('    newui'))


        self.document.attach(self.block)
        self.scroll = 1
        self.current = self.editor.attach(Text(''))
        self.update_gutter(self.scroll)
        self.rawdata = ''

    def update_gutter(self, start=1):
        # Set width
        digits = len(str(self.document.height+1+start))+1
        fmt = '% '+str(digits)+'d '
        self.gutter.width = digits + 1
        self.editor.margin_left = digits + 2
        # Generate labels
        a = [Text(fmt % i) for i in range(start, self.document.height+start)]
        self.gutter.detach(index=0, _notify=False)

        # Create elements
        g_style = Style()
        g_style.bg_color = 'white'
        g_style.color = 'black'
        g_style.attach(a)

        # Finalize
        self.gutter.attach(g_style)

    def update_modeline(self, text):
        self.bottom.detach(index=0, _notify=False)
        self.bottom.attach(Text(text))

    def callback(self, e):
        if e.type == 'draw':
            c = e.args[0]
            self.current.content += c
            if c == ' ':
                self.current = self.editor.attach(Text(''))
        elif e.type == 'backspace':
            if self.current.type != 'text' or self.current.content == '':
                self.editor.detach(self.current)
                self.current = None
                while self.current is None or self.current.type not in ('text', 'newline', 'tab'):
                    try:
                        self.editor.detach(index=-1)
                        self.current = self.editor.children[-1]
                    except:
                        self.current = self.editor.attach(Text(''))
                        break
            else:
                self.current.content = self.current.content[:-1]
        elif e.type == 'linefeed':
            self.editor.attach(Newline())
            self.current = self.editor.attach(Text(''))
        elif e.type == 'tab':
            self.editor.attach(Tab())
            self.current = self.editor.attach(Text(''))
        elif e.type == 'cursor_down':
            self.scroll += 1
            self.update_gutter(self.scroll)
        elif e.type == 'cursor_up':
            self.scroll -= 1
            if self.scroll < 1: self.scroll = 1
            self.update_gutter(self.scroll)
        elif e.type == 'resize':
            self.bottom.pos_y = self.document.height
            self.update_gutter(self.scroll)
            self.update_text('    Resizing...')


s = System()
try:
    a = s.getdocument()
    v = View(a)
    a.attachevent(v.callback)
    # b = TestView(a)
    s.start()
except:
    s.cleanup()
    raise
