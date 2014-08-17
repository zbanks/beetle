import collections
import colorsys
import doitlive
import math

from grassroots import grassroots as gr
from lights import Color

Point = collections.namedtuple("Point", ["x", "y"])

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
    def d(c, p, **kwargs):
        if abs(p.x - point.x) + abs(p.y - point.y) <= size:
            return color
        return c
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
        return reduce(lambda color, fn: fn(color, point, **self.state), self.effects, self.background_color)
