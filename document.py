class Event(object):
    def __init__(self, _type, args, flags):
        self._type = _type
        self._args = args
        self._flags = flags

    @property
    def type(self):
        return self._type

    @property
    def args(self):
        return self._args

    @property
    def flags(self):
        return self._flags

class NodeError(RuntimeError):
    pass

class Node(object):
    type = 'none'
    def __init__(self):
        self.children = []
        self.updatehook = None
        self.parent = None

        self.id = None

        self.absolute = False
        self.width = None
        self.height = None
        self.pos_x = 0
        self.pos_y = 0

        self.margin_left = 0
        self.margin_right = 0
        self.margin_top = 0
        self.margin_bottom = 0

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return id(self) == id(other)

    def top(self):
        if self.parent is None:
            return self
        return self.parent.top()

    def _notify(self):
        t = self.top()
        if t.updatehook is not None:
            t.updatehook(self)

    def attach(self, o, index=None, _notify=True):
        if type(o) in (list, tuple):
            for item in o:
                self.attach(item, index, _notify=False)
                if index is not None and index >= 0:
                    index += 1
                self._notify()
            return

        if o.parent is self:
            raise NodeError('Node already attached')

        o.parent = self
        if index is None:
            self.children.append(o)
        else:
            self.children.insert(index, o)
        if _notify: self._notify()
        return o

    def detach(self, o=None, index=None, _notify=True):
        if o is None:
            if index is None:
                raise NodeError('detach requires either object or index')
            try:
                o = self.children[index]
            except:
                raise NodeError('No such index')
        elif type(o) in (list, tuple):
            for item in o:
                self.detach(item, _notify=False)
            self._notify()
            return
        else:
            if index is not None:
                raise NodeError('detach cannot take both object and index')
            if o.parent is not self:
                raise NodeError('Node not attached')

        self.children.remove(o)
        o.parent = None
        if _notify: self._notify()
        return o

    def enter(self, cb):
        for child in self.children:
            cb(child)


class Block(Node):
    type = 'block'


class BachelorNode(Node):
    def attach(self, o):
        raise NodeError('Node is not mature enough to become a parent')

    def detach(self, o):
        raise NodeError('Node is not mature enough to lose a child')


class Text(BachelorNode):
    type = 'text'
    def __init__(self, content=''):
        super(Text, self).__init__()
        self._content = content

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        self._content = value
        self._notify()

class Newline(BachelorNode):
    type = 'newline'


class Tab(BachelorNode):
    type = 'tab'


class Style(Node):
    type = 'style'
    def __init__(self):
        super(Style, self).__init__()
        self._color = None
        self._bright = False
        self._bg_color = None
        self._bg_bright = False

    @property
    def color(self):
        return self._color
    @color.setter
    def color(self, value):
        self._color = value
        self._notify()

    @property
    def bg_color(self):
        return self._bg_color
    @bg_color.setter
    def bg_color(self, value):
        self._bg_color = value
        self._notify()

    @property
    def bright(self):
        return self._bright
    @bright.setter
    def bright(self, value):
        self._bright = value
        self._notify()

    @property
    def bg_bright(self):
        return self._bg_bright
    @bg_bright.setter
    def bg_bright(self, value):
        self._bg_bright = value
        self._notify()



class Document(Node):
    'The document is a special node that may not be used as child'
    def __init__(self):
        self.body = None
        self.width = 0
        self.height = 0
        self._scroll = 0
        self.listeners = []
        self.prerendered = []
        self.dependencies = {}

    @property
    def parent(self):
        'This makes parent read-only'
        return None

    def scroll(self, y):
        self._scroll += y
        if self._scroll < 0:
            self._scroll = 0

    def setdimensions(self, height=None, width=None):
        if self.height is not None:
            self.height = height
        if self.width is not None:
            self.width = width

    def attachevent(self, e):
        if e in self.listeners:
            return
        self.listeners.append(e)

    def detachevent(self, e):
        self.listeners.remove(e)

    def event(self, event):
        for listener in self.listeners:
            listener(event)

    def attach(self, body):
        if self.body is not None:
            self.detach()
        body.parent = self
        self.body = body

    def detach(self):
        self.body.parent = None
        self.body = None

    def getbyid(self, _id, body=None):
        if body is None: body = self.body
        for child in body.children:
            if child.id == _id:
                return child
