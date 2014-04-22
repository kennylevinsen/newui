from system import *
import sys, pdb

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
        self.editor.margin_left = 0
        self.editor.margin_bottom = 1

        self.cursor = Block()
        self.cursor.pos_x = 10
        self.cursor.pos_y = 0
        curstyle = Style()
        curstyle.bg_color = 'white'
        curstyle.fg_color = 'black'
        curstyle.attach(Text('K'))
        self.cursor.attach(curstyle)
        self.editor.attach(self.cursor)

        self.cursor_x = 0
        self.cursor_y = 0

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

        self.document.attachevent(self.callback)

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
        self.cursor.pos_x = self.cursor_x
        self.cursor.pos_y = self.cursor_y
        self.cursor._notify()

    def callback(self, e):
        if e.type == 'draw':
            c = e.args[0]
            self.current.content += c
            if c == ' ':
                self.current = self.editor.attach(Text(''))
            self.cursor_x += 1
            self.update_cursor()
        elif e.type == 'delete':
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
            self.cursor_y += 1
            if self.cursor_y >= self.document.height:
                self.scroll += 1
                self.cursor_y = self.document.height-1
            self.update_cursor()
            self.update_gutter(self.scroll)
        elif e.type == 'cursor_up':
            self.cursor_y -= 1
            if self.cursor_y < 0:
                self.scroll -= 1
                self.cursor_y = 0
            self.update_cursor()
            self.update_gutter(self.scroll)
        elif e.type == 'cursor_left':
            self.cursor_x -= 1
            if self.cursor_x < 0:
                self.cursor_y -= 1
                self.cursor_x = self.document.width
            self.update_cursor()
        elif e.type == 'cursor_right':
            self.cursor_x += 1
            if self.cursor_x > self.document.width:
                self.cursor_y += 1
                self.cursor_x = 0
        elif e.type == 'resize':
            self.bottom.pos_y = self.document.height
            self.update_gutter(self.scroll)
            # self.update_text('    Resizing...')


s = System()
try:
    a = s.getdocument()
    v = View(a)
    s.start()
except KeyboardInterrupt:
    s.cleanup()
except Exception as e:
    s.cleanup()
    print(e)
    pdb.post_mortem(sys.exc_traceback)
