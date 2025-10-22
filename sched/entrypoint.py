#!/app/pysched/bin/python
import sys
import glob
import os
import time
import random
import logging
import subprocess
import arrow
import datetime
import signal

from schedulellm import schedule

# catch sigterm
def signal_handler(sig, frame):
    print('SIGTERM received, exiting...')
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)


def between_10am_and_10pm():
    now = arrow.now()
    return now.hour >= 10 and now.hour < 22

def sleep_until_10am():
    now = arrow.now()
    ten_am = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if now >= ten_am:
        ten_am = ten_am.shift(days=1)
    sleep_time = (ten_am - now).total_seconds()
    print(f"Sleeping until 10 AM: {sleep_time} seconds")
    time.sleep(sleep_time)

if __name__ == '__main__':
    while True:
        print("Running schedule...")
        schedule(skip_rmq=False)
        if between_10am_and_10pm():
            print("Between 10 AM and 10 PM, sleeping for 1 hour")
            sleep_secs = 60 * 60
            readable = arrow.now().shift(seconds=sleep_secs).format('YYYY-MM-DD HH:mm:ss')
            print(f"Sleeping until {readable}")
            time.sleep(sleep_secs)
        else:
            sleep_until_10am()
