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
from content_scraper.llama_cpp import massage
from content_scraper.oddsapi import ncaab_odds

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
import requests

from pathlib import Path

sports = ["ncaab", "ncaaf", "nfl", "mlb"]
keys = [
    "sport",
    "away",
    "home",
    "iso_8601_utc_date",
    "point_spread",
]

# map of city -> nickname for nfl teams
nfl_nicknames = {
    "Arizona": "Cardinals",
    "Atlanta": "Falcons",
    "Baltimore": "Ravens",
    "Buffalo": "Bills",
    "Carolina": "Panthers",
    "Chicago": "Bears",
    "Cincinnati": "Bengals",
    "Cleveland": "Browns",
    "Dallas": "Cowboys",
    "Denver": "Broncos",
    "Detroit": "Lions",
    "Green Bay": "Packers",
    "Houston": "Texans",
    "Indianapolis": "Colts",
    "Jacksonville": "Jaguars",
    "Kansas City": "Chiefs",
    "Las Vegas": "Raiders",
    "Los Angeles": ["Rams", "Chargers"],
    "L.A.": ["Rams", "Chargers"],
    "Miami": "Dolphins",
    "Minnesota": "Vikings",
    "New England": "Patriots",
    "New Orleans": "Saints",
    "New York": ["Giants", "Jets"],
    "N.Y.": ["Giants", "Jets"],
    "Philadelphia": "Eagles",
    "Pittsburgh": "Steelers",
    "San Francisco": "49ers",
    "Seattle": "Seahawks",
    "Tampa Bay": "Buccaneers",
    "Tennessee": "Titans",
    "Washington": "Commanders"
}
# map of city -> nickname for nba teams
nba_nicknames = {
    "Atlanta": "Hawks",
    "Boston": "Celtics",
    "Brooklyn": "Nets",
    "Charlotte": "Hornets",
    "Chicago": "Bulls",
    "Cleveland": "Cavaliers",
    "Dallas": "Mavericks",
    "Denver": "Nuggets",
    "Detroit": "Pistons",
    "Golden State": "Warriors",
    "Houston": "Rockets",
    "Indiana": "Pacers",
    "Los Angeles": ["Lakers", "Clippers"],
    "L.A.": ["Lakers", "Clippers"],
    "Memphis": "Grizzlies",
    "Miami": "Heat",
    "Milwaukee": "Bucks",
    "Minnesota": "Timberwolves",
    "New Orleans": "Pelicans",
    "New York": "Knicks",
    "N.Y.": "Knicks",    
    "Oklahoma City": "Thunder",
    "Orlando": "Magic",
    "Philadelphia": "76ers",
    "Phoenix": "Suns",
    "Portland": "Trail Blazers",
    "Sacramento": "Kings",
    "San Antonio": "Spurs",
    "Toronto": "Raptors",
    "Utah": "Jazz",
    "Washington": "Wizards"
}

# map of city -> nickname for MLB teams
mlb_nicknames = {
    "Arizona": "Diamondbacks",
    "Atlanta": "Braves",
    "Baltimore": "Orioles",
    "Boston": "Red Sox",
    "Chicago": ["White Sox", "Cubs"],
    "Cincinnati": "Reds",
    "Cleveland": "Indians",
    "Colorado": "Rockies",
    "Detroit": "Tigers",
    "Houston": "Astros",
    "Kansas City": "Royals",
    "Los Angeles": ["Dodgers", "Angels"],
    "L.A.": ["Dodgers", "Angels"],
    "Miami": "Marlins",
    "Milwaukee": "Brewers",
    "Minnesota": "Twins",
    "New York": ["Yankees", "Mets"],
    "N.Y.": ["Yankees", "Mets"],
    "Oakland": "Athletics",
    "Philadelphia": "Phillies",
    "Pittsburgh": "Pirates",
    "San Diego": "Padres",
    "San Francisco": "Giants",
    "Seattle": "Mariners",
    "St. Louis": "Cardinals",
    "Tampa Bay": "Rays",
    "Texas": "Rangers",
    "Toronto": "Blue Jays",
    "Washington": "Nationals"
}

# map of city -> nickname for NCAA basketball teams
# there should be about 350 of these
ncaa_nicknames = json.load(open('teams2.json', 'r'))

nicknames = {
    "nfl": nfl_nicknames,
    "nba": nba_nicknames,
    "ncaab": ncaa_nicknames,
    "ncaaf": ncaa_nicknames,
    "mlb": mlb_nicknames,
}

# 'nba': "https://www.sportsline.com/nba/picks/"
# 'nba': ['MIL'],
# 'mlb': "https://www.sportsline.com/mlb/picks/",
# 'mlb': ['MIL', 'Milwaukee Brewers'],
SOURCES = {
    "ncaaf": "https://www.sportsline.com/college-football/picks/",
    "nfl": "https://www.sportsline.com/nfl/picks/",
    "ncaab": "https://www.sportsline.com/college-basketball/picks/",
    "mlb": "https://www.sportsline.com/mlb/picks/",
}

favorites = {
    'nfl': ['GB', 'Green Bay Packers'],
    'ncaaf': ['WISC', 'Wisconsin Badgers Football', 'Wisconsin Badgers'],
    'ncaab': ['WISC', 'Wisconsin Badgers Mens Basketball', 'Wisconsin Badgers'],
    'mlb': ['MIL', 'Milwaukee Brewers', 'Brewers', 'Milwaukee'],
}

