import threading
import time
import IPython

import doitlive
from grassroots import grassroots as gr

class Color(object):
    def __init__(self, r=0., g=0., b=0., h=0., s=0., v=0.):
        self.r = r
        self.g = g
        self.b = b

        self.h = h
        self.s = s
        self.v = v

    @property
    def html_rgb(self):
        f = lambda x: int(round(x * 255))
        return "rgb({}, {}, {})".format(f(self.r), f(self.g), f(self.b))

class LightStrip(gr.Blade, doitlive.SafeRefreshMixin):
    html_colors = gr.Field([])
    sid = gr.Field(0)

    def __init__(self, sid):
        self.colors = [Color(r=i / 20., g=0.2, b=0.2) for i in range(20)]
        self.sid = sid
        self.update()

    def update(self):
        self.html_colors = [c.html_rgb for c in self.colors]

class Beetle(doitlive.SafeRefreshableLoop):
    def __init__(self, ui, *args, **kwargs):
        self.ui = ui
        super(doitlive.SafeRefreshableLoop, self).__init__(*args, **kwargs)

    def step(self):
        self.ui.tick += 1
        time.sleep(0.5)

class BeetleUI(gr.Blade, doitlive.SafeRefreshMixin):
    tick = gr.Field(0)
    color = gr.Field("rgb(100,30,50)")

    def __init__(self):
        self.strips = [LightStrip(i) for i in range(10)]

def setup():
    ui = BeetleUI()
    beetle = Beetle(ui)
    beetle.start()
    root = gr.Root()
    run = lambda: gr.run(root)
    thread = threading.Thread(target=run)
    return beetle, ui, thread

if __name__ == "__main__":
    beetle, ui, webthread = setup()
    b = beetle
    webthread.start()
    stop = lambda: webthread.stop()
    IPython.start_ipython(user_ns=locals())
