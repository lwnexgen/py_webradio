import datetime
import os
import json
import time

from sport import Sport
from utils import get

schedule_pattern = "https://api.sportradar.us/ncaamb/{access_level}/{version}/{language_code}/games/{season_year}/{ncaamb_season}/schedule.{format}?api_key={your_api_key}"

def schedule(apikey, date):
    now = datetime.datetime.now()
    today = '{}-{}-{}'.format(
        now.year,
        now.month,
        now.day
    )
    seasonyear = now.year
    if now.month < 5:
        seasonyear -= 1
    cachefile = 'data/{}-ncaab'.format(today)
    if os.path.exists(cachefile):
        return json.load(open(cachefile))
    games = []
    for stage in ['CT', 'REG', 'PST']:
        url = schedule_pattern.format(
            your_api_key=apikey,
            access_level='trial',
            version='v4',
            language_code='en',
            season_year=seasonyear,
            ncaamb_season=stage,
            format='json'
        )
        resp = get(url)
        if resp.status_code != 200:
            print resp
            time.sleep(3)
            continue
        ncaabsched = json.loads(resp.text)
        games += [x for x in ncaabsched.get('games', []) if x['status'] == 'scheduled']
    if not games:
        return []    
    with open(cachefile, 'w') as cfp:
        cfp.write(json.dumps(games))
        cfp.flush()
    return games

class SportNCAAB(Sport):
    def __init__(self):
        pass
