from system import *
import sys, pdb

class TestView(object):
    def __init__(self, document):
        self.document = document
        self.top = document.top()
        self.block = Block()
        self.block.height = document.height
        self.block.width = document.width
        self.document.attach(self.block)
        self.l = 0

        self.document.attachevent(self.callback)

    def write(self, text):
        if len(text) >= self.block.width:
            text = text[:self.block.width]
        self.l += 1
        if self.l >= self.block.height:
            self.block.detach(index=0, _notify=False)
            self.block.detach(index=0, _notify=False)
            self.l -= 1
        self.block.attach([Text(text), Newline()])

    def callback(self, e):
        if e.type == 'resize':
            self.block.height = self.document.height
            self.block.width = self.document.width
            self.block._notify()
        self.write('%s: %s, %s' % (e.type, e.args, e.flags))

s = System()
try:
    a = s.getdocument()
    b = TestView(a)
    s.start()
except KeyboardInterrupt:
    s.cleanup()
except:
    s.cleanup()
    pdb.post_mortem(sys.exc_traceback)
