#!/usr/bin/env python 

import IPython
import threading
import time

import doitlive
from grassroots import grassroots as gr

import projection as pj
import lights as lt
import devices as dv

from projection import Point, Vector, Color

class DemoLightApp(gr.Blade, doitlive.SafeRefreshableLoop):
    tick = gr.Field(0)
    STATICS = ["tick", "b"]

    def __init__(self, *args, **kwargs):
        self.b = []
        self.strips = [lt.LightStrip(i, length=50) for i in range(2)]
        self.tick = 0
        self.rising = False
        self.projection = pj.Plane()
        self.testprj = pj.Plane()
        self.separate = False
        self.strip_config()
        self.enumerate_devices()
        super(doitlive.SafeRefreshableLoop, self).__init__(*args, **kwargs)

    def step(self):
        self.tick += 1
        self.projection.state['time'] = time.time()
        self.testprj.state['time'] = time.time()

        bg_color= Color(h=0.2, s=1.0, v=1.0, a=0.5)
        green = Color(r=0, g=1.0, b=0.0, a=1.0)
        self.projection.effects = []
        #self.projection.effects = [eff_solid(bg_color)]
        #self.render_strips()
        self.projection.effects.append(pj.eff_rainbow(pj.Point(0.6, 0.0), 3.0, alpha=1.0))

        self.testprj.effects.append(pj.eff_stripe(color=green, vector=pj.Point(0.6, 0.0), rate=3.0))
        self.render_strips()
        self.hw_export_strips()

    def strip_config(self):
        self.strips[0].points = [(Point(2.5/16., 0.7), 3), 
                                 (Point(0.0, 0.7), 11),
                                 (Point(0.0, 0.0), 16),
                                 (Point(1.0, 0.0), 11),
                                 (Point(1.0, 0.7), 9),
                                 (Point(8/16., 0.7), 0)] 
        self.strips[0].sid = 0x10
        self.strips[1].points = [(Point(2.5/16., 0.7), 50), 
                                 (Point(0.8, 1.0), 0)] 
        self.strips[1].sid = 0x30

    def render_strips(self):
        if self.separate:
            self.projection.render_strip(self.strips[0])
            self.testprj.render_strip(self.strips[1])
        else:
            for strip in self.strips:
                self.projection.render_strip(strip)

    def hw_export_strips(self):
        for strip in self.strips:
            for d in self.b:
                d.framed_packet(data=strip.hw_export(), addr=strip.sid, flags=0xF0)
        for d in self.b:
            d.flush()

    def enumerate_devices(self):
        self.free_devices()
        for i in range(10):
            try:
                self.b.append(dv.SingleBespeckleDevice('/dev/ttyUSB%d' % i, 3000000))
                #self.b.append(dv.SingleBespeckleDevice('/dev/ttyUSB%d' % i, 115200))
                if len(b) >= 4:
                    break
            except:
                pass
        print "Enumerated {0} devices.".format(len(self.b))

    def free_devices(self):
        print self.b
        for b in self.b:
            b.close()
        self.b = []

    def pre_refresh(self):
        reload(pj)
        reload(lt)
        reload(doitlive)


def setup():
    demoapp = DemoLightApp()
    demoapp.start()
    root = gr.Root()
    run = lambda: gr.run(root, host='0.0.0.0')
    thread = threading.Thread(target=run)
    return demoapp, root, thread

