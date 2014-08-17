import IPython
import colorsys
import collections
import math

from grassroots import grassroots as gr 

class Color(object):
    def __init__(self, r=None, g=None, b=None, h=None, s=None, v=None, a=1.0):
        self.r = r
        self.g = g
        self.b = b

        self.h = h
        self.s = s
        self.v = v

        self.a = a

        if r is None and g is None and b is None:
            self.rgb_from_hsv()
        if h is None and s is None and v is None:
            self.hsv_from_rgb()
        if any([x is None for x in [self.h, self.s, self.v, self.r, self.g, self.b]]):
            raise ValueError("Invalid color specification.")

    def set_rgb(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b
        self.hsv_from_rgb()

    def set_hsv(self, h, s, v):
        self.h = h
        self.s = s
        self.v = v
        self.rgb_from_hsv()

    def hsv_from_rgb(self):
        self.h, self.s, self.v = colorsys.hsv_to_rgb(self.r, self.g, self.b)

    def rgb_from_hsv(self):
        self.r, self.g, self.b = colorsys.hsv_to_rgb(self.h, self.s, self.v)

    def __str__(self):
        return self.html_rgb

    def __repr__(self):
        return self.html_rgb

    @property
    def html_rgb(self):
        f = lambda x: int(round(x * 255))
        return "rgb({}, {}, {})".format(f(self.r), f(self.g), f(self.b))

class LightStrip(gr.Blade):
    sid = gr.Field(0)
    copies = gr.Field(1)

    def __init__(self, sid, length=20, copies=1):
        self.length = length
        self.colors = [Color(r=i / float(self.length), g=0.2, b=0.2) for i in range(self.length)]
        self.sid = sid
        self.copies = copies

    @gr.PropertyField
    def html_colors(self):
        return [c.html_rgb for c in self.colors]

    def __repr__(self):
        return "<LightStrip: id={}, len={}>".format(self.sid, len(self))

    def __str__(self):
        return repr(self)

    def __len__(self):
        return self.length
