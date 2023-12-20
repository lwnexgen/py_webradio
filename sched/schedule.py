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

from urllib.parse import urlparse, urljoin

from content_scraper.python_scrape import main as ai_scrape

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

#     "nba": "https://www.sportsline.com/nba/picks/"
#     'nba': ['MIL'],
SOURCES = {
    "mlb": "https://www.sportsline.com/mlb/picks/",
    "ncaaf": "https://www.sportsline.com/college-football/picks/",
    "nfl": "https://www.sportsline.com/nfl/picks/",
    "ncaab": "https://www.sportsline.com/college-basketball/picks/"
}

favorites = {
    'nfl': ['GB'],
    'ncaaf': ['WISC'],
    'ncaab': ['WISC'],
    'mlb': ['MIL']
}

def scrape_sport_favorite(sport, url, favorite):
    cfg = {
        'debug': False,
        'odds_url': url,
        'team': favorite,
        'sport': sport,
        'endpoint': "https://api.openai.com/v1"
    }
    scraped = ai_scrape(cfg)
    try:
        matchups = json.loads(str(scraped))
        return matchups
    except:
        print(os.getcwd())
        print(scraped)
        raise

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

def scrape(to_scrape=None):
    """
    Scrape all sports
    """
    matchups = []
    if to_scrape:
        srcs = {
            to_scrape: SOURCES.get(to_scrape)
        }
    else:
        srcs = SOURCES
    for sport, url in srcs.items():
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
    print(f"Queued: {config['odds']} [{config['id']}] (API attempts: {config['metadata']['attempts']})")

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

def schedule(skipmq=False, show_time_only=False, sport='*'):
    """
    Scrape all upcoming events for my favorite teams over the next couple of days

    skipmq: don't try to add to rabbitmq
    show_time_only: show timestamp of first event (for passing to libfaketime)
    """
    if sport == '*':
        matchups = scrape()
    else:
        matchups = scrape(to_scrape=sport)
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
    parser.add_argument('--sport', choices=list(SOURCES.keys()))
    parser.add_argument('--time', action='store_true', help='Show time of events only')
    args = parser.parse_args()
    
    while True:
        try:
            sport = '*'
            if args.sport:
                sport = args.sport
            schedule(skipmq=True, show_time_only=args.time, sport=sport)
            if args.time:
                break
            time.sleep(1000)
        except:
            traceback.print_exc()
            time.sleep(100000)
