#!/usr/bin/env python
"""
Scrape vegasinsider.com for gametime information
"""
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
import time

SOURCES = {
    "ncaab": "https://www.vegasinsider.com/college-basketball/odds/las-vegas/",
    "ncaaf": "https://www.vegasinsider.com/college-football/odds/las-vegas/",
    "nfl": "https://www.vegasinsider.com/nfl/odds/las-vegas/",
    "mlb": "https://www.vegasinsider.com/mlb/odds/las-vegas/"
}

favorites = {
    'nfl': ['Green Bay'],
    'ncaaf': ['Wisconsin'],
    'ncaab': ['Wisconsin'],
    'mlb': ['Milwaukee']
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
    },
    'mlb': {
        'station': 96.7,
        'duration': 5
    }
}

def parse_odds(odds, sport):
    if sport == 'mlb':
        away, home = [x.strip() for x in odds.prettify().replace('</a>', '').split('<br/>')[-2:]]
    else:
        _home = odds.prettify().replace('</a>', '').split('<br/>')[-1].encode('utf-8').split('\xc2\xa0')[0].strip().split('\xc2\xbd')[0].strip()
        home = int(_home)
        away = home * -1
        if home < 0:
            away = "+" + str(away)
        else:
            home = "+" + str(home)
    return (home, away)


def scrape_sport(sport, url):
    """
    Scape the given sport for date/time and opponent info

    1) Pull each table row from site (https://www.vegasinsider.com/mlb/odds/las-vegas/)
    2) Parse out home/away and gameday/time info
    3) Figure out how to translate reported EST to CST (ugly!)
    4) Return gameinfo JSONs in list
    """
    if not url:
        return []
    try:
        src = requests.get(url).text
    except:
        print("Error scraping {}, retrying in 30s")
        time.sleep(30)
        return scrape_sport(sport, url)
    soup = Soup(src, 'html.parser')
    matchups = []
    for matchup in [
            x.parent for x in soup.findAll('span', {'class': 'cellTextHot'})
    ]:
        away_e, home_e = matchup.findAll('b')
        gameday, gametime = matchup.findAll('span').pop().text.split(' ', 1)
        _month, _day = gameday.split('/')

        try:
            home_odds, away_odds = parse_odds(matchup.parent.findAll('a', {'class': 'cellTextNorm'})[0], sport)
        except:
            home_odds, away_odds = ("?", "?")

        month = int(_month)
        day = int(_day)

        now = datetime.datetime.now()
        if now.month > month:
            year = now.year + 1
        else:
            year = now.year

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
        scheduled = arrow.get(est_scheduled_obj).to('UTC')
        scheduled_cst = arrow.get(est_scheduled_obj).to('America/Chicago')
        hl = hashlib.md5()
        hl.update(home_e.text + away_e.text + scheduled.isoformat())
        matchups.append({
            "sport": sport,
            "scheduled": scheduled.isoformat(),
            "scheduled_cst": scheduled_cst.isoformat(),
            "scheduled_at": scheduled.shift(minutes=-10).strftime("%I:%M %p %Y-%m-%d"),
            "scheduled_sort": scheduled_cst.shift(minutes=-10).strftime("%Y-%m-%d %I:%M %p"),
            "day": scheduled.strftime('%m-%d'),
            "time": scheduled.strftime('%I:%M %p'),
            "away": away_e.text,
            "home": home_e.text,
            "odds": "{} ({}) @ {} ({})".format(
                away_e.text, away_odds,
                home_e.text, home_odds
            ),
            "id": hl.hexdigest()
        })
    return matchups

def scrape():
    """
    Scrape all sports
    """
    matchups = []
    for sport, url in SOURCES.items():
        matchups += scrape_sport(sport, url)
    return matchups

def parse_daily(date):
    """
    Normalize date to (to play along with scraper site)

    MM-DD
    """
    return '{}-{}'.format(
        str(date.month).lstrip('0').zfill(2),
        str(date.day).lstrip('0').zfill(2))

def runcommand(command, simulate=False, silent=False):
    """
    Thin wrapper around subprocess for debugging commands
    """
    if not silent:
        print(" ".join([quote(x) for x in command]))
    if simulate:
        return
    return subprocess.check_output(command)

def _ex_q(scriptdir):
    """
    Grab sorted list of existing queued scripts
    """
    if not os.path.exists(scriptdir):
        os.makedirs(scriptdir)
        return []
    return sorted(glob.glob(os.path.join(scriptdir, "*")))

def _write_cat_cfg(fn, config):
    """
    Write a script that we can hand off to at(1) for scheduling
    """
    message = """#!/bin/sh
cat > {fn} << 'EOF'
{cfg}
EOF

pushd ../../
pkill -9 -f softfm
sleep 3
pysched/bin/python tune.py {station} --gameinfo={fn} --duration={duration}hr
popd
""".format(
    fn="/tmp/{}.json".format(os.path.basename(fn)),
    cfg=json.dumps(config, indent=2, sort_keys=True),
    station=tuner.get(config['sport'])['station'],
    duration=tuner.get(config['sport'])['duration'])

    with open(fn, 'w') as script:
        script.write(message)
        script.flush()

def queue(config):
    """
    Add an event to the queued list of events

    param:config - dict of event information

    1) Get the existing queue of events
    2) Verify that this event isn't already queued
    3) Queue this event via at(1)
    """
    print(json.dumps(config, indent=2))
    last = 0
    last_d = "data/scripts"
    # Existing queue
    queued = _ex_q(last_d)
    # Super ugly hashing implementation to ensure that a rescheduled game isn't double-queued
    if queued:
        for x in queued:
            with open(x, 'r') as qfp:
                contents = qfp.read()
                cfg_check = str(config.get('id'))
                print("Checking for {} in {}".format(cfg_check, qfp.name))
                if cfg_check in contents:
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
    """
    Scrape all upcoming events for my favorite teams over the next couple of days
    """
    print("Current time is: {}".format(
        datetime.datetime.now()
    ))
    matchups = scrape()
    upcoming = []
    for matchup in sorted(matchups, key=lambda x: x['scheduled']):
        for favorite in favorites[matchup["sport"]]:
            if favorite in str(matchup):
                queue(matchup)

if __name__ == "__main__":
    schedule()
