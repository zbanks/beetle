#!/usr/bin/env python
from demo import *

def main():
    demoapp, groot, webthread = setup()
    d = demo = demoapp
    webthread.start()
    stop = lambda: webthread.stop()
    variables = locals()
    variables.update(globals())
    IPython.start_ipython(user_ns=variables)

if __name__ == "__main__":
    main()
