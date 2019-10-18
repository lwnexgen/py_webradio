#!/usr/bin/env python
from bs4 import BeautifulSoup as Soup

from pipes import quote

import datetime
import glob
import json
import os
import requests
import subprocess
import arrow
import sys
import hashlib

SOURCES = {
    "ncaab": "http://www.vegasinsider.com/college-basketball/odds/las-vegas/",
    "ncaaf": "http://www.vegasinsider.com/college-football/odds/las-vegas/",
    "nfl": "http://www.vegasinsider.com/nfl/odds/las-vegas/"
}

favorites = {
    'nfl': ['Green Bay'],
    'ncaaf': ['Wisconsin'],
    'ncaab': ['Wisconsin']
}

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
    }
}

def scrape_sport(sport, url):
    if not url:
        return []
    src = requests.get(url).text
    soup = Soup(src, 'html.parser')
    matchups = []
    for matchup in [
            x.parent for x in soup.findAll('span', {'class': 'cellTextHot'})
    ]:
        away_e, home_e = matchup.findAll('b')
        gameday, gametime = matchup.findAll('span').pop().text.split(' ', 1)
        month, day = gameday.split('/')
        now = datetime.datetime.now()
        if now.month > month:
            year = now.year + 1
        elif month >= now.month:
            if day > now.day:
                year = now.year
            elif day == now.day:
                raise Exception("Weird schedule alert")
            elif day < now.day:
                year = now.year + 1
        time_s, period = gametime.split()
        hour_s, minute_s = time_s.split(':')
        hour = int(hour_s)
        minute = int(minute_s)
        if period == 'PM':
            if hour < 12:
                hour += 12
        try:
            est_scheduled_obj = arrow.get(
                datetime.datetime(year, int(month), int(day), hour, minute, 0, 0),
                "US/Eastern"
            )
        except:
            import traceback ; traceback.print_exc()
            import pdb ; pdb.set_trace()
        scheduled = arrow.get(est_scheduled_obj).to('US/Central')
        hl = hashlib.md5()
        hl.update(home_e.text + away_e.text + scheduled.isoformat())
        matchups.append({
            "sport": sport,
            "scheduled": scheduled.isoformat(),
            "scheduled_at": scheduled.shift(minutes=-10).strftime("%I:%M %p %Y-%m-%d"),
            "day": scheduled.strftime('%m-%d'),
            "time": scheduled.strftime('%I:%M %p'),
            "away": away_e.text,
            "home": home_e.text,
            "id": hl.hexdigest()
        })
    return matchups

def scrape():
    matchups = []
    for sport, url in SOURCES.items():
        matchups += scrape_sport(sport, url)
    return matchups

def parse_daily(date):
    return '{}-{}'.format(
        str(date.month).lstrip('0').zfill(2),
        str(date.day).lstrip('0').zfill(2))

def runcommand(command, simulate=False, silent=False):
    if not silent:
        print " ".join([quote(x) for x in command])
    if simulate:
        return
    return subprocess.check_output(command)

def _ex_q(scriptdir):
    if not os.path.exists(scriptdir):
        os.makedirs(scriptdir)
        return []
    return sorted(glob.glob(os.path.join(scriptdir, "*")))

def _write_cat_cfg(fn, config):
    with open(fn, 'w') as script:
        script.write("""#!/bin/sh
cat > {fn} << 'EOF'
{cfg}
EOF

pushd ../../
pkill -9 -f softfm
sleep 3
python tune.py {station} --gameinfo={fn} --duration={duration}hr 2>&1 | grep -v "Opening '/var" | tee /tmp/webtune.log
popd
""".format(
    fn="/tmp/{}.json".format(os.path.basename(fn)),
    cfg=json.dumps(config, indent=2, sort_keys=True),
    station=tuner.get(config['sport'])['station'],
    duration=tuner.get(config['sport'])['duration']))

def queue(config):
    print(json.dumps(config, indent=2))
    last = 0
    last_d = "data/scripts"
    queued = _ex_q(last_d)
    if queued:
        for x in queued:
            if str(config['id']) in open(x).read():
                print("Already have {} @ {} queued".format(config['away'], config['home']))
                return
        last = int(os.path.basename(queued[-1]).split('_')[0])
    script = (os.path.join(last_d, "{}_{}_{}".format(
        str(last + 1).zfill(2),
        config['away'].replace(' ', "-"),
        config['home'].replace(' ', "-")))
    )
    _write_cat_cfg(script, config)
    pwd = os.getcwd()
    try:
        os.chdir(last_d)
        at_command = ['at', '-f', os.path.basename(script), config['scheduled_at']]
        runcommand(at_command)
    except:
        import traceback
        traceback.print_exc()
    finally:
        os.chdir(pwd)

def schedule():
    matchups = scrape()
    upcoming = []
    for matchup in sorted(matchups, key=lambda x: x['scheduled']):
        for favorite in favorites[matchup["sport"]]:
            if favorite in str(matchup):
                queue(matchup)

if __name__ == "__main__":
    schedule()
