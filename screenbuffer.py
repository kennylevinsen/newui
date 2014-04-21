class ScreenBuffer(object):
    '''Screen buffer

    Use of this screen buffer allows for optimized differential rendition of the screen, given the previously rendered screen object.

    Optimized rendition is enabled when compile is given a previous screen object, as it enables differential rendition. During this type of partial rendering, a lot of cursor moves can occur. This is optimized by calculating the tradeoff of issuing a cursor-move, compared to just rendering the characters in between. This makes this renderer very bandwidth efficient.'''
    def __init__(self, height, width):
        '''Initialize a screen buffer of height * width

        :param int height: The height of the screen buffer
        :param int width: The width of the screen buffer'''
        self._height = height
        self._width = width
        self._lines = [[(' ', None, None) for y in range(width)] for i in range(height)]
        self._prev_modes = (None, None)

    def set(self, x, y, val, fg=None, bg=None):
        '''Set a cell in the screen buffer

        :param int x: The x coordinate
        :param int y: The y coordinate
        :param str val: The value to set
        :param str fg: The foreground mode
        :param str bg: The background mode'''
        self._lines[y][x] = (val, fg, bg)

    def get(self, x, y):
        '''Get a cell from the screen buffer

        :param int x: The x coordinate
        :param int y: The y coordinate
        :returns: tuple -- The content of the cell'''
        return self._lines[y][x]

    def _diff(self, old):
        '''Internal diff calculator between two ScreenBuffers.

        :param ScreenBuffer old: The old ScreenBuffer
        :returns: list -- List of (x, y) tuples of all the changes'''
        changed_coords = []
        for y in range(0, self._height):
            for x in range(0, self._width):
                oc, of, ob = old._lines[y][x]
                nc, nf, nb = self._lines[y][x]
                if (oc, of, ob) != (nc, nf, nb):
                    changed_coords.append((x, y))
        return changed_coords

    def _compile_char(self, x, y, res):
        '''Internal handler for rendering a character with a mode.
        The character is read from internal list of lines.

        :param int x: The x coordinate
        :param int y: The y coordinate
        :param list res: The result list'''
        c, f, b = self._lines[y][x]
        of, ob = self._prev_modes
        if f != of:
            if f is None: res.append('\x1b[39m')
            else: res.append(f)
        if b != ob:
            if b is None: res.append('\x1b[49m')
            else: res.append(b)
        self._prev_modes = (f, b)
        res.append(c)

    def compile(self, old=None):
        '''Compile render-string

        If an older screen instance is provided as argument, it will enable
        differential rendition from that point, allowing for optimal use of
        bandwidth, as well as faster, flicker-free rendition.

        :param ScreenBuffer old: The old screen instance
        :returns: str - The rendered command string'''
        if old is None:
            return self.compile_full()

        # Do not attempt optimized rendition after rescale
        if self._height != old._height or self._width != old._width:
            return self.compile()

        # Compile diff
        changed_coords = self._diff(old)
        self._prev_modes = old._prev_modes

        # We need to keep a track
        res = []
        origin_move = False
        prev_x = -10
        prev_y = -10
        for x,y in changed_coords:
            if origin_move and y == prev_y and x == prev_x + 1:
                # Single-character move
                # Cursor moves forward by itself, so no work necessary
                self._compile_char(x, y, res)
            elif origin_move and y == prev_y and x < prev_x + 6:
                # Multi-character move
                # Short enough that it's faster to just render
                # everything up to this character to move the cursor
                for i in range(prev_x+1, x+1):
                    self._compile_char(i, y, res)
            else:
                # Long multi-character move, or first move
                # Use a cursor move
                res.append('\x1b[%d;%dH' % (y+1, x+1))
                self._compile_char(x, y, res)
                origin_move = True
        return ''.join(res)

    def compile_full(self):
        '''Compiles a regular render-string
        :returns: str - The rendered command string'''
        res = []
        for y in range(self._height):
            res.append('\x1b[0m\x1b[%d;1H' % (y + 1))
            for x in range(self._width):
                self._compile_char(x, y, res)
        return ''.join(res)
