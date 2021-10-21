#!pysched/bin/python
import argparse
import atexit
import datetime
import glob
import json
import logging
import math
import os
import shlex
import sys
import tempfile
import time
import traceback

from multiprocessing import Process
from datetime import timezone
from subprocess import Popen, PIPE, CalledProcessError, check_call, check_output, DEVNULL

# jinja2 for rendering HTML stuff
from jinja2 import Environment, FileSystemLoader

# various utility libraries
import pika
import pint
import iso8601

log = logging.getLogger()

env = Environment(
    loader=FileSystemLoader('templates')
)

pcapture, pencode = None, None

def killall(procs=None):
    """
    Kill any running processes so that we don't fork-bomb
    """
    if procs is None:
        for p in [pcapture, pencode]:
            try:
                p.kill()
            except:
                pass
    else:
        for p in procs:
            try:
                p.kill()
            except:
                pass

tuner = {
    'nfl': {
        'station': 101.5,
        'duration': 4
    },
    'ncaab': {
        'station': 101.5,
        'duration': 4
    },
    'ncaaf': {
        'station': 101.5,
        'duration': 5
    },
    'mlb': {
        'station': 96.7,
        'duration': 5
    }
}

gains = {
    "96.7": "22.9",
    "100.5": "22.9",
    "101.5": "7.7"
}

squelches = {
    "96.7": "10"
}

# "96.7": "highpass=f=200,lowpass=f=3000"
filters = {}

def tune(station, capture_command, logfile='/dev/null'):
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

    encode_command = [
        '/usr/bin/ffmpeg',
        '-f', 's16le',
        '-ac', '1',
        '-ar', '48000',
        '-i', '-',
        '-c:a', fmt,
        '-b:a', '48k',
        "-ac", "2",
        '-map', '0:0',
        '-f', 'segment',
        '-segment_time', '5',
        '-segment_list', playlist,
        '-segment_format', seg,
        '-segment_list_flags', 'live',
        '-segment_wrap', '4800',
    ]

    if filters.get(station):
        encode_command += ['-af', filters.get(station)]

    encode_command += [audio_files]

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
        check_call(['pkill', '-9', '-f', 'airspy-fmradion'])
    except:
        pass

    try:
        pcap = Popen(capture_command, stdout=PIPE, stderr=DEVNULL)
    except:
        print("Error running capture command")
        traceback.print_exc()
        raise

    try:
        penc = Popen(encode_command, stdin=pcap.stdout, stderr=DEVNULL)
    except:
        print("Error running encode command")
        traceback.print_exc()
        raise

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
    date_obj = iso8601.parse_date(data.get('scheduled_cst'))
    gamedate = date_obj.strftime("%A, %B %d %Y")
    gametime = date_obj.strftime("%I:%M %p").lstrip('0')
    date = "{date} {time}".format(date=gamedate, time=gametime)
    homef = data.get('home')
    awayf = data.get('away')
    odds = data.get('odds')
    matchup = "{away} @ {home}".format(
        away=known_abbrev.get(awayf, awayf),
        home=known_abbrev.get(homef, homef)
    )
    gametemplate = env.get_template('game.html.jinja')

    rendered = gametemplate.render(
        **vars()
    )

    return rendered

def merge(gameinfo, station):
    """
    Merge all of the files in the current m3u8 into a single archive after recording
    is complete

    param:gameinfo - JSON information about game
    param:station - Station tuned so that we can figure out which m3u8 to parse
    """
    if not gameinfo:
        return
    m3u8 = "/var/www/html/webtune_live/{}.m3u8".format(str(station).replace('.', '_'))
    mp3s = [x.strip() for x in open(m3u8, 'r').readlines() if x.strip().endswith('.mp3')]
    # write a list of mp3s to a temp file that ffmpeg can read out of
    with tempfile.NamedTemporaryFile(mode='w') as tmp:
        output = "\n".join([
            "file '/var/www/html/webtune_live/{}'".format(str(x)) for x in mp3s
        ])
        tmp.write(output)
        os.chown(tmp.name, 1000, 1000)
        tmp.flush()
        home_team = gameinfo.get('home')
        away_team = gameinfo.get('away')
        date_sched = gameinfo.get('scheduled_at').split().pop()
        output_file = "/mnt/megapenthes/Badgers/{away}-vs-{home}-{sport}-{date}.mp3".format(
            away=away_team,
            home=home_team,
            date=date_sched,
            sport=gameinfo.get('sport', 'unk')
        ).replace(' ', '-')
        if os.path.isfile(output_file):
            os.remove(output_file)
        encode = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', tmp.name, '-c', 'copy', output_file]
        try:
            # Run ffmpeg as non-root so that the output is actually readable
            check_call(encode, stdout=DEVNULL, stderr=DEVNULL)
            print("Stored game as {}".format(output_file))
        except:
            traceback.print_exc()

