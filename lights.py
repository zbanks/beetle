import IPython
import collections
import colorsys
import copy
import math
import struct

from grassroots import grassroots as gr 

def rng(x):
    return min(1.0, max(0.0, x))

def intr(x):
    return int(round(x))

class Color(object):
    __slots__ = ["r", "g", "b", "h", "s", "v", "a"]
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

    def copy(self):
        return copy.deepcopy(self)

    def mix_onbg(self, oc):
        blend = lambda t, b: rng((t * self.a) + (b * (1.0 - self.a)))
        alpha = (1 - (1 - self.a) * (1 - oc.a))
        return Color(r=blend(self.r, oc.r), g=blend(self.g, oc.g), b=blend(self.b, oc.b), a=alpha)

    def mix_add(self, oc):
        blend = lambda t, b: rng((t * self.a) + b)
        alpha = oc.a
        return Color(r=blend(self.r, oc.r), g=blend(self.g, oc.g), b=blend(self.b, oc.b), a=alpha)

    def mix_sub(self, oc):
        blend = lambda t, b: rng(b - (t * self.a))
        alpha = oc.a
        return Color(r=blend(self.r, oc.r), g=blend(self.g, oc.g), b=blend(self.b, oc.b), a=alpha)

    def mix_addhue(self, oc):
        blend = lambda t, b: rng((t * self.a) + (b * (1.0 - self.a)))
        alpha = (1 - (1 - self.a) * (1 - oc.a))
        hue = (self.h + oc.h) % 1.0
        return Color(h=hue, s=blend(self.s, oc.s), v=blend(self.v, oc.v), a=alpha)

    def mix_takehue(self, oc):
        blend = lambda t, b: rng((t * self.a) + (b * (1.0 - self.a)))
        alpha = (1 - (1 - self.a) * (1 - oc.a))
        hue = self.h
        return Color(h=hue, s=blend(self.s, oc.s), v=blend(self.v, oc.v), a=alpha)

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

    def hw_export(self):
        #TODO: export to 15-bit RGB
        return 0x8000 | (self.hw_b(self.b) << 10) | (self.hw_g(self.g)) | (self.hw_r(self.r) << 5)

    def hw_r(self, r):
        return intr(self.a * r ** 2.2 * 0x1F)  & 0x1f
    def hw_g(self, g):
        return intr(self.a * g  ** 3.0* 0x1F) & 0x1f
    def hw_b(self, b):
        return intr(self.a * b ** 3.0 * 0x1F) & 0x1f

    def __str__(self):
        return self.html_rgb

    def __repr__(self):
        return self.html_rgb

    @property
    def html_rgb(self):
        f = lambda x: int(round(x * 255 * self.a))
        return "rgb({}, {}, {})".format(f(self.r), f(self.g), f(self.b))


class LightStrip(gr.Blade):
    sid = gr.Field(0)
    copies = gr.Field(1)
    points = gr.Field([])

    def __init__(self, sid, length=20, copies=1, points=None):
        self.length = length
        self.colors = [Color(r=i / float(self.length), g=0.2, b=0.2) for i in range(self.length)]
        self.sid = sid
        self.copies = copies
        self.points = points 

    @gr.PropertyField
    def html_colors(self):
        return [c.html_rgb for c in self.colors]

    def hw_export(self):
        output = []
        for color in self.colors:
            h = color.hw_export()
            output.append(h & 0xFF)
            output.append((h >> 8) & 0xFF)
        return output

    def __repr__(self):
        return "<LightStrip: id={}, len={}>".format(self.sid, len(self))

    def __str__(self):
        return repr(self)

    def __len__(self):
        return self.length
