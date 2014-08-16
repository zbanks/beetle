import IPython
import colorsys
import collections
import math
import numpy
import pyaudio
import struct
import threading
import time

import doitlive
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

from projection import *

class LightStrip(gr.Blade):
    html_colors = gr.Field([])
    sid = gr.Field(0)
    copies = gr.Field(1)

    def __init__(self, sid, length=20, copies=1):
        self.length = length
        self.colors = [Color(r=i / 20., g=0.2, b=0.2) for i in range(self.length)]
        self.sid = sid
        self.copies = copies
        self.update()

    def update(self):
        self.html_colors = [c.html_rgb for c in self.colors]

def diode_lpf(data,mem,alpha):
    if mem is None: mem = data
    if data>mem:
        return data
    result = mem+alpha*(data-mem)
    return result, result

def lpf(data,mem,alpha):
    if mem is None: mem = data
    result = mem+alpha*(data-mem)
    return result, result

def sfilter(channel, fn, data, **kwargs):
    history = sfilter.history.get(channel)
    data, history = fn(data, history, **kwargs)
    sfilter.history[channel] = history
sfilter.history = {}

class Beetle(doitlive.SafeRefreshableLoop):
    STRIP_LENGTH=50
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 48000
    HISTORY_SIZE = 500

    RANGES = [(20,200),(200,1200),(1200,2400),(2400,1200)]
    TAU_LPF = .1
    COLOR_PERIOD = 60

    def __init__(self, ui, *args, **kwargs):
        self.ui = ui
        self.strips = [LightStrip(i) for i in range(10)]
        self.init_audio()
        self.min_fbin = 20
        self.alpha = 1.0
        self.smooth_dict = {}
        self.history=collections.deque()
        self.lpf_audio=[0]*len(self.RANGES)
        self.i = 0
        self.projection = Plane()
        super(doitlive.SafeRefreshableLoop, self).__init__(*args, **kwargs)

    def smooth(self, key, now, alpha=0.1, fn=None):
        if not fn:
            fn = lpf
        if key not in self.smooth_dict:
            self.smooth_dict[key] = now
        output = fn(now, self.smooth_dict[key], alpha)
        self.smooth_dict[key]  = output
        return output

    def step(self):
        self.ui.tick += 1
        audio, fft = self.analyze_audio()
        self.write_spectrum(fft)
        def maxat(a): return max(enumerate(a), key=lambda x: x[1])[0] 
        #self.read_midi_events()

        #self.mind =20 #self.inp(24, 4)
        mind = self.min_fbin
        dom_chk = maxat(fft[mind:-mind]) + mind
        dom_freq = self.RATE * dom_chk / self.CHUNK
        #self.dom_freq = dom_freq

        dom_freq = sfilter("dom_freq", dom_freq, fn=lpf, alpha=0.161) #self.inp(14, 10) / 500.0)
        #sys.stdout.write("\rdom_freq %d" % dom_freq)

        octave = 2.0 ** math.floor(math.log(dom_freq) / math.log(2))
        self.octave = octave
        self.hue = ((dom_freq - octave) / octave)
        self.hue = self.hue % 1.0

        self.lpf_audio=[lpf(float(data),mem,self.alpha) for data,mem in zip(audio,self.lpf_audio)]

        self.history.append(self.lpf_audio)
        if len(self.history)>self.HISTORY_SIZE:
            self.history.popleft()

        scaling_factor=[max(max([d[j] for d in self.history]),1) for j in range(len(self.RANGES))]

        levels=[a/f for a,f in zip(self.lpf_audio,scaling_factor)]
        bass_val = max(min((levels[0]-0.1)/0.9,1.), 0.0)
        bass_val = sfilter("bass_val", bass_val, alpha=0.53, fn=lpf)
        bass_hue = (self.hue + 0.95) % 1.0
        if bass_val < 0.0: # Switch colors for low bass values
            bass_hue = (bass_hue + 0.9) % 1.0
            bass_val *= 1.0

        bass_val = max(bass_val ** 1.45 , 0.0)

        bass_color= Color(h=bass_hue, s=1., v=bass_val )
        treble_color= Color(h=self.hue, s=0.7 ,v=0.9 )

        #treble_size = (0.5-0.3*levels[1]) 
        treble_size = sfilter("treble_size", levels[1] , alpha=0.9, fn=diode_lpf)

        self.projection.effects = [eff_diamond(bass_color, Point(0.4, 0.4), treble_size * 5),
                                   eff_diamond(treble_color, Point(0.5, 0.5), treble_size * 3)]

        #treble_size = levels[1]
        #time.sleep(0.5)
        #self.i = (self.i + 1) % len(self.strips)
        #strip.colors = [bass_color for i in range(20)]
        #strip.colors[:treble_size] = [treble_color for i in range(treble_size)]
        #strip.update()
        for i, strip in enumerate(self.strips):
            strip.colors = self.projection.render(Point(0, i/10.), Point(1, i/10.), 20)
            strip.update()

        #strip = self.strips[1]
        #strip.colors = [treble_color for i in range(20)]
        #strip.update()
        self.ui.debug = str(bass_color)

    def init_audio(self):
        #pyaudio.pa.initialize(pyaudio.pa)
        self.pa=pyaudio.PyAudio()

        #devs=[self.pa.get_device_info_by_index(i) for i in range(self.pa.get_device_count())]

        self.in_stream = self.pa.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK)

    def analyze_audio(self):
        data = self.in_stream.read(self.CHUNK)
        samples = struct.unpack('h'*self.CHUNK,data)
        #fft = pyfftw.interfaces.numpy_fft.rfft(samples)
        fft=numpy.fft.rfft(samples)
        fft=abs(fft)**2
        out=[]
        for (low,high) in self.RANGES:
            low_bucket=int(self.CHUNK*low/self.RATE)
            high_bucket=int(self.CHUNK*high/self.RATE)
            result=sum(fft[low_bucket:high_bucket])
            out.append(result)
        return out, fft

    def write_spectrum(self, fft):
        fft = map(math.log1p, fft)
        mval = max(fft)
        mind = self.min_fbin
        def maxat(a): return max(enumerate(a), key=lambda x: x[1])[0] 
        dom_chk = maxat(fft[mind:-mind]) + mind
        dom_freq = self.RATE * dom_chk / self.CHUNK
        ranges = [mval * x  for x in [0.95, 0.9, 0.7, 0.5, 0.4]] #[0.6, 0.4, 0.2, 0.1, 0.05]]
        spec_max = 80
        spec_range = fft[0:spec_max]
        self.ui.spectrum = ("max @: %d; mind: %d\n" % (dom_chk, mind))
        for r in ranges:
            self.ui.spectrum += ("".join([' ' if v < r else '#' for v in spec_range])) + "\n"
        for s in range(spec_max)[::7]:
            freq = int(self.RATE * s / self.CHUNK)
            self.ui.spectrum += ("|{: <6}".format(freq))

    def pre_refresh(self):
        self.old_id = id(self)

    def post_refresh(self):
        print self.old_id, id(self)

class BeetleUI(gr.Blade):
    tick = gr.Field(0)
    color = gr.Field("rgb(100,30,50)")
    spectrum = gr.Field("")
    debug = gr.Field("")

def setup():
    ui = BeetleUI()
    beetle = Beetle(ui)
    beetle.start()
    root = gr.Root()
    run = lambda: gr.run(root)
    thread = threading.Thread(target=run)
    return beetle, ui, root, thread

