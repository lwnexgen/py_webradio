#!/usr/bin/env python
import subprocess
import tempfile
import os
import fnmatch
import natsort

import speech_recognition as sr

from random import randint

def _randlist():
    for root, _, files in os.walk('/var/www/html/webtune_live/'):
        all_mp3s = natsort.natsorted(fnmatch.filter(files, "*.mp3"))
        left = randint(0, len(all_mp3s))
        right = min(left + 15, len(all_mp3s))
        mp3s = [os.path.join(root, x) for x in all_mp3s[left:right]]
        break
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write("\n".join(["file '{}'".format(x) for x in mp3s]))
        tmp.flush()
    return tmp.name

def convert():
    input_file = _randlist()
    output_file = input_file + '.wav'
    command = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', input_file, output_file]
    try:
        with open('/dev/null', 'w') as nope:
            subprocess.call(command, stdout=nope, stderr=nope)
    except:
        import traceback ; traceback.print_exc()
    finally:
        os.remove(input_file)
    return output_file

def translate():
    r = sr.Recognizer()
    recording = convert()
    af = sr.AudioFile(recording)
    with af as source:
        r.adjust_for_ambient_noise(source)
        audio = r.record(source)
        print(r.recognize_wit(audio, 'PNUS65AKF224OOGGLP2Y7KH2F2VQCQZQ'))
    os.remove(recording)

if __name__ == '__main__':
    translate()
