from __future__ import absolute_import, division, print_function, unicode_literals
from string import printable

class Terminal(object):
    colors = {
        'black': 0,
        'red': 1,
        'green': 2,
        'yellow': 3,
        'blue': 4,
        'magenta': 5,
        'cyan': 6,
        'white': 7,
        'default': 9
    }
    @staticmethod
    def cursor_move(x,y):
        return ('\x1b[%d;%dH' % (y,x))

    @staticmethod
    def cursor_horiz_move(x):
        return '\x1b[%dG'

    @staticmethod
    def cursor_hide():
        return '\x1b[?25l'

    @staticmethod
    def cursor_show():
        return '\x1b[?25h'

    @staticmethod
    def clear_line():
        return '\x1b[2'

    @staticmethod
    def sgr(d):
        return '\x1b[%dm' % d

    @staticmethod
    def reset():
        return Terminal.sgr(0)

    @staticmethod
    def bold():
        return Terminal.sgr(1)

    @staticmethod
    def underline(p):
        if p:
            return Terminal.sgr(4)
        else:
            return Terminal.sgr(24)

    @staticmethod
    def fcolor(color, bright=False):
        if bright:
            return Terminal.sgr(90+Terminal.colors[color])
        else:
            return Terminal.sgr(30+Terminal.colors[color])

    @staticmethod
    def bcolor(color, bright=False):
        if bright:
            return Terminal.sgr(100+Terminal.colors[color])
        else:
            return Terminal.sgr(40+Terminal.colors[color])
