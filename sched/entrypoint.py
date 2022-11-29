#!pysched/bin/python
import sys
import glob
import os
import time
import random
import logging
import subprocess

from schedule import schedule

log = logging.getLogger()

def cmd():
    log.info("full argv: {}".format(sys.argv))
    args = sys.argv[1:]
    return args

if __name__ == '__main__':
    args = cmd()
    srand = random.SystemRandom()
    
    while not args:
        schedule()
        time.sleep(srand.randint(300, 1200))

    print("Executing following: {}".format(args))
    os.execv(args[0], args)
