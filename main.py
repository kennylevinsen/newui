from system import *
import sys, pdb

class View(object):
    def __init__(self, system):
        self.system = system
        self.document = system.getdocument()
        self.top = self.document.top()

        self.block  = Block()
        self.gutter = Block()
        self.editor = Block()
        self.bottom = Block()
        self.cursor = Block()

        self.cursor_x = 0
        self.cursor_y = 0
        self.scroll = 1

        self.setup_cursor(self.cursor)
        self.setup_modeline(self.bottom)
        self.setup_gutter(self.gutter)

        self.block.attach(self.gutter)
        self.block.attach(self.editor)
        self.block.attach(self.bottom)
        self.editor.attach(self.cursor)

        self.document.attach(self.block)
        self.current = self.editor.attach(Text(''))

        self.document.attachevent(self.callback)

    def setup_modeline(self, mode):
        mode.absolute = True
        mode.height = 1
        mode.margin_top = self.document.height - 1
        mode.attach(Text('    newui'))

    def setup_cursor(self, cursor):
        cursor.margin_left = self.cursor_x
        cursor.margin_right = self.cursor_y

        style = StyleOverride()
        style.bg_color = 'white'
        style.color = 'black'

        cursor.attach(style)

    def setup_gutter(self, gutter):
        gutter.width = 5
        gutter.margin_bottom = 1
        gutter.attach(Node())
        self.update_gutter(self.scroll)

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

    def update_cursor(self):
        self.cursor.margin_left = self.cursor_x
        self.cursor.margin_top = self.cursor_y
        self.cursor._notify()

    def up(self):
        self.cursor_y -= 1
        if self.cursor_y < 0:
            self.scroll -= 1
            self.cursor_y = 0
        self.update_cursor()
        self.update_gutter(self.scroll)

    def down(self):
        self.cursor_y += 1
        if self.cursor_y >= self.document.height-1:
            self.scroll += 1
            self.cursor_y = self.document.height-2
        self.update_cursor()
        self.update_gutter(self.scroll)

    def back(self):
        self.cursor_x -= 1
        if self.cursor_x <= 0:
            if self.cursor_y > 0:
                self.up()
                self.cursor_x = self.document.width-self.gutter.width
            else:
                self.cursor_x = 0
        self.update_cursor()

    def forward(self):
        self.cursor_x += 1
        if self.cursor_x >= self.document.width-self.gutter.width:
            if self.cursor_y < self.document.height-2:
                self.down()
                self.cursor_x = 0
            else:
                self.cursor_x = self.document.width-5
        self.update_cursor()

    def write(self, c):
        self.current.content += c
        # if c == ' ':
        #     self.current = self.editor.attach(Text(''))
        self.cursor_x += 1
        self.update_cursor()

    def backspace(self):
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

    def callback(self, e):
        if e.type == 'draw':
            self.write(e.args[0])
        elif e.type == 'delete':
            self.backspace()
        elif e.type == 'linefeed':
            self.editor.attach(Newline())
            self.current = self.editor.attach(Text(''))
        elif e.type == 'tab':
            self.editor.attach(Tab())
            self.current = self.editor.attach(Text(''))
        elif e.type == 'cursor_down':
            self.down()
        elif e.type == 'cursor_up':
            self.up()
        elif e.type == 'cursor_back':
            self.back()
        elif e.type == 'cursor_forward':
            self.forward()
        elif e.type == 'resize':
            self.bottom.pos_y = self.document.height
            self.update_gutter(self.scroll)
        elif e.type == 'function_key' and e.args[0] == 15:
            self.system.render(differential=False)


s = System()
try:
    v = View(s)
    s.start()
except KeyboardInterrupt:
    s.cleanup()
except Exception as e:
    s.cleanup()
    print(e)
    pdb.post_mortem(sys.exc_traceback)
