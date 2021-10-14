import requests as _requests
import time
    
def get(url):
    time.sleep(3)
    return _requests.get(url)
