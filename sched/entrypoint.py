#!pysched/bin/python
import sys
import glob
import os
import time
import random
import logging
import subprocess
import arrow
import datetime

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
        sleep_secs = random.randint(240, 900)
        readable = arrow.get(datetime.datetime.utcnow()).to('America/Chicago').shift(seconds=sleep_secs).format('YYYY-MM-DD h:mm:ss A')
        print(f"Sleeping until {readable}")
        time.sleep(sleep_secs)

    print("Executing following: {}".format(args))
    os.execv(args[0], args)
