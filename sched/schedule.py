#!pysched/bin/python
"""
Scrape vegasinsider.com for gametime information
"""
from bs4 import BeautifulSoup as Soup

# requests for scraping odds sites
import requests

# arrow for datetime / timezone conversions
import arrow

# pika for rabbitmq integration
import pika

from pipes import quote

import datetime
import glob
import json
import os
import subprocess
import sys
import hashlib
import time
import traceback

SOURCES = {
    "ncaab": "https://www.vegasinsider.com/college-basketball/teams/{}/",
    "ncaaf": "https://www.vegasinsider.com/college-football/teams/{}/",
    "nfl": "https://www.vegasinsider.com/nfl/teams/{}/",
    "mlb": "https://www.vegasinsider.com/mlb/odds/las-vegas/"
}

favorites = {
    'nfl': ['Packers'],
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
    }
}

def is_float(inp):
    try:
        float(inp)
        return True
    except:
        pass
    return False

def parse_odds(odds_string):
    try:
        home_odds_r = float(odds_string.split()[-1])
        away_odds_r = home_odds_r * -1
        home_odds = str(home_odds_r)
        away_odds = str(away_odds_r)
        if home_odds_r > 0:
            home_odds = "+" + str(home_odds_r)
        if away_odds_r > 0:
            away_odds = "+" + str(away_odds_r)        
        return home_odds, away_odds
    except:
        return '?', '?'

def scrape_matchup(url, rel_url, sport, favorite):
    matchup_url = url + '../../..' + rel_url
    try:
        src = requests.get(matchup_url).text        
    except:
        print("Error scraping matchup url {}, retrying in 30s".format(matchup_url))
        time.sleep(30)
        return scrape_matchup(url, rel_url)

    try:
        soup = Soup(src, 'html.parser')
        datestr = ' '.join(soup.findAll('span', {'class': 'text-white'})[0].text.replace(',', '').split())
        teams = ' '.join(sorted([ x.text.strip() for x in soup.findAll('div') if favorite in x.text and '@' in x.text ], key=lambda y: len(y))[0].split())
        away, home = teams.split(' @ ', 1)
        home_odds, away_odds = parse_odds("")
        scheduled_est = arrow.get(datestr.replace(' ET', ' US/Eastern'), 'ddd MMM D YYYY h:mm A ZZZ')
    except Exception as exc:
        print("Unable to parse {}\n{}".format(matchup_url, exc))
        # traceback.print_exc()
        # sys.exit(1)
        return None

    hl = hashlib.md5()
    hl.update((home + away + sport).encode('utf-8'))
    scheduled = scheduled_est.to('UTC')
    scheduled_cst = scheduled_est.to('US/Central')
    matchup = {
        "sport": sport,
        "raw_date": datestr,
        "scheduled": scheduled.isoformat(),
        "scheduled_cst": scheduled_cst.isoformat(),
        "scheduled_at": scheduled.shift(minutes=-10).strftime("%I:%M %p %Y-%m-%d"),
        "scheduled_sort": scheduled_cst.shift(minutes=-10).strftime("%Y-%m-%d %I:%M %p"),
        "day": scheduled_cst.format("ddd MMM Do YYYY"),
        "time": scheduled_cst.format('h:mm A'),
        "away": away,
        "home": home,
        "odds": "{} ({}) @ {} ({})".format(
            away, away_odds,
            home, home_odds
        ),
        "id": hl.hexdigest()
    }
    return matchup

def scrape_sport_favorite(sport, url, favorite):
    url = url.format(favorite)
    try:
        src = requests.get(url).text
    except:
        print("Error scraping {}, retrying in 30s".format(url))
        time.sleep(30)
        return scrape_sport(sport, url, favorite)
    soup = Soup(src, 'html.parser')
    matchups = []
    for matchup in [x for x in soup.findAll('div', {'class': 'flex-equalize pr-2'})]:
        matchup_link = matchup.findAll('a', {'class': 'matchup-link'})[0].get('href')
        scraped = scrape_matchup(url, matchup_link, sport, favorite)
        if scraped is not None:
            matchups.append(scraped)
    return matchups

def scrape_sport(sport, url, favorites):
    """
    Scape the given sport for date/time and opponent info

    1) Pull each table row from site (https://www.vegasinsider.com/mlb/odds/las-vegas/)
    2) Parse out home/away and gameday/time info
    3) Figure out how to translate reported EST to CST (ugly!)
    4) Return gameinfo JSONs in list
    """
    if not url:
        return []
    matchups = []
    for favorite in favorites:
        matchups += scrape_sport_favorite(sport, url, favorite)
    return matchups

def scrape():
    """
    Scrape all sports
    """
    matchups = []
    for sport, url in SOURCES.items():
        matchups += scrape_sport(sport, url, favorites.get(sport, []))
    return matchups

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

def queue(config, rmq, queuename='schedule'):
    """
    Add a queue object to rabbitmq
    """
    rmq.basic_publish(exchange='', routing_key=queuename, body=json.dumps(config))
    print("Queued: {} [{}]".format(config.get('odds'), config.get('id')))

def schedule(skipmq=False):
    """
    Scrape all upcoming events for my favorite teams over the next couple of days
    """
    print("Current time is: {}".format(
        datetime.datetime.now()
    ))
    matchups = scrape()
    upcoming = []
    rmq = None
    queuename = 'schedule'
    for matchup in sorted(matchups, key=lambda x: x['scheduled']):
        for favorite in favorites[matchup["sport"]]:
            if skipmq is False and rmq is None:                
                for x in range(5):
                    print("RabbitMQ connection attempt {}".format(x))
                    try:
                        rmq = pika.BlockingConnection(pika.ConnectionParameters('rmq'))
                        channel = rmq.channel()
                        channel.queue_declare(queue=queuename)
                        break
                    except Exception as exc:
                        print("Unsuccesful attempt {}".format(x))
                        if x == 4:
                            traceback.print_exc()
                        time.sleep(5)
                if rmq is None:
                    sys.exit(1)
                else:
                    print("Connection sucessful")
            if favorite in str(matchup):
                if skipmq is False:
                    queue(matchup, channel)
    if rmq:
        print("Closing RMQ connection")
        rmq.close()

if __name__ == "__main__":
    while True:
        schedule(skipmq=True)
        time.sleep(600)
