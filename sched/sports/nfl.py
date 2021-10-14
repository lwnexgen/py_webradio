import datetime
import json
import os
import time

from sport import Sport
from utils import get

schedule_pattern = "https://api.sportradar.us/nfl-{access_level}{version}/games/{year}/{nfl_season}/schedule.{format}?api_key={your_api_key}"

def schedule(apikey, date):
    date = datetime.datetime.now()
    today = '{}-{}-{}'.format(
        date.year,
        date.month,
        date.day
    )
    cachefile = 'data/{}-nfl'.format(today)
    if os.path.exists(cachefile):
        return json.load(open(cachefile))
    nflseason = date.year
    if date.month < 7:
        nflseason -= 1
    games = []
    for stage in ['PRE', 'REG', 'PST']:
        url = schedule_pattern.format(
            your_api_key=apikey,
            access_level='ot',
            version=2,
            year=nflseason,
            nfl_season=stage,
            format='json'
        )
        resp = get(url)
        if resp.status_code != 200:
            print resp
            time.sleep(3)
            continue
        sched = json.loads(resp.text)
        for week in sched['weeks']:
            for game in week['games']:
                if game.get('status') == 'scheduled':
                    games.append(game)
    if not games:
        return []
    with open(cachefile, 'w') as cfp:
        cfp.write(json.dumps(games))
        cfp.flush()
    return games

class SportNFL(Sport):
    def __init__(self):
        pass
