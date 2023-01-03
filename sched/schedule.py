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
    "ncaab": "https://www.actionnetwork.com/ncaab/odds/{}",
    "ncaaf": "https://www.actionnetwork.com/ncaaf/odds/{}",
    "nfl": "https://www.actionnetwork.com/nfl/odds/{}",
    "nba": "https://www.actionnetwork.com/nba/odds/{}"
}

favorites = {
    'nfl': ['Packers'],
    'ncaaf': ['Wisconsin'],
    'ncaab': ['Wisconsin'],
    'nba': ['milwaukee-bucks'],
    'mlb': ['milwaukee-brewers']
}

def parse_odds(soup):
    home_spread = "?"
    away_spread = "?"

    try:
        options = [x for x in soup.findAll('thead') if 'Spread' in x.text][0]
        away_spread = options.parent.findAll('div', { 'data-testid': 'book-cell__odds' })[0].findAll('span')[0].text
        home_spread = options.parent.findAll('div', { 'data-testid': 'book-cell__odds' })[3].findAll('span')[0].text
    except:
        pass

    return home_spread, away_spread

def scrape_matchup(url, rel_url, sport, favorite, headers):
    matchup_url = url + '/../../..' + rel_url
    try:
        src = requests.get(matchup_url, headers=headers).text
    except:
        print("Error scraping matchup url {}, retrying in 30s".format(matchup_url))
        time.sleep(30)
        return scrape_matchup(url, rel_url)

    try:
        soup = Soup(src, 'html.parser')
        datestr = soup.findAll('div', {'class': 'game-odds__date-container'})[0].text
        scheduled_utc = arrow.get(datestr.replace('a.m.', 'AM ').replace('p.m.', 'PM ') + ' UTC', 'dddd h:mm A MMMM D, YYYY')
        scheduled_est = scheduled_utc.to('US/Eastern')
        teams = soup.findAll('h1', {'class': 'game-odds__title'})[0].text.replace(' Odds', '')
        away, home = teams.split(' vs. ', 1)

        now_utc = arrow.utcnow()
        how_long = scheduled_utc.timestamp - now_utc.timestamp

        if how_long < 0 and math.fabs(how_long) > 4 * 3600:
            with open('schedule_skip.log', 'a') as sc:
                sc.write(f"Not scheduling a game ({away} @ {home}) more than 4hrs old\n")
                sc.flush()
            return None

        try:
            home_odds, away_odds = parse_odds(soup)
        except:
            home_odds, away_odds = '?', '?'
    except Exception as exc:
        with open("schedule_skip.log", "a") as sc:
            sc.write(f"Unable to parse {matchup_url}\n{exc}\n")
            sc.flush()
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
    url = url.format(TEAM_MAP.get(favorite, favorite))

    hl = hashlib.md5()
    hl.update(str(datetime.datetime.now()).encode('utf-8'))

    headers = {
        'User-Agent': hl.hexdigest()
    }

    try:
        src = requests.get(url, headers=headers).text
    except:
        print("Error scraping {}, retrying in 30s".format(url))
        time.sleep(30)
        return scrape_sport(sport, url, favorite)

    soup = Soup(src, 'html.parser')
    matchups = []
    for matchup in [x for x in soup.findAll('a', {'class': 'next-game__details-link'})]:
        matchup_link = matchup.get('href')
        scraped = scrape_matchup(url, matchup_link, sport, favorite, headers)
        if scraped is not None:
            matchups.append(scraped)
            break
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
                offset_time = (arrow.get(matchup['scheduled']).datetime - datetime.timedelta(minutes=10, seconds=30)).strftime('%Y-%m-%d %H:%M:%S')
                print(f"FAKETIME=@{offset_time}")
                break
            else:
                print(matchup['odds'])
    if rmq:
        print("Closing RMQ connection")
        rmq.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Schedule events based on published odds")
    parser.add_argument('--time', action='store_true', help='Show time of events only')
    args = parser.parse_args()

    while True:
        schedule(skipmq=True, show_time_only=args.time)
        time.sleep(5)
        if args.time:
            break
