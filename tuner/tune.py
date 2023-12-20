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

from multiprocessing import Process, Queue
from datetime import timezone
from subprocess import run, Popen, PIPE, CalledProcessError, check_call, check_output, DEVNULL
from io import StringIO

# jinja2 for rendering HTML stuff
from jinja2 import Environment, FileSystemLoader

# various utility libraries
import pika
import pint
import iso8601
import arrow
import requests

log = logging.getLogger()

env = Environment(
    loader=FileSystemLoader('templates')
)

favorites = {
    'nfl': ['Packers'],
    'ncaaf': ['Wisconsin'],
    'ncaab': ['Wisconsin'],
    'nba': ['milwaukee'],
    'mlb': ['milwaukee']
}

pcapture, pencode = None, None

class ExitCase(Exception):
    "Raised when we want to exit from this script"
    pass

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
    time.sleep(30)
    for proc in ['ffmpeg', 'airspy-fmradion']:
        try:
            run(['pkill', '-9', '-f', proc])
        except:
            pass

tuner = {}
with open('tuner.json') as jsfp:
    tuner = json.load(jsfp)

fscfg = {}
with open('fscfg.json') as jsfp:
    fscfg = json.load(jsfp)

gains = {}
squelches = {}
filters = {}

def tune(station, capture_command, logfile='/dev/null'):
    """
    Tune into the given station, and write out an m3u8 file

    RTL2832U -> (Airspy | RTL-SDR) -> (ffmpeg | m3u8) -> Clappr <- nginx

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
        '-ac', "2",
        '-map', '0:0',
        '-f', 'segment',
        '-segment_time', '3',
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
        print(json.dumps(capture_command))
        # pcap = Popen(capture_command, stdout=PIPE, stderr=DEVNULL)
        pcap = Popen(capture_command, stdout=PIPE)
    except:
        print("Error running capture command")
        traceback.print_exc()
        raise

    try:
        print(json.dumps(encode_command))
        # penc = Popen(encode_command, stdin=pcap.stdout, stderr=DEVNULL)
        penc = Popen(encode_command, stdin=pcap.stdout)
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
    date_obj = iso8601.parse_date(
        data.get('scheduled_cst', datetime.datetime.now().isoformat()))
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

def get_output_fn(output_filename):
    output_dir = fscfg.get('output_dir', '/tmp')
    return f"{output_dir}/{output_filename}.mp3"

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
    if not os.path.exists(m3u8):
        print(f"Couldn't find {m3u8} on disk")
        return
    mp3s = [x.strip() for x in open(m3u8, 'r').readlines() if x.strip().endswith('.mp3')]
    # write a list of mp3s to a temp file that ffmpeg can read out of
    with tempfile.NamedTemporaryFile(mode='w') as tmp:
        output = "\n".join([
            "file '/var/www/html/webtune_live/{}'".format(str(x)) for x in mp3s
        ])
        tmp.write(output)
        os.chown(tmp.name, 1000, 1000)
        tmp.flush()
        output_file = get_output_fn(gameinfo.get('output_filename'))
        if os.path.isfile(output_file):
            os.remove(output_file)
        encode = ['/usr/bin/ffmpeg', '-f', 'concat', '-safe', '0', '-i', tmp.name, '-c', 'copy', output_file]
        try:
            with open('merge.log', 'a') as mergelog:
                result = check_output(encode, stderr=mergelog)
            print("Stored game as {}".format(output_file))
        except Exception as exc:
            print(traceback.format_exc())

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
        'js/custom_local.js': 'custom.js.jinja',
        'js/search.js': 'search.js.jinja'
    }

    address_config = {}
    with open('config.json') as cfg_fp:
        address_config = json.load(cfg_fp)
    if not address_config.get('local_address') or not address_config.get('remote_address'):
        log.info("Must define local_address and remote_address in --config file")
        parser.print_usage()

    for output, templatename in rendermap.items():
        if os.path.exists(output):
            os.remove(output)
        for mp3 in glob.glob('*.mp3'):
            os.remove(mp3)
        with open(output, 'w') as outfp:
            host = address_config.get('remote_address')
            if os.environ.get('DOMAIN'):
                host = "https://{}".format(os.environ.get('DOMAIN'))
            jsfile = "custom.js"
            if 'local' in output:
                host = address_config.get('local_address')
                jsfile = "custom_local.js"

            # querystr = '+'.join(gameinfo_json.get('odds').split()) + '+'
            top_id = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json').json()[0]
            top_story = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{top_id}.json').json()['title']
            from urllib.parse import quote            
            querystr = quote(top_story)
            outfp.write(env.get_template(templatename).render(
                gameinfo=gameinfo,
                away=gameinfo_json.get('away'),
                home=gameinfo_json.get('home'),
                sport=gameinfo_json.get('sport'),
                station_readable=str(station).replace('.', '_'),
                jsfile=jsfile,
                server_host=host,
                local=('local' in output),
                querystr=querystr
            ))
            if output == 'tuner.html':
                json.dumps(gameinfo_json, indent=2)
            outfp.flush()
    check_call(['make', 'deploy'],stdout=DEVNULL,stderr=DEVNULL)

def schedule_tune(config, exit_queue, now=False):
    """
    Tune into the desired station at the desired time, based on the config file.

    Read config file, then sleep until it's time to record
    """
    tcfg = tuner.get(config.get('sport'))
    station = float(tcfg.get('station'))
    duration_seconds = int(os.environ.get("DURATION", tcfg.get('duration') * (60*60)))
    station_hz = int(station * 1000000.0)
    gameinfo_json = config
    capture_command = [
        'pysched/bin/airspy-fmradion',
        '-m', 'fm',
        '-t', 'rtlsdr',
        '-c', 'freq={}'.format(
            station_hz,
        ),
        '-E8',
        '-M',
        '-R', '-'
    ]

    now_time = arrow.utcnow().datetime
    nice_now = arrow.get(now_time).to("America/Chicago").strftime('%Y-%m-%d %I:%M:%S %p')
    
    if now:
        start_at = now_time + datetime.timedelta(seconds=10)
        duration_seconds = 180
    else:
        start_at = arrow.get(iso8601.parse_date(config['scheduled']))

    nice_start = arrow.get(start_at).to('America/Chicago').strftime('%Y-%m-%d %I:%M:%S %p')
    offset = start_at - datetime.timedelta(seconds=600)
    sleep_duration = offset.timestamp() - now_time.timestamp()
    
    # if this is more than 4 hours in the past, don't tune
    if sleep_duration < -1 * 4 * 3600:
        print("Not tuning for {} in {}s in the past".format(config.get('odds'), sleep_duration))
        return None
    
    print(f"Sleeping from {nice_now} until {nice_start} (for {sleep_duration}s) until {config['odds']} starts (OpenAI attempts: {config['metadata']['attempts']})")
    time.sleep(max(3, sleep_duration))
    render_html(config)

    print("Starting recording of {} for {}s".format(config['odds'], duration_seconds))
    pcapture, pencode = tune(station, capture_command)
    try:
        start = datetime.datetime.now()
        stop = datetime.timedelta(seconds=duration_seconds)
        normal_exit = False
        elapsed = 0
        while elapsed < duration_seconds:
            time.sleep(1)
            if pcapture.poll() or pencode.poll():
                raise Exception("Capture/encode process stopped")
            elapsed = (datetime.datetime.now() - start).seconds
            if elapsed % 15 == 0:
                print(f"Recorded for {elapsed}s using PIDs: {pcapture.pid},{pencode.pid}")
        normal_exit = True
        print("Recorded {} from {} to {}".format(
            config['odds'], start, datetime.datetime.now()
        ))
    except:
        import traceback ; traceback.print_exc()
    finally:
        killall(procs=[pcapture,pencode])
        if normal_exit:
            merge(gameinfo_json, station)
    if not exit_queue:
        return normal_exit
    print("Finished tuning and saving recording")
    exit_queue.basic_publish(exchange='', routing_key="schedule", body="exit")
    print("Published exit message")
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
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='rmq', heartbeat=600, blocked_connection_timeout=300))
            channel = connection.channel()
            channel.queue_declare(queue='schedule')
            break
        except Exception as exc:
            time.sleep(5)

    def sched_process(ch, method, properties, body):
        if body.decode('utf-8') == 'exit':
            for id, scheduled in sched_procs.items():
                try:
                    print(f"Terminating proc {id}")
                    sched_procs[id]['proc'].kill()
                except:
                    traceback.print_exc()
            channel.stop_consuming()
            raise ExitCase("Received exit signal")

        config = json.loads(body)
        existing = {}
        dead = []

        # flag dead procs, and check for existing queued recordings
        for id, scheduled in sched_procs.items():
            if id == config.get('id'):
                existing = scheduled
                break

        # first thread wins if 'now' is specified
        if now and sched_procs:
            print("Immediate tune specified, first entry ({}) wins".format(
                list(sched_procs.values())[0]['config']['id']
            ))
            return

        # if a game with this existing id has been scheduled already,
        # make sure this isn't a reschedule event and just continue
        if existing:
            if existing.get('config', {}).get('scheduled') != config.get('scheduled') or existing.get('config', {}).get('odds') != config.get('odds'):
                print("Updating {} ({}): {} {} [{}] -> {} {} [{}]".format(
                    existing['config']['odds'],
                    existing.get('proc'),

                    existing['config']['odds'],
                    existing['config']['day'], existing['config']['time'],
                    existing['config']['id'][0:8],

                    config['odds'],
                    config['day'], config['time'],
                    config['id'][0:8]
                ))
                existing.get('proc').kill()
                del sched_procs[config['id']]
            else:
                message = "Not changing {} already scheduled for: {} {} [{}]".format(
                    existing['config']['odds'],
                    existing['config']['day'], existing['config']['time'],
                    existing['config']['id'][0:8]
                )
                date = datetime.datetime.now().isoformat()
                with open('status.log', 'a') as status:
                    status.write(f'{date}: {message}\n')
                if os.environ.get('DEBUG'):
                    print(message)
                output_file = get_output_fn(existing.get('config')['output_filename'])
                if os.path.isfile(output_file):
                    print(f"{output_file} already exists, killing existing process")
                    sched_procs[existing['config']['id']]['proc'].kill()
                    del sched_procs[existing['config']['id']]
                return

        for proc_id in list(sched_procs.keys()):
            proc_obj = sched_procs.get(proc_id)
            proc = proc_obj.get('proc')
            if not proc or not proc.is_alive():
                print("Removing finished process {}".format(proc_id))
                del sched_procs[proc_id]
                continue

        output_file = get_output_fn(config.get('output_filename'))
        if os.path.isfile(output_file):
            with open('status.log', 'a') as status:
                date = datetime.datetime.now().isoformat()
                status.write(f'{date}: {output_file} already exists, not tuning\n')
            return
        
        future_tune = Process(target=schedule_tune, args=(config, ch,), kwargs={'now': now}, daemon=True, name=config.get('odds', 'generic-' + config.get('day')))
        future_tune.start()
        sched_procs[config['id']] = {
            'config': config,
            'proc': future_tune,
        }

        print("Pending recordings:\n{}".format(
            "\n".join(["{}: {} {} ({})".format(
                i,x['config']['day'] + ' ' + x['config']['time'], x['config']['odds'], get_output_fn(x['config'].get('output_filename'))) for i,x in enumerate(sched_procs.values()) if x['proc'].is_alive()])
        ))

    channel.basic_consume(queue='schedule', on_message_callback=sched_process, auto_ack=True)

    if now:
        print('[Warning] Running in "now" mode')
        print('[Successful] Waiting for RabbitMQ messages from sched container')
    else:
        print('[Successful] Waiting for RabbitMQ messages from sched container')

    channel.start_consuming()

if __name__ == '__main__':
    parser = argparse.ArgumentParser("Tune and stream over web")
    parser.add_argument('--now', action='store_true', help='Start now instead of waiting until time for event')
    parser.add_argument('--sport', choices=list(tuner.keys()))
    print("now it is {}".format(
        arrow.utcnow().strftime('%Y-%m-%d %I:%M:%S %p')
    ))
    args = parser.parse_args()
    render_html({
        'home': "waiting for schedule",
        'away': "pending",
        'sport': "ncaab"
    })
    if args.sport:
        schedule_tune(
            {
                "sport": args.sport,
                "home": "",
                "away": "",
                "scheduled": (arrow.utcnow().naive + datetime.timedelta(seconds=5)).isoformat(),
                "scheduled_cst": (arrow.utcnow().to('US/Central').naive + datetime.timedelta(seconds=5)).isoformat(),
                "odds": tuner.get(args.sport, {}).get('station')
            }, None)
    else:
        try:
            dequeue(now=args.now)
        except ExitCase as exc:
            pass
