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
from urllib.parse import urlparse, urljoin

import argparse
import datetime
import glob
import math
import json
import os
import subprocess
import sys
import hashlib
import time
import traceback
import random

TEAM_MAP = {
    "Wisconsin": "wisconsin-badgers",
    "Packers": "green-bay-packers",
    "Milwaukee": {
        "nba": "Bucks",
        "mlb": "Brewers",
    }
}

SOURCES = {
    "mlb": "https://www.sportsline.com/mlb/picks/",
    "ncaaf": "https://www.sportsline.com/college-football/picks/",
    "nfl": "https://www.sportsline.com/nfl/picks/",
    "ncaab": "https://www.sportsline.com/college-basketball/picks/",
    "nba": "https://www.sportsline.com/nba/picks/"
}

preferred_odds = {
    "mlb": "moneyLine",
    "ncaaf": "spread",
    "nba": "spread",
    "nfl": "spread",
    "ncaab": "spread"
}

favorites = {
    'nfl': ['Packers-gb'],
    'ncaaf': ['Wisconsin-WIS'],
    'ncaab': ['Wisconsin-WIS'],
    'nba': ['milwaukee'],
    'mlb': ['milwaukee-mil']
}

seasons = {
    "mlb": "summer",
    "nfl": "winter",
    "ncaab": "winter",
    "nba": "winter",
    "ncaaf": "winter"
}


leagues = {
    "ncaaf": 2,
    "ncaab": 116,
    "mlb": 1,
    "nfl": 1
}

def scrape_matchup(matchup_blob, headers, sport):
    try:
        datestr = matchup_blob.get('date')['start']
    except:
        datestr = matchup_blob.get('date')

    scheduled = arrow.get(datestr).to('UTC')
    scheduled_cst = arrow.get(datestr).to('America/Chicago')

    matchup_blob["teams"] = {
        "home": {
            "name": matchup_blob["home"]
        },

        "away": {
            "name": matchup_blob["away"]
        }
    }
    
    home = matchup_blob["teams"]["home"]["name"]

    try:
        away = matchup_blob["teams"]["away"]["name"]
    except:
        away = matchup_blob["teams"]["visitors"]["name"]
    
    odds = matchup_blob.get('odds')

    day = scheduled_cst.format("ddd MMM Do YYYY")
    time = scheduled_cst.format('h:mm A')

    nice_away = away.replace('.','')
    nice_home = home.replace('.','')
    date_day = scheduled_cst.format('YYYY-MM-DD-hh-mm-A')
    output_filename = "-".join(f"{nice_away}-vs-{nice_home}-{sport}-{date_day}".split())
    
    hl = hashlib.md5()
    hl.update((home + away + sport + day).encode('utf-8'))
    
    matchup = {
        "sport": sport,
        "raw_date": datestr,
        "scheduled": scheduled.isoformat(),
        "scheduled_cst": scheduled_cst.isoformat(),
        "scheduled_at": scheduled_cst.shift(minutes=-10).strftime("%I:%M %p %Y-%m-%d"),
        "scheduled_sort": scheduled_cst.shift(minutes=-10).strftime("%Y-%m-%d %I:%M %p"),
        "day": day,
        "time": time,
        "away": away,
        "home": home,
        "odds": "{} ({}) @ {} ({})".format(
            away, odds.get('away'),
            home, odds.get('home')
        ),
        "output_filename": output_filename,
        "id": hl.hexdigest()
    }

    print("Queuing {odds} {day} {time}".format(
        odds=matchup['odds'],
        day=matchup['day'],
        time=matchup['time']
    ))

    return matchup

def puppet_scrape(url):
    script = ""
    with open('sportsline.js') as sp:
        script = sp.read().replace('SCRAPE_URL', url)
    puppet_cmd = ['docker', 'run', '--dns', '192.168.0.102', '-i', '--init', '--cap-add=SYS_ADMIN', '--rm', 'ghcr.io/puppeteer/puppeteer:latest', 'node', '-e', script]
    return subprocess.check_output(puppet_cmd)

