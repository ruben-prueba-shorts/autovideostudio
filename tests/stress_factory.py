#!/usr/bin/env python3
"""Generate synthetic high-resolution assets, then benchmark the offline renderer."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import sys
import time
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import local_factory as f


def create(root, seconds, count):
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(260630)
    images = []
    for i in range(count):
        path = root/f'{i+1:04}.jpg'
        if not path.exists():
            # Unique image content; realistic decoded dimensions. No generation service.
            small = Image.frombytes('RGB', (480, 270), rng.randbytes(480*270*3))
            image = small.resize((1920, 1080), Image.Resampling.BILINEAR)
            draw = ImageDraw.Draw(image)
            color = ((i*53)%180+40, (i*79)%180+40, (i*23)%180+40)
            draw.rectangle((0, 0, 400, 150), fill=color)
            draw.text((20, 40), f'SYNTHETIC SCENE {i+1:04}', fill='white', font_size=42)
            image.save(path, quality=88)
        images.append({'path': path.name, 'sha256': f.digest(path)})
    audio = root/'tone.wav'
    if not audio.exists():
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000', '-t', str(seconds), str(audio)], check=True)
    manifest = {'format': 'video-factory-render/v1', 'id': f'load_{seconds:04}_{count:03}', 'channel': 'life-ranges-es',
                'material': 'synthetic', 'alignment': {'source': 'synthetic-known-times', 'reviewed': False},
                'audio': {'path': audio.name, 'sha256': f.digest(audio)},
                'scenes': [{'id': f's{i+1:04}', 'start': i*seconds/count, 'end': (i+1)*seconds/count,
                            'prompt': f'Known synthetic image {i+1}', 'narration': f'Synthetic scene {i+1}', 'image': images[i]} for i in range(count)],
                'cues': [{'start': i*seconds/count, 'end': (i+1)*seconds/count, 'text': f'Synthetic scene {i+1}'} for i in range(count)],
                'clips': [{'start': 0, 'end': min(30, seconds), 'title': 'Synthetic verification clip'}]}
    path = root/'render.ready.json'
    f.atomic_json(path, manifest)
    return path


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output'); p.add_argument('--stages', nargs='+', type=int, default=[30, 120, 300, 600, 1080])
    p.add_argument('--prepare-only', action='store_true')
    args = p.parse_args()
    base = Path(args.output).resolve()
    base.mkdir(parents=True, exist_ok=True)
    results = []
    for seconds in args.stages:
        count = 160 if seconds == 1080 else max(3, round(seconds/6.75))
        path = create(base/f'{seconds:04}', seconds, count)
        if args.prepare_only:
            print(str(path), flush=True)
            continue
        start = time.monotonic()
        result = f.render(path, base/'rendered', burn=True)
        # The existing independent auditor fully decodes output and checks recommended codecs.
        audit = subprocess.run(['node', str(Path(__file__).resolve().parents[1]/'tools/audit-mp4.cjs'), result['master'], str(seconds), 'horizontal'], capture_output=True, text=True)
        result['audit'] = json.loads(audit.stdout)
        result['passed'] = audit.returncode == 0
        result['totalValidationSeconds'] = round(time.monotonic()-start, 3)
        results.append(result)
        f.atomic_json(base/'results.json', results)
        print(json.dumps(result), flush=True)
        if not result['passed']:
            sys.exit(1)
