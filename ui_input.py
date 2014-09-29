import doitlive
import math
import time

from nanokontrol import NanoKontrol2, Map as NKMap
from lights import *

class NKController(NanoKontrol2, doitlive.SafeRefreshMixin):
    """ Functional NanoKontrol2 controller.

    See controller.md
    """
    class Map(object):
        ALPHA = NKMap.SLIDERS[0]
        HUE = NKMap.KNOBS[0]


        WHITE = NKMap.SS[1]
        BLACK = NKMap.MS[1]
        ONOFF = NKMap.RS[0]

        S = NKMap.SS[0]
        SYNC = S
        M = NKMap.MS[0]
        R = NKMap.RS[1]
        REVERSE = R

        SIZE = NKMap.SLIDERS[1]
        SPEED = NKMap.KNOBS[1]

        GLOBAL_LPF = NKMap.RECORD
        BLACKOUT = NKMap.STOP

        STOP = NKMap.STOP
        PLAY = NKMap.PLAY
        RECORD = NKMap.RECORD

    OFFSETS = {
        0: 0,
        1: 2,
        2: 4,
        3: 6,
    }

    def __init__(self):
        NanoKontrol2.__init__(self)
        doitlive.SafeRefreshMixin.__init__(self)
        self.lpf_state = {x: 0.0 for x in NKMap.ALL}
        self.blink_state = {x: None for x in NKMap.DIGITAL}
        self.edge_state = {x: None for x in NKMap.DIGITAL}
        self.beat_state = {}
        self.last_beat_adjustment = None

        self.lpf_alpha = 0.1
        self.blink_period = 16
        self.blink_duty_on = 0.5

        self.start_beat_tracking(0)
        self.start_beat_tracking(1)
        self.start_beat_tracking(2)
        self.start_beat_tracking(3)

    def global_lpf(self, lpf=None):
        if lpf is None:
            return not self.toggle_state[self.Map.GLOBAL_LPF]
        return lpf

    def start_beat_tracking(self, bank, key=Map.SYNC):
        offset = self.OFFSETS[bank] + key
        self.beat_state[offset] = {
            "phi": 0.0,
            "tau": 0.5,
            "bpm": 120,
            "deltas": [], 
            "last_event": 0.0,
            "alpha": 0.1
        }

    def set_bank_bpm(self, bank, bpm=140.0, key=Map.SYNC):
        offset = self.OFFSETS[bank] + key
        if offset in self.beat_state:
            data = self.beat_state[offset]
            old_phase = ((time.time() + data["phi"]) % data["tau"]) / data["tau"]
            data["tau"] = 60. / bpm
            data["bpm"] = bpm
            data["deltas"] = [data["tau"]] * 3 # preload
            new_phase = ((time.time() + data["phi"]) % data["tau"]) / data["tau"]
            data["phi"] -= (new_phase - old_phase) * data["tau"]
            print "BPM Set: phi={:0.2f}; bpm={:0.1f}".format(new_phase, bpm)

    def bank_bpm(self, bank, bpm=None, key=Map.SYNC):
        if bpm is not None:
            return self.set_bank_bpm(bank, bpm)
        offset = self.OFFSETS[bank] + key
        if offset in self.beat_state:
            data = self.beat_state[offset]
            return data["bpm"]
        return 140


    def bank_beat(self, bank, key=Map.SYNC, cont=False):
        offset = self.OFFSETS[bank] + key
        data = self.beat_state[offset]
        if cont:
            return ((time.time() + data["phi"]) / data["tau"])
        else:
            return ((time.time() + data["phi"]) % data["tau"]) / data["tau"]

    def update(self):
        self.process_input()

        for key, data in self.beat_state.items():
            events = self.events.get(key, [])
            for timestamp, evtype in events:
                if not evtype:
                    continue  # Only keydown events
                delta = timestamp - data["last_event"]
                data["last_event"] = timestamp
                if 0.1 < delta < 2.0:
                    data["deltas"] = ([delta] + data["deltas"])[:5]
                    deltas = data["deltas"]
                    data["tau"] = sum(deltas) / len(deltas)
                    data["bpm"] = 60. / data["tau"]
                    alpha = data["alpha"]
                else:
                    alpha = 1.0
                phase = ((timestamp + data["phi"]) % data["tau"]) / data["tau"]
                if phase > 0.5:
                    error = (1.0 - phase) * data["tau"]
                else:
                    error = phase * data["tau"]
                data["phi"] -= error * alpha
                new_phase =  ((timestamp + data["phi"]) % data["tau"]) / data["tau"]
                print "Beat tap: phi={:0.2f} --> {:0.2f}; bpm={:0.1f}; err={:0.2f}".format(phase, new_phase, data["bpm"], error)
                self.last_beat_adjustment = key
            self.set_led(key, 0.2 > ((time.time() + data["phi"]) % data["tau"]) / data["tau"])
    
        if self.last_beat_adjustment is not None:
            data = self.beat_state[self.last_beat_adjustment]
            if self.edge_state[NKMap.SET]:
                for key, _dat in self.beat_state.items():
                    self.beat_state[key] = data.copy()
            if self.edge_state[NKMap.SLEFT]:
                old_phase = ((time.time() + data["phi"]) ) / data["tau"]
                data["tau"] *= 2
                data["bpm"] *= 0.5
                data["deltas"] = [x * 2 for x in data["deltas"]]
                new_phase = ((time.time() + data["phi"]) ) / data["tau"]
                data["phi"] -= (new_phase - old_phase) * data["tau"]
            if self.edge_state[NKMap.SRIGHT]:
                old_phase = ((time.time() + data["phi"]) ) / data["tau"]
                data["tau"] *= 0.5
                data["bpm"] *= 2
                data["deltas"] = [x * 0.5 for x in data["deltas"]]
                new_phase = ((time.time() + data["phi"]) ) / data["tau"]
                data["phi"] -= (new_phase - old_phase) * data["tau"]


        for key, val in self.edge_state.items():
            new = self.state[key]
            if val is None and new: # Off -> On
                self.edge_state[key] = True
            if val is False and not new: # On -> Off
                self.edge_state[key] = None
            if val is True:  # Edge detection
                self.edge_state[key] = False

        for key, prev in self.lpf_state.items():
            new = self.toggle_state[key]
            if new is True: new = 1.0
            if new is False: new = 0.0
            self.lpf_state[key] = self.lpf_alpha * new + (1.0 - self.lpf_alpha) * prev

        for key, count in self.blink_state.items():
            if count is not None:
                self.set_led(key, count < self.blink_duty_on * self.blink_period)
                self.blink_state[key] = (count + 1) % self.blink_period

    def blink_led(self, key, state=True):
        self.blink_state[key] = 0 if state else None
        self.set_led(key, state)

    def bank(self, bank, key, lpf=None):
        lpf = self.global_lpf(lpf)
        offset = self.OFFSETS[bank]
        if lpf:
            return self.lpf_state[offset + key]
        else:
            return self.toggle_state[offset + key]

    def bank_edge(self, bank, key):
        offset = self.OFFSETS[bank]
        return self.edge_state[offset + key]

    def bank_lpf(self, *args, **kwargs):
        return self.bank(*args, lpf=True, **kwargs)

    def bank_color(self, bank, yiq=None, kappa=1.8, lpf=None):
        # TODO: When both black & white are pressed?
        # yiq \in [0.0, 1.0] for YIQ-based color, otherwise HSV
        lpf = self.global_lpf(lpf)
        hue = self.bank(bank, self.Map.HUE, lpf=lpf)
        #alpha = self.bank(bank, self.Map.ALPHA, lpf=lpf) 
        alpha = self.bank_alpha(bank, lpf=lpf)

        black = Black()
        black.a = self.bank(bank, self.Map.BLACK, lpf=lpf)
        white = White()
        white.a = self.bank(bank, self.Map.WHITE, lpf=lpf)

        if alpha is None:
            return None
        elif yiq is not None:
            color = yiq_from_phase(y=yiq, phase=hue, kappa=kappa, a=1.0)
        else:
            color = Color(h=hue, s=1.0, v=1.0, a=1.0)
        out_color =  black.mix_onbg(white.mix_onbg(color))
        out_color.a = alpha
        return out_color


    def bank_speed(self, bank, a=10.0, gamma=1.5, lpf=None):
        lpf = self.global_lpf(lpf)
        speed = a * (self.bank(bank, self.Map.SPEED, lpf=lpf) ** gamma )
        if self.bank(bank, self.Map.REVERSE, lpf=False):
            speed *= -1
        return speed

    def bank_alpha(self, bank, lpf=None):
        # If off returns None
        lpf = self.global_lpf(lpf)
        on = self.bank(bank, self.Map.ONOFF, lpf=lpf)
        alpha = self.bank(bank, self.Map.ALPHA, lpf=lpf)
        if on is True:
            return alpha
        if on is False or on < 0.05:
            return None
        return on * alpha

