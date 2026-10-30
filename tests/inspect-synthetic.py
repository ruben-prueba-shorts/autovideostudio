"""Independent decoded-frame and audio checks for the synthetic load fixtures."""
import array
import io
import json
import math
from pathlib import Path
import subprocess
import sys
from PIL import Image


def command(args):
    return subprocess.run(['ffmpeg', '-v', 'error', '-threads', '2']+args, check=True, capture_output=True).stdout


results = json.loads(Path(sys.argv[1]).read_text())
checks = []
for result in results:
    movie, count, duration = result['master'], result['scenes'], result['duration']
    frame_indices = [math.floor((i+.5)*duration/count*result['fps']) for i in range(count)]
    select = '+'.join(f'eq(n\\,{i})' for i in frame_indices)
    pixels = command(['-i', movie, '-vf', f'select={select},crop=2:2:20:20,scale=1:1,format=rgb24', '-fps_mode', 'vfr', '-f', 'rawvideo', '-'])
    assert len(pixels) == count*3, (len(pixels), count)
    max_error = 0
    for i in range(count):
        expected = [(i*53)%180+40, (i*79)%180+40, (i*23)%180+40]
        error = max(abs(pixels[i*3+j]-expected[j]) for j in range(3))
        max_error = max(max_error, error)
        assert error < 15, (i, expected, list(pixels[i*3:i*3+3]))
    frame = Image.open(io.BytesIO(command(['-ss', '1', '-i', movie, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-threads', '1', '-'])))
    region = frame.crop((200, 550, 1080, 690)).convert('RGB')
    rgb = region.tobytes()
    white = sum(min(rgb[i:i+3])>235 for i in range(0,len(rgb),3))
    assert white > 100, 'Expected visible synthetic subtitle text'
    audio = []
    for position in [1, duration-1]:
        samples = array.array('h', command(['-ss', str(position), '-i', movie, '-t', '0.5', '-vn', '-ac', '1', '-ar', '24000', '-f', 's16le', '-']))
        rms = math.sqrt(sum(x*x for x in samples)/len(samples))/32768
        frequency = sum(1 for a,b in zip(samples,samples[1:]) if a<=0<b)/(len(samples)/24000)
        assert rms > .01 and abs(frequency-440)<8, (position, rms, frequency)
        audio.append({'position': position, 'rms': round(rms, 4), 'frequency': frequency})
    checks.append({'duration': duration, 'scenesCheckedInOrder': count, 'maxColorError': max_error,
                   'subtitleWhitePixels': white, 'audio': audio, 'passed': True})
    print(json.dumps(checks[-1]), flush=True)
Path(sys.argv[1]).with_name('decoded-checks.json').write_text(json.dumps(checks, indent=2))
