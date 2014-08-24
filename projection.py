import collections
import colorsys
import doitlive
import math

from grassroots import grassroots as gr
from lights import Color, rng

Point = collections.namedtuple("Point", ["x", "y"])
# Vector is exactly the same, but it's more readable
Vector = collections.namedtuple("Vector", ["x", "y"])

def points_along(start, end, length):
    if length == 1:
        # Return the midpoint 
        return Point(x=(start.x + end.x)/2, y=(start.y + end.y)/2)
    dx = (end.x - start.x) / float(length - 1)
    dy = (end.y - start.y) / float(length - 1)
    sx = start.x
    sy = start.y
    return [Point(x=sx + dx * i, y=sy + dy * i) for i in range(length)]
    

def eff_diamond(color, point, size):
    def d(c, p, state):
        if abs(p.x - point.x) + abs(p.y - point.y) <= size:
            return color
        return c
    return d

def eff_circle(color, point, size):
    mc = color.copy()
    alpha = mc.a
    def d(c, p, state):
        rad = (p.x - point.x) ** 2 + (p.y - point.y) ** 2
        rads = rng(rad / float(size) ** 2)
        mc.a = alpha * (1.0 - rads)
        return mc.mix_onbg(c)
    return d

def eff_plane(color, point, vector, fade=0.2):
    mc = color.copy()
    alpha = mc.a
    def d(c, p, state):
        dist  = vector.x * (p.x - point.x) + vector.y * (p.y - point.y)
        if dist <= 0:
            return c
        if abs(dist) >= abs(fade):
            return color
        mc.a = abs(dist / fade)
        return mc.mix_onbg(c)
    return d

def eff_solid(color):
    def d(c, p, state):
        return color.mix_onbg(c)
    return d

def eff_rainbow(vector, rate=5.):
    def d(c, p, state):
        time = state.get("time", 0.)
        offset = (time / float(rate))
        hue = ((p.x - offset * vector.x) + (p.y - offset * vector.y)) % 1.0
        mc = Color(h = hue, s=1.0, v=1.0, a=0.5)
        return mc.mix_addhue(c)
    return d

def eff_colorout(color, key, rate=0.05):
    mc = color.copy()
    alpha = mc.a
    def d(c, p, state):
        st = state.get(key, None)
        if st is None:
            st = state[key] = 0
        last_st = state.get(key + "_last", st)
        now_time = state.get("time", 0.0)
        start_time = state.get(key + "_start", None)
        if start_time is None:
            start_time = now_time
        if last_st != st:
            start_time = state[key + "_start"] = now_time

        elapsed_time = now_time - start_time
        part_complete = elapsed_time * rate
        if part_complete < 0.0:
            part_complete = 0.0
        if part_complete > 1.0:
            st = state[key] = 0

        state[key + "_last"] = st
        mc.a = part_complete * alpha
        return mc.mix_onbg(c)
    return d

class Plane(gr.Blade):
    def __init__(self):
        # Effect :: (Color -> Point -> Color)
        self.effects = []
        self.background_color = Color(r=0, g=0, b=0, a=0)
        self.state = {}

    def render(self, start, end, length):
        # Renders the stack of layers along the line from `start` to `end`
        # Returns a list of colors of length `length`
        return map(self.render_at, points_along(start, end, length))

    def render_at(self, point):
        # Renders a single point by applying effects stack
        return reduce(lambda color, fn: fn(color, point, self.state), self.effects, self.background_color)

    def render_strip(self, strip):
        pairs = zip(s, s[1:])
        colors = []
        for (start, l), (end, _l) in pairs:
            colors.append(render(start, end, l))
        strip.colors = colors


