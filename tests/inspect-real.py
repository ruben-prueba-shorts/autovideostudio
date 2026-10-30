#!/usr/bin/env python3
"""Independent inspection of the three-scene real smoke test, no generation.

Requires FFmpeg, numpy/scipy, Pillow and Tesseract. OCR and signal
correlation are evidence, not a substitute for subjective listening approval.
"""
import array
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
import wave

import numpy as np
from PIL import Image, ImageDraw
from scipy.signal import correlate
from scipy.ndimage import label


def command(args):
    return subprocess.check_output(args, stderr=subprocess.DEVNULL)


def frame(video, time):
    return Image.open(BytesIO(command(['ffmpeg', '-v', 'error', '-ss', str(time), '-i', str(video), '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-']))).convert('RGB')


def normalized(text):
    return re.sub(r'[^a-z0-9 ]', '', ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c)))


def audio(video):
    return np.frombuffer(command(['ffmpeg', '-v', 'error', '-i', str(video), '-map', '0:a:0', '-ac', '1', '-ar', '24000', '-f', 'f32le', '-']), dtype='<f4')


def compare_audio(reference, actual, stream_start):
    # Match independent four-second windows near beginning, middle and end.
    # A positive offset means the rendered sound is later than the source.
    result = []
    for start in [0.2, 10.2, 21.2]:
        a = int(start*24000)
        clip = reference[a:a+4*24000]
        lower, upper = max(0, a-12000), min(len(actual), a+len(clip)+12000)
        candidate = actual[lower:upper]
        if len(candidate) < len(clip):
            raise ValueError('Rendered audio does not cover the final test window')
        c = correlate(candidate, clip, mode='valid', method='fft')
        offset = int(np.argmax(c))
        matched = candidate[offset:offset+len(clip)]
        similarity = float(np.corrcoef(clip, matched)[0, 1])
        lag = (lower+offset-a)/24000+stream_start
        result.append({'sourceStart': start, 'duration': 4, 'lagSeconds': lag, 'streamStartSeconds': stream_start, 'correlation': similarity})
    return result


def inspect(folder):
    plan = json.loads((folder/'alignment-result.json').read_text())
    with wave.open(str(folder/'mako-gemini-3.8.wav'), 'rb') as source:
        samples = array.array('h', source.readframes(source.getnframes()))
        reference = np.asarray(samples, dtype=np.float32)/32768
    originals = [Image.open(folder/f'prompt-{n}-original.jpg').convert('RGB') for n in [102, 110, 97]]
    def comparison(im):
        small = np.asarray(im.resize((160, 90)), dtype=np.float32)
        return small[:66]  # exclude subtitle area
    targets = [comparison(im) for im in originals]
    result = {'material': 'real', 'humanListeningApproved': False, 'videos': {}}
    contacts = Image.new('RGB', (960, 3*290), '#111111')
    draw = ImageDraw.Draw(contacts)
    for name, vertical in [('video-real-horizontal.mp4', False), ('short-real-vertical.mp4', True)]:
        video = folder/name
        probe = json.loads(command(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(video)]))
        stream_start = float(next(s for s in probe['streams'] if s['codec_type']=='audio').get('start_time', 0))
        detail = {'duration': float(probe['format']['duration']), 'audio': compare_audio(reference, audio(video), stream_start), 'imageChecks': [], 'subtitleSamples': []}
        for i, scene in enumerate(plan['scenes']):
            t = scene['start']+1.7
            picture = frame(video, t)
            # ClipFarming contain mode keeps the whole landscape frame centered.
            source_area = picture
            if vertical:
                height = round(picture.width*720/1280)
                top = (picture.height-height)//2
                source_area = picture.crop((0, top, picture.width, top+height))
            sample = comparison(source_area)
            distances = [float(np.mean((sample-target)**2)) for target in targets]
            selected = int(np.argmin(distances))
            detail['imageChecks'].append({'scene': i+1, 'time': t, 'expectedPromptId': str([102, 110, 97][i]), 'matchingImageIndex': selected, 'mse': distances, 'passed': selected==i})
            thumb = picture.copy();thumb.thumbnail((620 if not vertical else 270, 255))
            contacts.paste(thumb, ((0 if not vertical else 670), i*290+24))
            draw.text((0 if not vertical else 670, i*290+5), f'{name}: scene {i+1} at {t:.2f}s', fill='white')
        for i, cue in enumerate(plan['cues']):
            t = (cue['start']+cue['end'])/2
            im = frame(video, t)
            if vertical:
                roi = im.crop((round(im.width*.12), round(im.height*.75), round(im.width*.88), round(im.height*.89)))
            else:
                # AutoVideo's white caption outline overlaps detailed artwork.
                # Restrict to its line, remove white source-image components that
                # touch the crop boundary, and invert the remaining white glyphs.
                width = min(im.width*.9, max(170, len(cue['text'])*23))
                roi = im.crop((round((im.width-width)/2), round(im.height*.78), round((im.width+width)/2), round(im.height*.86)))
                pixels = np.asarray(roi)
                mask = (pixels.min(2)>210)&((pixels.max(2).astype(int)-pixels.min(2))<30)
                labels, count = label(mask)
                for component in range(1, count+1):
                    ys, xs = np.where(labels==component)
                    if len(ys)<4 or ys.min()==0 or ys.max()==mask.shape[0]-1 or xs.min()==0 or xs.max()==mask.shape[1]-1:
                        mask[labels==component] = False
                roi = Image.fromarray(np.uint8(~mask)*255)
            target = folder/f'ocr-{name}-{i:02}.png'
            roi.resize((roi.width*2, roi.height*2)).save(target)
            text = command(['tesseract', str(target), 'stdout', '--psm', '7']).decode().strip()
            target.unlink()
            detail['subtitleSamples'].append({'cue': i+1, 'time': t, 'expected': cue['text'], 'ocr': text, 'exactNormalizedMatch': normalized(text)==normalized(cue['text'])})
        detail['passedImageOrder'] = all(c['passed'] for c in detail['imageChecks'])
        detail['passedAudioPreservation'] = all(a['correlation']>.98 and abs(a['lagSeconds'])<.15 for a in detail['audio'])
        detail['subtitleExactOcrMatches'] = sum(c['exactNormalizedMatch'] for c in detail['subtitleSamples'])
        result['videos'][name] = detail
    contacts.save(folder/'real-contact-sheet.jpg', quality=92)
    (folder/'independent-inspection.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(v['passedImageOrder'] and v['passedAudioPreservation'] for v in result['videos'].values()):
        raise ValueError('Image order or audio preservation failed; do not approve output')


if __name__ == '__main__':
    inspect(Path(sys.argv[1]))
