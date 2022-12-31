#!/usr/bin/env python
# This silly file just replaces sensitive values in docker-compose.yml - should really be jinja
import subprocess
import json
import urlparse

def main():
    config = json.load(open('tuner/config.json'))
    local_ip = urlparse.urlparse(config['local_address']).netloc.split(':')[0]
    code_dir = config['code_dir']
    base_dir = config['base_dir']
    cmd = ["sed",
           "-e", "s;DEFINEIP;{};g".format(local_ip),
           "-e", "s;CODEDIR;{};g".format(code_dir),
           "-e", "s;BASEDIR;{};g".format(base_dir),
           'docker-compose.yml.templ'
    ]
    subprocess.call(cmd)
    
if __name__ == '__main__':
    main()
