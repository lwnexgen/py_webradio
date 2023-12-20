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

from sshtunnel import open_tunnel

log = logging.getLogger()

def is_between_10am_and_10pm():
    # Get the current local time
    current_time = arrow.now()

    # Define the time range: 10 AM (10:00) to 10 PM (22:00)
    start_time = current_time.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = current_time.replace(hour=22, minute=0, second=0, microsecond=0)

    # Check if the current time is between 12 PM and 10 PM
    return (start_time <= current_time <= end_time)

def seconds_until_tomorrow_12pm():
    # Get the current local time
    current_time = arrow.now()

    # Get tomorrow's date at 12 PM
    tomorrow_12pm = current_time.shift(days=+1).replace(hour=12, minute=0, second=0, microsecond=0)

    # Calculate the number of seconds until tomorrow at 12 PM
    return (tomorrow_12pm - current_time).total_seconds()

def wake_windows_pc():
    # ssh -F ssh_config pyserver -- sudo /usr/local/sbin/wolwindows
    subprocess.call(["ssh", "-F", "ssh_config", "pyserver", "--", "sudo", "/usr/local/sbin/wolwindows"])
    time.sleep(10)
    subprocess.call(["ssh", "-F", "ssh_config", "windows", "--", "sudo", "/usr/local/sbin/openai_service.sh", "start"])
    time.sleep(10)
    
def cmd():
    log.info("full argv: {}".format(sys.argv))
    args = sys.argv[1:]
    return args

if __name__ == '__main__':
    args = cmd()
    srand = random.SystemRandom()
    
    while not args:
        schedule()
        print("tunneled in!")
        if is_between_10am_and_10pm():
            # Sleep between 30 and 60 minutes
            sleep_secs = srand.randint(1800, 3600)
        else:
            # Sleep until 12 PM tomorrow
            sleep_secs = seconds_until_tomorrow_12pm()        
        readable = arrow.get(datetime.datetime.utcnow()).to('America/Chicago').shift(seconds=sleep_secs).format('YYYY-MM-DD h:mm:ss A')
        print(f"Sleeping until {readable}")
        time.sleep(sleep_secs)
