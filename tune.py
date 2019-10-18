#/usr/bin/env python
from subprocess import Popen, PIPE, CalledProcessError, check_call
from jinja2 import Environment, FileSystemLoader

import argparse
import atexit
import datetime
import glob
import json
import math
import os
import pint
import shlex
import time
import traceback
import iso8601
import sys

env = Environment(
    loader=FileSystemLoader('templates')
)

parser = argparse.ArgumentParser("Tune and stream over web")
parser.add_argument("station")
parser.add_argument("--duration", default="6hr")
parser.add_argument("--gameinfo")

pcapture, pencode = None, None

def killall():
    for p in [pcapture, pencode]:
        try:
            p.kill()
        except:
            pass

def tune(station):
    fmt, ext, seg = ("mp3", "mp3", "mpegts")

    station_hz = int(station * 1000000.0)
    station_readable = str(station).replace('.', '_')

    playlist = '/var/www/html/webtune_live/{}.m3u8'.format(station_readable)
    audio_files = '/var/www/html/webtune_live/{}-segment-%03d.{}'.format(
        station_readable, ext
    )

    capture_command = [
        '/usr/local/bin/softfm',
        '-f', str(station_hz),
        '-R', '-'
    ]

    encode_command = [
        '/usr/bin/ffmpeg',
        '-f', 's16le',
        '-ac', '2',
        '-ar', '48000',
        '-i', '-',
        '-c:a', fmt,
        '-b:a', '64k',
        '-map', '0:0',
        '-f', 'segment',
        '-segment_time', '3',
        '-segment_list', playlist,
        '-segment_format', seg,
        '-segment_list_flags', 'live',
        '-segment_wrap', '4800',
        audio_files
    ]
    try:
        if os.path.exists(playlist):
            os.remove(playlist)
        for output in glob.glob(audio_files.replace('%03d',
                                                    '*').replace(ext,
                                                                 '*')):
            os.remove(output)
    except:
        pass

    try:
        check_call(['pkill', '-9', '-f', 'softfm'])
    except:
        traceback.print_exc()

    pcap = Popen(capture_command, stdout=PIPE)
    penc = Popen(encode_command, stdin=pcap.stdout)
    return pcap, penc

atexit.register(killall)

ureg = pint.UnitRegistry('units.txt')

known_abbrev = {
    "WIS": "Wisconsin",
    "OSU": "Ohio State",
    "MSU": "Michigan State",
    "GB": "Green Bay",
    "TB": "Tampa Bay"
}

def render_game_info(input_json):
    data = ""
    try:
        data = json.load(open(input_json, 'r'))
    except:
        traceback.print_exc()
        return data
    date_obj = iso8601.parse_date(data.get('scheduled'))
    gamedate = date_obj.strftime("%A, %B %d %Y")
    gametime = date_obj.strftime("%I:%M %p").lstrip('0')
    date = "{date} {time}".format(date=gamedate, time=gametime)
    homef = data.get('home')
    awayf = data.get('away')
    matchup = "{away} @ {home}".format(
        away=known_abbrev.get(awayf, awayf),
        home=known_abbrev.get(homef, homef)
    )
    gametemplate = env.get_template('game.html.jinja')
    return gametemplate.render(
        **vars()
    )

rendermap = {
    'tuner.html': 'tuner.html.jinja',
    'tuner_local.html': 'tuner.html.jinja',
    'js/custom.js': 'custom.js.jinja',
    'js/custom_local.js': 'custom.js.jinja'
}

if __name__ == '__main__':
    args = parser.parse_args()
    try:
        stop = datetime.timedelta(seconds=int(args.duration))
    except:
        duration = ureg.parse_expression(args.duration)
        stop = duration.to_timedelta()
    station = float(args.station)
    gameinfo = render_game_info(args.gameinfo)
    for output, templatename in rendermap.iteritems():
        with open(output, 'w') as outfp:
            host = "***REMOVED***:***REMOVED***"
            jsfile = "custom.js"
            if 'local' in output:
                host = "***REMOVED***:***REMOVED***"
                jsfile = "custom_local.js"
            outfp.write(env.get_template(templatename).render(
                gameinfo=gameinfo,
                station_readable=str(station).replace('.', '_'),
                jsfile=jsfile,
                server_host=host
            ))
            outfp.flush()
    check_call(['make', 'deploy'])
    pcapture, pencode = tune(station)
    try:
        start = datetime.datetime.now()
        while datetime.datetime.now() < start + stop:
            time.sleep(1)
            if pcapture.poll() or pencode.poll():
                raise Exception("Encode process stopped")
        print "\nRecorded from {} to {}".format(
            start, datetime.datetime.now()
        )
    except:
        pass
    finally:
        killall()
