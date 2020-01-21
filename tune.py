#/usr/bin/env python
from subprocess import Popen, PIPE, CalledProcessError, check_call, check_output
from jinja2 import Environment, FileSystemLoader

import argparse
import tempfile
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
parser.add_argument("--duration", default="6hr", help="How long to record for")
parser.add_argument("--gameinfo", help="Path to JSON file with information about game")
parser.add_argument('--config', default='config.json', help='Config file override',
                    type=argparse.FileType('r'))

pcapture, pencode = None, None

def killall():
    """
    Kill any running processes so that we don't fork-bomb
    """
    for p in [pcapture, pencode]:
        try:
            p.kill()
        except:
            pass

def tune(station):
    """
    Tune into the given station, and write out an m3u8 file

    RTL2832U -> (SoftFM | RTL-SDR) -> (ffmpeg | m3u8) -> Apache -> Clappr

    Dependencies:
    https://github.com/jorisvr/SoftFM (FM tuning tools for RTL-SDR)
    https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr (Software Defined Radio for RTL2832U)
    https://www.apache.org/ (Simple Linux HTTP server)
    https://github.com/clappr/clappr (Open-source media frontend for web)
    """
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

# Human-readable units for durations
ureg = pint.UnitRegistry('units.txt')

known_abbrev = {
    "WIS": "Wisconsin",
    "OSU": "Ohio State",
    "MSU": "Michigan State",
    "GB": "Green Bay",
    "TB": "Tampa Bay"
}

def render_game_info(data):
    """
    Write a summary page with game information

    param:data - input JSON
    """
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

def demote(user_uid, user_gid):
    """
    Drop user privileges
    """
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)
    return result

def merge(gameinfo, station):
    """
    Merge all of the files in the current m3u8 into a single archive after recording
    is complete

    param:gameinfo - JSON information about game
    param:station - Station tuned so that we can figure out which m3u8 to parse
    """
    if not gameinfo:
        return
    m3u8 = "/var/www/html/webtune_live/{}.m3u8".format(station.replace('.', '_'))
    mp3s = [x.strip() for x in open(m3u8, 'r').readlines() if x.strip().endswith('.mp3')]
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write("\n".join([
            "file '/var/www/html/webtune_live/{}'".format(x) for x in mp3s
        ]))
        tmp.flush()
    os.chown(tmp.name, 1000, 1000)
    home_team = gameinfo.get('home')
    away_team = gameinfo.get('away')
    date_sched = gameinfo.get('scheduled_at').split().pop()
    output_file = "***REMOVED***/Badgers/{away}-vs-{home}-{sport}-{date}.mp3".format(
        away=away_team,
        home=home_team,
        date=date_sched,
        sport=gameinfo.get('sport', 'unk')
    ).replace(' ', '-')
    encode = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', tmp.name, '-c', 'copy', output_file]
    try:
        # Run ffmpeg as non-root so that the output is actually readable
        check_call(encode, preexec_fn=demote(1000, 1000))
    except:
        traceback.print_exc()
    finally:
        os.remove(tmp.name)

# Map of jinja templates to output files
rendermap = {
    'tuner.html': 'tuner.html.jinja',
    'tuner_local.html': 'tuner.html.jinja',
    'js/custom.js': 'custom.js.jinja',
    'js/custom_local.js': 'custom.js.jinja'
}

if __name__ == '__main__':
    """
    1) Read command line arguments
    2) Render out HTML to local directory with gameinfo and controls, using parameters in --config
    3) Deploy to /var/www
    4) Start live background render process, poll until it crashes or
       duration elapses
    5) Make sure all lingering subprocesses are dead
    6) Merge the output files into a single mp3
    """
    args = parser.parse_args()
    try:
        stop = datetime.timedelta(seconds=int(args.duration))
    except:
        try:
            duration = ureg.parse_expression(args.duration)
        except:
            duration = ureg.parse_expression("6hr")
        stop = duration.to_timedelta()

    gameinfo_json = {}
    try:
        gameinfo_json = json.load(open(args.gameinfo, 'r'))
    except:
        traceback.print_exc()
        pass

    station = float(args.station)
    if gameinfo_json:
        gameinfo = render_game_info(gameinfo_json)
    else:
        gameinfo = {}

    address_config = json.load(args.config)
    if not address_config.get('local_address') or not address_config.get('remote_address'):
        print("Must define local_address and remote_address in --config file")
        parser.print_usage()
        sys.exit(1)

    for output, templatename in rendermap.iteritems():
        with open(output, 'w') as outfp:
            host = address_config.get('remote_address')
            jsfile = "custom.js"
            if 'local' in output:
                host = address_config.get('local_address')
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
        merge(gameinfo_json, args.station)
