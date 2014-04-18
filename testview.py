from system import *
import sys, pdb

class TestView(object):
    def __init__(self, document):
        self.document = document
        self.top = document.top()
        self.block = Block()
        self.block.height = document.height
        self.block.width = document.width
        # self.block.attach(Text('Hello'))
        ba = Block()
        bb = Block()
        ba.attach([Text('Hello World'), Newline(), Text('You\'re beautiful')])
        bb.attach([Text('I am your fatherdddddddddddddddddddddddddddddddddddddddd'), Newline(), Text('Yes'), Newline(), Text('I am')])

        # ba.absolute = True
        # bb.absolute = True
        # ba.pos_x = 5
        # ba.pos_y = 2
        # bb.pos_x = 30
        # bb.pos_y = 1
        self.block.attach(ba)
        self.block.attach(bb)
        self.document.attach(self.block)


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
