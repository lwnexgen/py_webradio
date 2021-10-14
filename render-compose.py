#!/usr/bin/env python
# This silly file just replaces sensitive values in docker-compose.yml
import subprocess
import json
import urlparse

def main():
    config = json.load(open('tuner/config.json'))
    local_ip = urlparse.urlparse(config['local_address']).netloc.split(':')[0]
    cmd = ["sed", "-e", "s;DEFINEIP;{};g".format(local_ip), 'docker-compose.yml.templ']
    subprocess.call(cmd)
    
if __name__ == '__main__':
    main()