def scrape_sport_favorite(sport, url, favorite):
    url = url.format(TEAM_MAP.get(favorite, favorite))

    hl = hashlib.md5()
    hl.update(str(datetime.datetime.now()).encode('utf-8'))

    host = urlparse(url).netloc

    headers = {
        'User-Agent': hl.hexdigest()
    }

    data = {
        "errors": None
    }

    try:
        src = puppet_scrape(url)
        soup = Soup(src, features="html.parser")
        data["soup"] = soup
        data["response"] = [ x for x in soup.find_all('a') if 'Matchup Analysis' in x.text ]
    except:
        data['errors'] = traceback.format_exc()
        
    if data['errors']:
        print(json.dumps(data, indent=2))
        return []

    matchups = []
    seen = set()
    for _matchup in sorted(x.get('href') for x in data['response']):        
        fav_match = False
        for chunk in favorite.split('-'):
            if len(chunk) == 1:
                raise f"{chunk} is only 1 character long!"
            if chunk.lower() in _matchup.lower():
                fav_match = True
        if not fav_match:
            with open('/tmp/schedule_skip.log', 'a') as sk:
                sk.write(f"{_matchup} does not look like it involves {favorite}\n")
                sk.flush()
            continue
        print(f"{_matchup} looks like it involves {favorite}")
        matchup_soup = Soup(requests.get(urljoin(url, _matchup)).text, features="html.parser")
        
        try:
            json_info = json.loads(matchup_soup.findAll('script', {'type':'application/json'})[0].string).get('props', {}).get('pageProps',{}).get('data', {}).get('gameByAbbr')
            date = arrow.get(json_info.get('scheduledTime')).to('America/Chicago')
            home = f"{json_info['homeTeam']['location']} {json_info['homeTeam']['nickName']}"
            away = f"{json_info['awayTeam']['location']} {json_info['awayTeam']['nickName']}"            
        except:
            print("Unable to grab JSON info off of webpage")
            continue
        
        odds = {
            "home": "pk",
            "away": "pk"
        }

        try:
            preferred_line = preferred_odds.get(sport)
            if preferred_line == 'moneyLine':
                key = 'outcomeOdds'
            else:
                key = 'value'
            odds['home'] = json_info['odds'][preferred_line]['home'][key]
            odds['away'] = json_info['odds'][preferred_line]['away'][key]
        except:
            pass
        
        matchup = {
            "date": date.isoformat(),
            "home": home,
            "away": away,
            "odds": odds
        }

        matchups.append(scrape_matchup(matchup, headers, sport))
        
    return matchups

def scrape_sport(sport, url, favorite_list):
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
    for favorite in favorite_list:
        matchups += scrape_sport_favorite(sport, url, favorite)
    return matchups

def scrape():
    """
    Scrape all sports
    """
    matchups = []
    for sport, url in SOURCES.items():
        favorite_list = favorites.get(sport, [])
        print(f"Scraping {sport} from {url} using {favorite_list}")
        matchups += scrape_sport(sport, url, favorite_list)
    return matchups

def queue(config, rmq, queuename='schedule'):
    """
    Add a queue object to rabbitmq
    """
    rmq.basic_publish(
        exchange='',
        routing_key=queuename,
        body=json.dumps(config)
    )
    print("Queued: {} [{}]".format(config.get('odds'), config.get('id')))

def rmq_connect():
    queuename = 'schedule'
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
        return rmq, channel
    return None, None

def schedule(skipmq=False, show_time_only=False):
    """
    Scrape all upcoming events for my favorite teams over the next couple of days

    skipmq: don't try to add to rabbitmq
    show_time_only: show timestamp of first event (for passing to libfaketime)
    """
    matchups = scrape()
    upcoming = []
    rmq = None
    for matchup in sorted(matchups, key=lambda x: x['scheduled']):
        if skipmq is False and rmq is None:
            rmq, channel = rmq_connect()
        if skipmq is False:
            queue(matchup, channel)
        else:
            if show_time_only:
                offset_time = (
                    arrow.get(matchup['scheduled']).datetime - datetime.timedelta(minutes=10, seconds=30)).strftime('%Y-%m-%d %H:%M:%S')
                print(f"FAKETIME=@{offset_time}")
            else:
                print(matchup['odds'])
    if rmq:
        print("Closing RMQ connection")
        rmq.close()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
    
    parser = argparse.ArgumentParser("Schedule events based on published odds")
    parser.add_argument('--time', action='store_true', help='Show time of events only')
    args = parser.parse_args()
    
    while True:
        try:
            schedule(skipmq=True, show_time_only=args.time)
            if args.time:
                break
            time.sleep(1000)
        except:
            traceback.print_exc()
            time.sleep(100000)
