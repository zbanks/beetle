import collections
import math
import numpy
import pyaudio
import struct
import threading
import time
import traceback

import doitlive
from nanokontrol import Map as NKMap
from grassroots import grassroots as gr

import projection
import lights
import devices
import ui_input

from projection import *
from lights import *

def diode_lpf(data,mem,alpha, dalpha=0.0):
    if mem is None: mem = data
    if data>mem:
        result = data+dalpha*(mem-data)
    else:
        result = mem+alpha*(data-mem)
    return result, result

def lpf(data,mem,alpha):
    if mem is None: mem = data
    result = mem+alpha*(data-mem)
    return result, result

def circ_lpf(data, mem, alpha):
    if mem is None: mem = data
    a = min(data, mem)
    b = max(data, mem)
    ap = a + 1.0
    result = a+alpha*(b-a)
    resultw = (ap+alpha*(b-ap)) % 1.0
    if (abs(mem - result) < abs(mem - resultw)) ^ (alpha > 0.5):
        return result, result
    else:
        return resultw, resultw

def sfilter(channel, fn, data, **kwargs):
    history = sfilter.history.get(channel)
    data, history = fn(data, history, **kwargs)
    sfilter.history[channel] = history
    return data
sfilter.history = {}

def waverage(data):
    weight, total = map(sum, zip(*[(w, x*w) for x, w in data]))
    return total / weight

