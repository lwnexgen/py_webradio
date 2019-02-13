#!/usr/bin/env python
NCAABKEY="58xm6vpkyrjyg7ez893k3bg4"
NCAAFKEY="n5spfw2s49vu8u9ycmkjt84g"
NFLKEY="chr2gwpheb8gycxzrrm6989d"

from pipes import quote

import argparse
import datetime
import sys
import os
import subprocess
import glob
import json

import iso8601
import requests
import tablib
import time

from sports.nfl import schedule as nflsched
from sports.ncaab import schedule as ncaabsched
from sports.ncaaf import schedule as ncaafsched

schedules = {
    'nfl': nflsched,
    'ncaab': ncaabsched,
    'ncaaf': ncaafsched
}

apikeys = {
    'nfl': NFLKEY,
    'ncaab': NCAABKEY,
    'ncaaf': NCAAFKEY
}

favorites = {
    'nfl': ['GB'],
    'ncaaf': ['WIS'],
    'ncaab': ['WIS']
}

tuner = {
    'nfl': {
        'station': 101.5,
        'duration': 3.5
    },
    'ncaab': {
        'station': 101.5,
        'duration': 3.0,
    },
    'ncaaf': {
        'station': 101.5,
        'duration': 4.5
    }
}

def undefined(*args, **kwargs):
    raise NotImplementedError()

OFFSET = -6

parser = argparse.ArgumentParser("Schedule radio broadcast tuning")
parser.add_argument("--sport", 
                    default='all', 
                    choices=apikeys.keys())
parser.add_argument('--subset', default='favorites', 
                    choices=['favorites', 'all'])
parser.add_argument('--date', default='default')
parser.add_argument('--daemon', action='store_true')
parser.add_argument('--sim', action='store_true')

def parse_daily(date):
    return '{}-{}-{}'.format(date.year, 
                             date.month, 
                             str(date.day).lstrip('0').zfill(2))

def get_schedule(sports, date, favorite_teams=None):
    table = tablib.Dataset(headers=['sport', 'game', 'date', 'time', 'id'])
    for sport in sports:
        favorites = favorite_teams.get(sport)
        apikey = apikeys.get(sport)
        schedule = schedules.get(sport, undefined)(apikey, date)
        for game in sorted(schedule, key=lambda x: x.get('scheduled')):
            home = game.get('home')
            away = game.get('away')
            if isinstance(home, dict):
                home = home.get('alias')
                away = away.get('alias')
            if len(home) > 5:
                home = 'TBD'
            if len(away) > 5:
                away = 'TBD'
            fulltime = (iso8601.parse_date(game.get('scheduled')) + \
                   datetime.timedelta(hours=OFFSET))
            gamedate = parse_daily(fulltime)
            gametime = fulltime.strftime("%I:%M %p")
            if gamedate != date:
                continue
            if favorite_teams:
                if not (home in favorites or away in favorites):
                    continue
            table.append(
                [sport, '{}@{}'.format(away, home), gamedate, gametime, game.get('id')]
            )
    return table.sort('date')

def runcommand(command, simulate=False, silent=False):
    if not silent:
        print " ".join([quote(x) for x in command])
    if simulate:
        return
    return subprocess.check_output(command)

def find_game(sport, game_id):
    schedule = schedules.get(sport, undefined)(apikeys.get(sport),
                                               parse_daily(datetime.datetime.now()))
    for game in schedule:
        if game.get('id') == game_id:
            return game

if __name__ == '__main__':
    args = parser.parse_args()
    if args.sport != 'all':
        raise NotImplementedError("Must use all sports for now")

    sports = ['nfl', 'ncaab', 'ncaaf']

    if args.date == 'default':
        today = parse_daily(datetime.datetime.now())
    else:
        today = args.date

    if not args.daemon or args.date != 'default':
        print get_schedule(sports, today, favorites)
        if not args.sim:
            sys.exit(0)
    
    while True:
        scheduledir = 'schedule/{}.d'.format(today)
        try:
            os.makedirs(scheduledir)
        except:
            pass
        print "Scheduling for {}".format(today)
        sched = get_schedule(sports, today, favorites)
        for row in sched:
            gameday = row[sched.headers.index('date')]
            gametime = row[sched.headers.index('time')]
            schedulefile = '{}_{}.at'.format(
                gameday.replace(' ', '_'),
                gametime.replace(' ', '_')
            )
            tuner_info = tuner.get(row[sched.headers.index('sport')])
            gameinfofn = "{}/{}_{}.json".format(
                scheduledir,
                row[sched.headers.index('game')].replace('@', '-at-'),
                row[sched.headers.index('time')].replace(':', '_').replace(
                    ' ', ''
                )
            )
            game_json = find_game(row[sched.headers.index('sport')],
                                  row[sched.headers.index('id')])
            if game_json:
                with open(gameinfofn, 'w') as ginf:
                    ginf.write(
                        json.dumps(game_json, indent=2, sort_keys=True)
                    )
            with open('{}/{}'.format(scheduledir, schedulefile),'w') as atf:
                if game_json:
                    atf.write(
                        "python tune.py {station} --duration {duration}hr --gameinfo {gameinfo}".format(
                            duration=tuner_info.get('duration'),
                            station=tuner_info.get('station'),
                            gameinfo=gameinfofn
                        ))
                else:
                    atf.write(
                        "python tune.py {station} --duration {duration}hr".format(
                            duration=tuner_info.get('duration'),
                            station=tuner_info.get('station')
                        ))                        

        # Remove current at queue entries
        cqs = runcommand(['atq'], silent=True)
        for j in cqs.strip().split('\n'):
            if not j:
                continue
            jid = j.split()[0]
            runcommand(['atrm', jid], simulate=args.sim)
    
        # Build atqueue from schedule
        for atfile in glob.glob('{}/*.at'.format(scheduledir)):
            attime = os.path.basename(atfile).split('.')[0]
            attd = datetime.datetime.strptime(attime, '%Y-%m-%d_%I:%M_%p')
            attime = (attd - datetime.timedelta(minutes=10)).strftime(
                '%I:%M%p'
            )
            print runcommand(['at', '-f', atfile, attime], simulate=args.sim)
                
        if args.sim:
            sys.exit(0)

        # Reset today flag
        newtime = parse_daily(datetime.datetime.now())
        if newtime == today:
            sleep = (60 * 60 * 4)
            print "Sleeping {} seconds".format(sleep)
            time.sleep(sleep)
            today = parse_daily(datetime.datetime.now())
            continue