def scrape_sport_favorite(sport, url, favorite):
    cfg = {
        'debug': False,
        'odds_url': url,
        'team': favorite,
        'sport': sport,
        'endpoint': "https://api.openai.com/v1"
    }
    matchups = []
    
    SEATGEEK_KEY = os.environ.get('SEATGEEK_KEY', 'a224b635685150511dee50c5e3140c4c5195e96f58549ca8f446b3df3d3b8af9')
    SEATGEEK_UID = os.environ.get('SEATGEEK_UID', 'NDAzMjEzMHwxNzAzMDg2Njk2LjMyOTA5NjY')

    session = requests.Session()
    session.auth = (SEATGEEK_UID, SEATGEEK_KEY)

    # "datetime": datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
    performers_params = {
        "q": f"{favorite.lower().replace(' ', '-')}",
        "taxonomies.name": "sports",
    }
    performers_url = "https://api.seatgeek.com/2/performers"
    response = session.get(performers_url, params=performers_params)
    try:
        performers = response.json()
    except:
        import pdb ; pdb.set_trace()

    if not performers.get('performers'):
        return []

    def performer_filter(performer):
        return performer['name'].lower() == favorite.lower()

    def team_name_nickname(short_name, full_name):
        sport_nicknames = nicknames.get(sport, {})
        for team_name, _nicknames in sport_nicknames.items():
            if isinstance(_nicknames, str):
                team_nicknames = [_nicknames]
            elif isinstance(_nicknames, list):
                team_nicknames = _nicknames
            else:
                raise Exception(f"Unknown type for nicknames: {type(_nicknames)}")            

            for nickname in team_nicknames:
                w_abbrev = f"{team_name} {nickname}"
                if w_abbrev.lower() in full_name.lower() or w_abbrev.lower().replace('st.', 'state') in full_name.lower():
                    return w_abbrev
        return None
                
    
    for performer in performers['performers']:
        performer_id = performer['id']
        if not performer_filter(performer):
            continue
        events_params = {
            "performers[any].id": performer_id,
            "datetime_utc.gte": datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
            "datetime_utc.lte": (datetime.datetime.utcnow() + datetime.timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%S'),
        }        
        events_url = "https://api.seatgeek.com/2/events"
        response = session.get(events_url, params=events_params)
        assert response.status_code == 200
        for event in response.json().get('events', []):
            if event.get('time_tbd') or event.get('date_tbd'):
                continue
            arrow_time = arrow.get(event['datetime_utc'])
            home_team = None
            away_team = None
            performers = event['performers']
            for team in event['performers']:
                if team.get('home_team'):
                    home_team = team
                else:
                    team_name = team.get('name', "")
                    for city in nicknames.get(sport):
                        if city not in team_name and city.replace('St.', 'State') not in team_name:
                            continue
                        _teams = nicknames[sport][city]
                        if isinstance(_teams, str):
                            _teams = [_teams]
                        for _team in _teams:
                            if city in team_name or (f"{city.replace('St.', 'State')} {_team}") in team_name:
                                away_team = team
                                break
            if not away_team:
                print(f"Could not find away team for {event}")
                print(json.dumps(event['performers'], indent=2))
            if not home_team:
                print(f"Could not find home team for {event}")
                print(json.dumps(event['performers'], indent=2))
            if not home_team or not away_team:
                continue
            assert home_team is not None, f"Could not find home team for {event}"
            assert away_team is not None, f"Could not find away team for {event}"
            blob = {}
            blob['sport'] = sport
            blob['iso_8601_utc_date'] = arrow_time.isoformat()
            blob['point_spread'] = 0.0
            blob['point_spread_type'] = 'unknown'
            blob['ticket_price'] = event.get('stats', {}).get('lowest_price')
            blob['seatgeek_link'] = event.get('url')
            blob['home'] = team_name_nickname(home_team['short_name'], home_team['name'])
            blob['away'] = team_name_nickname(away_team['short_name'], away_team['name'])
            try:
                schedule_blob = massage(blob)
            except:
                continue
            matchups.append(schedule_blob)
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
        sport_matchups = scrape_sport_favorite(sport, url, favorite)
        if not sport_matchups and sport == 'ncaab':
            if sport == 'ncaab' and not matchups:
                all_ncaab_matchups = ncaab_odds(massage_function=massage)
                for matchup in all_ncaab_matchups:
                    print(f"Checking {favorite} in {matchup['away']} vs {matchup['home']}")
                    if favorite.lower() in [str(matchup['home'].lower().strip()), str(matchup['away'].lower().strip())]:
                        matchups.append(matchup)
        else:
            matchups += sport_matchups
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

    odds_str = get_odds_str(config)
    if 'metadata' in config:
        print(f"Queued: {odds_str} [{config['id']}] (API attempts: {config['metadata']['attempts']})")
    else:
        print(f"Queued: {odds_str} [{config['id']}]")
    if not config.get('output_filename'):
        return
        
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

def get_odds_str(cfg):
    return f"{cfg['away']} @ {cfg['home']} (${cfg['ticket_price']})"

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