class Beetle(doitlive.SafeRefreshableLoop):
    STRIP_LENGTH=50
    #CHUNK = 1024
    CHUNK = 2048
    #CHUNK = 4096
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 48000
    HISTORY_SIZE = 200

    RANGES = [(20,300),(300,1400),(1600,2800),(3000,6000)]
    MIN_FREQ = 200

    def __init__(self, ui, *args, **kwargs):
        self.b = []
        self.ui = ui
        self.strips = [LightStrip(i) for i in range(3)]
        self.init_audio()
        self.min_fbin = 20
        self.alpha = 1.0
        self.smooth_dict = {}
        self.history=collections.deque()
        self.lpf_audio=[0]*len(self.RANGES)
        self.i = 0
        self.projection = Plane()
        self.strip_config()
        self.enumerate_devices()
        #self.nk = NanoKontrol2()
        self.nk = ui_input.NKController()
        self.nkm = ui_input.NKController.Map
        self.mi = None
        self.mstat = {}
        self.start_time = time.time()
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
        self.strips[0].points = [(Point(0.0, 0.0), 50), 
                                 (Point(1.0, 1.0), 0)] 
        self.strips[0].sid = 0x10
        self.strips[1].points = [(Point(0.4, 0.0), 50), 
                                 (Point(0.4, 1.5), 0)] 
        self.strips[1].sid = 0x11
        self.strips[2].points = [(Point(0.6, 0.0), 50), 
                                 (Point(0.6, 1.5), 0)] 
        self.strips[2].sid = 0x12
        
        #self.strips[3].points = [(Point(0.86, 0.0), 4), 
        #                         (Point(0.86, 0.14), 5),
        #                         (Point(1.00, 0.14), 40),
        #                         (Point(1.00, 1.4), 1), 
        #                         (Point(0.95, 1.4), 0)] 
        #self.strips[3].sid = 0x13
        #self.strips[4].points = [(Point(0.15, 0.0), 50),  #TODO
        #                         (Point(0.15, 1.0), 0)] 
        #self.strips[4].sid = 0x18
    def render_strips(self):
        for strip in self.strips:
            if strip.sid == 0x10:
                a = 1
                #continue
            self.projection.render_strip(strip)

    def hw_export_strips(self):
        to_remove = set()
        for strip in self.strips:
            for d in self.b:
                try:
                    d.framed_packet(data=strip.hw_export(), addr=strip.sid, flags=0xFF)
                except:
                    print("ERROR sending data! Reload hardware!")
                    to_remove.add(d)
                    try:
                        d.close()
                    except:
                        pass

        for d in self.b:
            try:
                d.flush()
            except:
                print("ERROR sending data! Reload hardware!")
                to_remove.add(d)
                try:
                    d.close()
                except:
                    pass
        self.b = filter(lambda x: x not in to_remove, self.b)

    def analyze_dom_freq(self, fft):
        def maxat(a): return max(enumerate(a), key=lambda x: x[1])[0] 

        freq = lambda b: self.RATE * float(b) / self.CHUNK
        fbin = lambda f: int(self.CHUNK * f / self.RATE)
        #dom_freq = self.RATE * dom_chk / self.CHUNK

        octave_maxes = []
        for o in range(12):
            if (2 ** o) < self.MIN_FREQ:
                continue
            o_low = fbin(2 ** o)
            o_high = fbin(2 ** (o + 1)) - 1
            if o_low <= 1:
                continue
            samples = fft[o_low:o_high]
            try:
                dom_chk = maxat(samples) + o_low
            except:
                print o_low, o_high
                raise
            dom_freq = freq(dom_chk)
            dom_amp = max(samples)
            octave = 2.0 ** math.floor(math.log(dom_freq) / math.log(2))

            pos = (dom_freq - octave) / octave
            octave_maxes.append((pos, dom_amp))

        return waverage(octave_maxes)

    def step(self):
        self.ui.record('time', (time.time() - self.start_time) * 10)
        self.start_time = time.time()
        self.nk.update()
        self.ui.tick += 1

        # --- Audio Math ---

        audio, fft = self.analyze_audio()
        self.write_spectrum(fft)
        def maxat(a): return max(enumerate(a), key=lambda x: x[1])[0] 

        #self.mind =20 #self.inp(24, 4)

        #mind = self.min_fbin
        #dom_chk = maxat(fft[mind:-mind]) + mind
        #dom_freq = self.RATE * dom_chk / self.CHUNK
        #octave = 2.0 ** math.floor(math.log(dom_freq) / math.log(2))

        #self.dom_freq = dom_freq
        #self.hue = ((dom_freq - octave) / octave)


        #dom_freq = sfilter("dom_freq", data=dom_freq, fn=diode_lpf, alpha=0.08) #self.inp(14, 10) / 500.0)
        #sys.stdout.write("\rdom_freq %d" % dom_freq)

        #self.octave = octave
        self.hue = self.analyze_dom_freq(fft)
        #self.hue = self.hue % 1.0
        self.ui.record('huer', self.hue)
        self.hue = sfilter("dhue", data=self.hue, fn=circ_lpf, alpha=0.01)

        self.lpf_audio=[lpf(float(data),mem,alpha=0.3)[0] for data,mem in zip(audio,self.lpf_audio)]

        self.history.append(self.lpf_audio)
        if len(self.history)>self.HISTORY_SIZE:
            self.history.popleft()

        scaling_factor=[max(max([d[j] for d in self.history]),1) for j in range(len(self.RANGES))]

        #levels=[a/f for a,f in zip(self.lpf_audio,scaling_factor)]
        levels=[rng(a/f) for a,f in zip(audio,scaling_factor)]

        for i, l in enumerate(levels):
            self.ui.record("levels[%d]" % i, l)
        self.ui.record('hue', self.hue)

        # --- Color picking ---
        self.hue = (self.hue + self.nk.state[NKMap.KNOBS[0]]) % 1.0
        #self.hue = sfilter("hue", data=self.hue, alpha=0.04, fn=lpf)

        bass_val = max(min((levels[0]-0.1)/0.9,1.), 0.0)
        bass_val = sfilter("bass_val", data=bass_val, alpha=0.02, fn=lpf)
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
        treble_size = sfilter("treble_size", data=levels[1] , alpha=0.01, fn=lpf)
        treble_intens = sfilter("treble_intens", data=levels[3] , alpha=0.01, fn=lpf)
        bass_size = sfilter("bass_size", data=levels[0] , alpha=0.01, fn=lpf)
        #treble_size = levels[2]

        #bg_alpha = self.inp(32) / 127.0
        #treble_size *= self.nk.state[NKMap.SLIDERS[0]]
        self.treble_size = treble_size
    
        #whiteout_act = abs(self.nk.bank_beat(0)  * 2 - 1.0)

        self.projection.effects = [#eff_solid(bass_color),
                                   #eff_circle(bass_color, Point(0.4, 0.4), treble_size * 5),
                                   #eff_circle(treble_color, Point(0.5, 0.5), treble_size ),
                                   #eff_rainbow(Point(0.5, 0.5), 20),
                                   #eff_colorout(Color(0.0, 0.0, 0.0), "black"),
                                   #eff_solid(Color(r=1.0, g=1.0, b=1.0, a=whiteout_act)),
                                   #eff_solid(solid_color),
                                   #eff_solid(Color(r=0.0, g=0.0, b=0.0, a=whiteout)),
                                   ]
        #rainbow = 20 * self.nk.state[NKMap.KNOBS[7]] - 10.0

        #TODO: pull this out into a function?
        def make_rainbow(bank):
            alpha = self.nk.bank_alpha(bank)
            speed = self.nk.bank_speed(bank)
            size = 3 * self.nk.bank(bank, self.nkm.SIZE) ** 3
            if alpha is not None:
                kappa = 2.2
                y = 0.3
                #kappa = self.nk.bank(bank, self.nkm.HUE) * 5
                y = self.nk.bank(bank, self.nkm.HUE)
                effect = eff_rainbow(Point(0, size), rate=speed, alpha=alpha, kappa=kappa, y=y)
                self.projection.effects.append(effect)

        def make_hsv_rainbow(bank):
            alpha = self.nk.bank_alpha(bank)
            speed = self.nk.bank_speed(bank)
            if alpha is not None:
                #kappa = self.nk.bank(bank, self.nkm.HUE) * 5
                #y = self.nk.bank(bank, self.nkm.HUE)
                effect = eff_hsv_rainbow(Point(0, 50), rate=speed, alpha=alpha)
                self.projection.effects.append(effect)

        def make_stripes(bank):
            phase = self.nk.bank_beat(bank, cont=True)
            hue_offset = ((math.sin(phase * math.pi / 2.0) ** 2) ** 4) 
            y = (hue_offset * 0.3) + 0.2
            color = self.nk.bank_color(bank, yiq=y)
            size = 15 * (1 - self.nk.bank(bank, self.nkm.SIZE)) ** 3
            speed = self.nk.bank_speed(bank, a=15) 
            phase = self.nk.bank_beat(bank, cont=True)
            bpm = self.nk.bank_bpm(bank)
            if color is not None:
                #effect = eff_stripe_beat(Point(speed, speed), color, phase, gamma=size)
                effect = eff_stripe_time(Point(0, speed), color, bpm / 40, gamma=size, key='stripe_%d' % bank)

                if self.nk.bank_edge(bank, self.nkm.SYNC):
                    self.projection.state["offset__st"] = 0
                self.projection.effects.append(effect)

        def make_pulsar(bank):
            alpha = self.nk.bank_alpha(bank)
            gamma = 15 * (1 - self.nk.bank(bank, self.nkm.SPEED)) ** 3
            size = 0.3 * self.nk.bank(bank, self.nkm.SIZE)
            if self.nk.bank(bank, self.nkm.REVERSE, lpf=False):
                size *= -1
            if alpha is not None:
                phase = self.nk.bank_beat(bank, cont=True)
                hue_offset = ((math.sin(phase * math.pi / 2.0) ** 2) ** gamma) * size
                #self.hue = 0.1
                bass_hue = (self.hue + self.nk.bank(bank, self.nkm.HUE)) % 1.0
                treble_hue = (bass_hue + hue_offset) % 1.0
                treble_alpha = alpha * (0.5 * treble_intens + 0.5)
                bass_val = 0.7 * bass_size + 0.3 
                #bass_val = 0.5
                self.ui.record("bass_size", bass_size)
                white = White()
                white.a = self.nk.bank(bank, self.nkm.WHITE, lpf=True)

                treble_color= Color(h=treble_hue, s=1.0 ,v=1.0, a=treble_alpha)
                treble_color = white.mix_onbg(treble_color)
                bass_color= Color(h=bass_hue, s=1., v=1, a=0.6 * bass_val * alpha)

                bass_color_sol = bass_color.copy()
                bass_color_sol.a = 0.2

                center = Point(0.5, 0.8)

                effect_bgs = eff_circle(bass_color_sol, center, 1.0)
                effect_bg = eff_circle(bass_color, center, bass_size * 3.0 + 0.3, gamma=3)
                effect_fg = eff_circle(treble_color, center, treble_size, gamma=5)

                #self.projection.effects.append(effect_bgs)
                self.projection.effects.append(effect_bg)
                self.projection.effects.append(effect_fg)

        def make_blackout(btn):
            color = Black()
            color.a = self.nk.lpf_state[btn]
            effect = eff_solid(color)
            self.projection.effects.append(effect)

        make_pulsar(0)
        make_stripes(1)
        make_rainbow(3)
        make_stripes(2)
        make_blackout(self.nkm.BLACKOUT)
        #make_hsv_rainbow(1)
        #if self.nk.toggle_state[NKMap.SS[7]]:
            #self.projection.effects.append(eff_stripe(Point(.7, .7), Color(r=0, g=0.0, b=0, a=rainbow_alpha), rainbow, gamma= 10 * self.nk.state[NKMap.KNOBS[6]] ** 3))

        #self.projection.effects.append(eff_sine(treble_color, Point(0.5, 0.5), amp))

        #self.projection.effects.append(eff_solid(Color(r=0.0, g=0.0, b=0.0, a=blackout_act)))

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
        self.ui.flush_records()

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
                #self.b.append(devices.SingleBespeckleDevice('/dev/ttyUSB%d' % i, 460800))
                self.b.append(devices.SingleBespeckleDevice('/dev/ttyUSB%d' % i, 3000000))
                #self.b.append(devices.SingleBespeckleDevice('/dev/ttyUSB%d' % i, 115200))
                #self.b.append(devices.SingleBespeckleDevice('/dev/ttyUSB%d' % i, 9600))
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
    levels = gr.Field([])
    debug = gr.Field("")

    graph_data = gr.Field([])
    graph_data_towrite = {}
    def record(self, key, data):
        self.graph_data_towrite[key] = data
    def flush_records(self):
        self.graph_data.append(self.graph_data_towrite.copy())
        self.graph_data = self.graph_data[-20:]



def setup():
    ui = BeetleUI()
    beetle = Beetle(ui)
    beetle.start()
    root = gr.Root()
    run = lambda: gr.run(root, host="0.0.0.0")
    thread = threading.Thread(target=run)
    return beetle, ui, root, thread