def render_html(config):
    """
    Render actual static frontpage based on configuration file from JSON
    received from scheduler
    """
    gameinfo_json = config
    tcfg = tuner.get(config.get('sport'))
    station = float(tcfg.get('station'))
    duration = ureg.parse_expression("{}hr".format(tcfg.get('duration')))
    gameinfo = render_game_info(gameinfo_json)

    # TODO: move this into a config file
    rendermap = {
        'tuner.html': 'tuner.html.jinja',
        'tuner_local.html': 'tuner.html.jinja',
        'js/custom.js': 'custom.js.jinja',
        'js/custom_local.js': 'custom.js.jinja'
    }

    address_config = {}
    with open('config.json') as cfg_fp:
        address_config = json.load(cfg_fp)
    if not address_config.get('local_address') or not address_config.get('remote_address'):
        log.info("Must define local_address and remote_address in --config file")
        parser.print_usage()
        sys.exit(1)

    for output, templatename in rendermap.items():
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
                server_host=host,
                local=('local' in output)
            ))
            outfp.flush()
    check_call(['make', 'deploy'],stdout=DEVNULL,stderr=DEVNULL)

def schedule_tune(config, now=False):
    """
    Tune into the desired station at the desired time, based on the config file.

    Read config file, then sleep until it's time to record
    """
    tcfg = tuner.get(config.get('sport'))
    station = float(tcfg.get('station'))
    duration_seconds = tcfg.get('duration') * (60*60)
    station_hz = int(station * 1000000.0)
    gameinfo_json = config
    capture_command = [
        'pysched/bin/airspy-fmradion',
        '-m', 'fm',
        '-t', 'rtlsdr',
        '-E8',
        "-M",
        '-c', 'freq={},gain={}'.format(
            station_hz,
            gains.get(str(station), "auto")
        ),
        '-R', '-'
    ]
    now_time = datetime.datetime.now(datetime.timezone.utc)

    if now:
        start_at = now_time + datetime.timedelta(seconds=10)
        duration_seconds = 10
    else:
        start_at = iso8601.parse_date(config['scheduled'])

    sleep_duration = (start_at - now_time)
    print("Sleeping for {} until {} starts".format(sleep_duration, config['odds']))
    time.sleep(sleep_duration.total_seconds())
    render_html(config)

    print("Starting recording of {}".format(config['odds']))
    pcapture, pencode = tune(station, capture_command)
    try:
        start = datetime.datetime.now()
        stop = datetime.timedelta(seconds=duration_seconds)
        normal_exit = False
        while datetime.datetime.now() < start + stop:
            time.sleep(1)
            if pcapture.poll() or pencode.poll():
                raise Exception("Capture/encode process stopped")
        normal_exit = True
        print("Recorded {} from {} to {}".format(
            config['odds'], start, datetime.datetime.now()
        ))
    except:
        pass
    finally:
        killall(procs=[pcapture,pencode])
        if normal_exit:
            merge(gameinfo_json, station)
    return normal_exit

sched_procs = {}

def dequeue(now=False):
    """
    Listen for scheduling messages from Rabbit MQ
    """
    # TODO: pull this from config
    connection = None
    channel = None
    for x in range(5):
        print("RabbitMQ connection attempt {}".format(x))
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='rmq'))
            channel = connection.channel()
            channel.queue_declare(queue='schedule')
            break
        except Exception as exc:
            time.sleep(5)

    def sched_process(ch, method, properties, body):
        config = json.loads(body)
        existing = {}
        dead = []

        # flag dead procs, and check for existing queued recordings
        for id, scheduled in sched_procs.items():
            if id == config.get('id'):
                existing = scheduled
                break
            if not scheduled.get('proc').is_alive():
                dead.append(id)

        # no need to keep these around
        for id in dead:
            print("Finished recording {}, removing".format(sched_procs[id]['config']['odds']))
            del sched_procs[id]

        # first thread wins if 'now' is specified
        if now and sched_procs:
            print("Immediate tune specified, first entry ({}) wins".format(
                list(sched_procs.values())[0]['config']['id']
            ))
            return

        # if a game with this existing id has been scheduled already,
        # make sure this isn't a reschedule event and just continue
        if existing:
            if existing.get('config', {}).get('scheduled') != config.get('scheduled'):
                print("Rescheduling existing {} [{}] for {}".format(
                    existing['config']['scheduled'],
                    existing['config']['id'],
                    config.get('scheduled')
                ))
                existing.get('proc').terminate()
                del sched_procs[config['id']]
            else:
                print("Not changing process already scheduled for: {} [{}]".format(
                    existing['config']['scheduled'],
                    existing['config']['id']
                ))
                return

        future_tune = Process(target=schedule_tune, args=(config,), kwargs={'now': now})
        future_tune.start()
        sched_procs[config['id']] = {
            'config': config,
            'proc': future_tune,
        }
        print("Pending recordings:\n{}".format(
            "\n".join(["{}: {} {}".format(
                i,x['config']['scheduled_cst'], x['config']['odds']) for i,x in enumerate(sched_procs.values())])
        ))

    channel.basic_consume(queue='schedule', on_message_callback=sched_process, auto_ack=True)
    print('[Successful] Waiting for RabbitMQ messages from sched container')
    channel.start_consuming()

if __name__ == '__main__':
    parser = argparse.ArgumentParser("Tune and stream over web")
    parser.add_argument('--now', action='store_true', help='Start now instead of waiting until time for event')
    args = parser.parse_args()

    dequeue(now=args.now)
