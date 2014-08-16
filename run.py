#!/usr/bin/env python
from beetle import *

def main():
    beetle, ui, groot, webthread = setup()
    b = beetle
    webthread.start()
    stop = lambda: webthread.stop()
    variables = locals()
    variables.update(globals())
    IPython.start_ipython(user_ns=variables)

if __name__ == "__main__":
    main()
