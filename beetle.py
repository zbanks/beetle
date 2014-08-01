import threading
import time

import refreshable
from grassroots import grassroots as gr

class Beetle(refreshable.SafeRefreshableLoop):
    def __init__(self, ui, *args, **kwargs):
        self.ui = ui
        threading.Thread.__init__(self, *args, **kwargs)


class BeetleUI(gr.Blade, refreshable.SafeRefreshMixin):
    strips = gr.Field([])

def setup():
    ui = BeetleUI()
    beetle = Beetle(ui)
    beetle.start()
    return beetle, ui

if __name__ == "__main__":
    print "Use ipython to run:"
    print ">>> from beetle import *"
    print ">>> b, ui = setup()"
