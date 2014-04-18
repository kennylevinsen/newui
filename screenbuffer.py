
class ScreenBuffer(object):
    '''Screen buffer

    Use of this screen buffer allows for optimized differential rendition of the screen, given the previously rendered screen object.

    Optimized rendition is enabled when compile is given a previous screen object, as it enables differential rendition. During this type of partial rendering, a lot of cursor moves can occur. This is optimized by calculating the tradeoff of issuing a cursor-move, compared to just rendering the characters in between. This makes this renderer very bandwidth efficient.

    In the future, it will also enable optimizing graphics modes, to avoid issuing bogus mode set/reset commands.'''
    def __init__(self, height, width):
        '''Initialize a screen buffer of height * width

        :param int height: The height of the screen buffer
        :param int width: The width of the screen buffer'''
        self.height = height
        self.width = width
        self.lines = [[' ' for y in range(width)] for i in range(height)]

    def set(self, x, y, val):
        '''Set a cell in the screen buffer

        :param int x: The x coordinate
        :param int y: The y coordinate
        :param str val: The value to set'''
        self.lines[y][x] = val

    def get(self, x, y):
        '''Get a cell from the screen buffer

        :param int x: The x coordinate
        :param int y: The y coordinate
        :returns: str -- The content of the cell'''
        return self.lines[y][x]

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
        if self.height != old.height or self.width != old.width:
            return self.compile()

        # Compile diff
        changed_coords = []
        for y in range(0, self.height):
            for x in range(0, self.width):
                old_char = old.lines[y][x]
                new_char = self.lines[y][x]
                if old_char != new_char:
                    changed_coords.append((x, y))

        # We need to keep a track
        res = []
        origin_move = False
        prev_x = -1
        prev_y = -1
        for x,y in changed_coords:
            if origin_move and y == prev_y and x == prev_x + 1:
                # Single-character move
                # Cursor moves forward by itself, so no work necessary
                res.append(self.lines[y][x])
            elif origin_move and y == prev_y and x < prev_x + 6:
                # Multi-character move
                # Short enough that it's faster to just render
                # everything up to this character to move the cursor
                res.append(''.join(self.lines[y][prev_x+1:x+1]))
            else:
                # Long multi-character move, or first move
                # Use a cursor move
                c = self.lines[y][x]
                res.append('\x1b[%d;%dH%s' % (y+1, x+1, c))
                origin_move = True
        return ''.join(res)

    def compile_full(self):
        '''Compiles a regular render-string
        :returns: str - The rendered command string'''
        s = []
        for i,line in enumerate(self.lines):
            s.append('\x1b[%d;1H%s' % (i+1, ''.join(line)))
        return ''.join(s)
