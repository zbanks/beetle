#!/usr/bin/env python 

import IPython
import threading
import time

import doitlive
from grassroots import grassroots as gr

import projection
import lights
import devices

from projection import *
from lights import *

class DemoLightApp(gr.Blade, doitlive.SafeRefreshableLoop):
    tick = gr.Field(0)
    STATICS = ["tick"]

    def __init__(self, *args, **kwargs):
        self.strips = [LightStrip(i, length=50) for i in range(1)]
        self.tick = 0
        self.rising = False
        self.projection = Plane()
        self.strip_config()
        self.enumerate_devices()
        super(doitlive.SafeRefreshableLoop, self).__init__(*args, **kwargs)

    def step(self):
        time.sleep(0.01)
        self.tick += 1

        bg_color= Color(h=0.2, s=1.0, v=1.0, a=0.5)
        self.projection.effects = [eff_solid(bass_color)]

    def strip_config(self):
        self.strips[0].points = [(Point(0.4, 0.0), 50), 
                                 (Point(0.4, 1.0), 0)] 
        self.strips[0].sid = 0x10

    def render_strips(self):
        for strip in self.strips:
            self.projection.render_strip(strip)

    def hw_export_strips(self):
        for strip in self.strips:
            for d in self.b:
                d.framed_packet(data=strip.hw_export(), addr=strip.sid, flags=0x00)
        for d in self.b:
            d.flush()

    def enumerate_devices(self):
        self.free_devices()
        self.b = []
        for i in range(10):
            try:
                self.b.append(devices.SingleBespeckleDevice('/dev/ttyUSB%d' % i, 3000000))
                #self.b.append(devices.SingleBespeckleDevice('/dev/ttyUSB%d' % i, 115200))
                if len(b) >= 4:
                    break
            except:
                pass
        print "Enumerated {0} devices.".format(len(self.b))

    def free_devices(self):
        for b in self.b:
            b.close()
        self.b = []


def setup():
    demoapp = DemoLightApp()
    demoapp.start()
    root = gr.Root()
    run = lambda: gr.run(root)
    thread = threading.Thread(target=run)
    return demoapp, root, thread

