import collections
import math
import numpy
import pyaudio
import struct
import threading
import time
import traceback

import doitlive
from nanokontrol import NanoKontrol2, Map as NKMap
from grassroots import grassroots as gr

import projection
import lights
import devices

from projection import *
from lights import *

def diode_lpf(data,mem,alpha):
    if mem is None: mem = data
    if data>mem:
        return data, data
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
    return data
sfilter.history = {}

MIDI_NAMES = {
    "k0": 16,
}

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
        self.b = []
        self.ui = ui
        self.strips = [LightStrip(i) for i in range(2)]
        self.init_audio()
        self.min_fbin = 30
        self.alpha = 1.0
        self.smooth_dict = {}
        self.history=collections.deque()
        self.lpf_audio=[0]*len(self.RANGES)
        self.i = 0
        self.projection = Plane()
        self.strip_config()
        self.enumerate_devices()
        self.nk = NanoKontrol2()
        self.mi = None
        self.mstat = {}
        super(doitlive.SafeRefreshableLoop, self).__init__(*args, **kwargs)

    def unsaturate(self):
        h = self.history[-1]
        self.history = collections.deque()
        for i in range(self.HISTORY_SIZE):
            self.history.append(h)

    def smooth(self, key, now, alpha=0.1, fn=None):
        if not fn:
            fn = lpf
        if key not in self.smooth_dict:
            self.smooth_dict[key] = now
        output = fn(now, self.smooth_dict[key], alpha)
        self.smooth_dict[key]  = output
        return output

    def strip_config(self):
        self.strips[0].points = [(Point(0.4, 0.0), 50), 
                                 (Point(0.4, 1.0), 0)] 
        self.strips[0].sid = 0x10
        self.strips[1].points = [(Point(0.6, 0.0), 50), 
                                 (Point(0.6, 1.0), 0)] 
        self.strips[1].sid = 0x20

    def render_strips(self):
        for strip in self.strips:
            self.projection.render_strip(strip)

    def hw_export_strips(self):
        for strip in self.strips:
            for d in self.b:
                try:
                    d.framed_packet(data=strip.hw_export(), addr=strip.sid, flags=0x10)
                except:
                    print("ERROR sending data! Reload hardware!")
                    try:
                        d.close()
                    except:
                        pass

        for d in self.b:
            d.flush()

    def step(self):
        self.nk.process_input()
        self.ui.tick += 1

        # --- Audio Math ---

        audio, fft = self.analyze_audio()
        self.write_spectrum(fft)
        def maxat(a): return max(enumerate(a), key=lambda x: x[1])[0] 

        #self.mind =20 #self.inp(24, 4)
        mind = self.min_fbin
        dom_chk = maxat(fft[mind:-mind]) + mind
        dom_freq = self.RATE * dom_chk / self.CHUNK
        #self.dom_freq = dom_freq

        dom_freq = sfilter("dom_freq", data=dom_freq, fn=lpf, alpha=0.02) #self.inp(14, 10) / 500.0)
        #sys.stdout.write("\rdom_freq %d" % dom_freq)

        octave = 2.0 ** math.floor(math.log(dom_freq) / math.log(2))
        self.octave = octave
        self.hue = ((dom_freq - octave) / octave)
        self.hue = self.hue % 1.0
        self.hue = (self.hue + self.nk.state[NKMap.KNOBS[0]]) % 1.0
        self.hue = sfilter("hue", data=self.hue, alpha=0.02, fn=lpf)

        self.lpf_audio=[lpf(float(data),mem,alpha=0.2)[0] for data,mem in zip(audio,self.lpf_audio)]

        self.history.append(self.lpf_audio)
        if len(self.history)>self.HISTORY_SIZE:
            self.history.popleft()

        scaling_factor=[max(max([d[j] for d in self.history]),1) for j in range(len(self.RANGES))]

        levels=[a/f for a,f in zip(self.lpf_audio,scaling_factor)]

        # --- Color picking ---

        bass_val = max(min((levels[0]-0.1)/0.9,1.), 0.0)
        bass_val = sfilter("bass_val", data=bass_val, alpha=0.1, fn=lpf)
        bass_hue = (self.hue + 0.95) % 1.0
        if bass_val < 0.0: # Switch colors for low bass values
            bass_hue = (bass_hue + 0.9) % 1.0
            bass_val *= 1.0

        bass_val = max(bass_val ** 1.45 , 0.0)

        treble_color= Color(h=self.hue, s=1.0 ,v=1.0, a=0.9 )
        bass_color= Color(h=bass_hue, s=1., v=bass_val, a=0.5)

        # --- Projection ---
        self.projection.state["time"] = time.time()

        #treble_size = (0.5-0.3*levels[1]) 
        treble_size = sfilter("treble_size", data=levels[1] , alpha=0.03, fn=diode_lpf)

        #bg_alpha = self.inp(32) / 127.0
        treble_size *= self.nk.state[NKMap.SLIDERS[0]]
        self.treble_size = treble_size
        blackout = self.nk.state[NKMap.SLIDERS[1]]
        whiteout = 1.0 - self.nk.state[NKMap.SLIDERS[2]]
        whiteout_act = self.nk.state[NKMap.SLIDERS[3]]
        solid_out = self.nk.state[NKMap.SLIDERS[4]]
        bass_color.a = blackout
        solid_color = treble_color.copy()
        solid_color.a = solid_out

        blackout_act = self.nk.state[NKMap.SLIDERS[5]]
        blackout_act = sfilter("blackout", data=blackout_act, alpha=0.1, fn=diode_lpf)
    

        self.projection.effects = [eff_solid(bass_color),
                                   #eff_circle(bass_color, Point(0.4, 0.4), treble_size * 5),
                                   eff_circle(treble_color, Point(0.5, 0.5), treble_size ),
                                   #eff_rainbow(Point(0.5, 0.5), 20),
                                   eff_colorout(Color(0.0, 0.0, 0.0), "black"),
                                   eff_solid(Color(r=1.0, g=1.0, b=1.0, a=whiteout_act)),
                                   eff_solid(solid_color),
                                   #eff_solid(Color(r=0.0, g=0.0, b=0.0, a=whiteout)),
                                   ]
        rainbow = 0.05 +  0.5 * self.nk.state[NKMap.KNOBS[7]]
        rainbow_alpha = self.nk.state[NKMap.SLIDERS[7]]
        if self.nk.toggle_state[NKMap.RS[7]]:
            self.projection.effects.append(eff_rainbow(Point(5, 5), rainbow, alpha=rainbow_alpha))
        if self.nk.toggle_state[NKMap.MS[7]]:
            self.projection.effects.append(eff_stripe(Point(5, 5), Color(r=1, g=0.0, b=0), rainbow, gamma=10.5))

        #self.projection.effects.append(eff_sine(treble_color, Point(0.5, 0.5), amp))

        #self.projection.effects.append(eff_solid(Color(r=0.0, g=0.0, b=0.0, a=blackout_act)))

        solid_color.a = 0.8
        #self.projection.effects = [eff_solid(solid_color)]

        #treble_size = levels[1]
        #time.sleep(0.5)
        #self.i = (self.i + 1) % len(self.strips)
        #strip.colors = [bass_color for i in range(20)]
        #strip.colors[:treble_size] = [treble_color for i in range(treble_size)]

        #strip = self.strips[1]
        #strip.colors = [treble_color for i in range(20)]
        self.ui.debug = str(bass_color)
        self.render_strips()
        self.hw_export_strips()

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
        reload(projection)
        reload(lights)
        reload(doitlive)

    def post_refresh(self):
        self.strip_config()

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

