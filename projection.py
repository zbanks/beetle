import collections
import colorsys
import doitlive
import math

from grassroots import grassroots as gr
from lights import Color, rng

Point = collections.namedtuple("Point", ["x", "y"])
# Vector is exactly the same, but it's more readable
Vector = collections.namedtuple("Vector", ["x", "y"])

def norm(v):
    return (v.x ** 2 + v.y ** 2) ** 0.5

def points_along(start, end, length):
    if length == 1:
        # Return the midpoint 
        return Point(x=(start.x + end.x)/2, y=(start.y + end.y)/2)
    dx = (end.x - start.x) / float(length + 1)
    dy = (end.y - start.y) / float(length + 1)
    sx = start.x
    sy = start.y
    return [Point(x=sx + dx * i, y=sy + dy * i) for i in range(1, length+1)]

def timer(state, key, rate=1.0, start=False):
    time = state.get('time', 0.)
    last_time = state.get('last_time__{}'.format(key), time)
    offset = state.get('offset__{}'.format(key), 0.)

    time_delta = time - last_time
    offset += time_delta / float(rate)

    if start:
        offset = 0.0

    state['last_time__{}'.format(key)] = time
    state['offset__{}'.format(key)] = offset
    
    return offset
    

def eff_sine(color, point, rate):
    mc = color.copy()
    alpha = mc.a
    def d(c, p, state):
        rad = ((p.x - point.x) ** 2 + (p.y - point.y) ** 2) ** 0.5
        rads = rng(rad / float(rate + 0.1) ** 2)
        mc.a = alpha * math.sin(rads)
        return  mc.mix_onbg(c)

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
        rads = rng(rad / float(size + 0.1) ** 2)
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

def eff_rainbow(vector, rate=5., alpha=1.0, key='rainbow'):
    def d(c, p, state):
        time = state.get("time", 0.)
        offset = timer(state, key=key, rate=rate)

        hue = offset + float((p.x * vector.x) + (p.y * vector.y)) 

        mc = Color(h=0.0, s=1.0, v=1.0, a=alpha)
        mc.set_yiq(y=0.5, i=math.sin(hue), q=math.cos(hue))

        return mc.mix_onbg(c)
    return d

def eff_stripe(vector, color, rate=5., gamma=2.5, key='stripe'):
    mc = color.copy()
    alpha = mc.a
    def d(c, p, state):
        time = state.get("time", 0.)
        offset = timer(state, key=key, rate=rate)

        wv = offset + float((p.x * vector.x) + (p.y * vector.y)) 
        value = (math.sin(wv) ** 2) ** gamma

        mc.a = alpha * value
        return mc.mix_onbg(c)
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
        s = strip.points
        if s is not None:
            pairs = zip(s, s[1:])
            colors = []
            for (start, l), (end, _l) in pairs:
                colors += self.render(start, end, l)
            strip.colors = colors


