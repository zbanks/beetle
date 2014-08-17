#!/usr/bin/env python 

import IPython
import threading
import time

import doitlive
from grassroots import grassroots as gr

from projection import *
from lights import *

class DemoLightApp(gr.Blade, doitlive.SafeRefreshableLoop):
    tick = gr.Field(0)
    STATICS = ["tick"]

    def __init__(self, *args, **kwargs):
        self.strips = [LightStrip(i, length=50) for i in range(4)]
        self.tick = 0
        self.rising = False
        super(doitlive.SafeRefreshableLoop, self).__init__(*args, **kwargs)

    def step(self):
        self.tick += 1
        self.strips[0].colors[0].r = (self.tick % 256) / 255.
        time.sleep(0.01)


def setup():
    demoapp = DemoLightApp()
    demoapp.start()
    root = gr.Root()
    run = lambda: gr.run(root)
    thread = threading.Thread(target=run)
    return demoapp, root, thread

