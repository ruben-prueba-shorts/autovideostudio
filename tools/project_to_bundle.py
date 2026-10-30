#!/usr/bin/env python3
"""Extract a saved AutoVideo project into a new, offline render bundle."""
import argparse
import base64
import json
from pathlib import Path
import re

import local_factory as factory


def decode_data(value, allowed, limit):
    match = re.fullmatch(r'data:([^;,]+);base64,([A-Za-z0-9+/=\s]+)', value or '')
    if not match or match[1] not in allowed or len(match[2]) > limit*4//3+8:
        raise ValueError('Unsupported or oversized embedded asset')
    data = base64.b64decode(match[2], validate=True)
    if len(data) > limit:
        raise ValueError('Embedded asset exceeds limit')
    return match[1], data


def convert(project_path, target, channel, material='real', reviewed=False):
    project_path, target = Path(project_path), Path(target)
    if project_path.stat().st_size > 600*1024*1024:
        raise ValueError('Project exceeds 600 MiB')
    data = json.loads(project_path.read_text())
    if data.get('type') != 'FacelessStudioProject' or data.get('version') != 1 or not data.get('voice'):
        raise ValueError('An AutoVideo project with embedded narration is required')
    scenes = data.get('scenes', [])
    if material == 'real' and (not reviewed or not data.get('verified') or any(s.get('timingSource') != 'recognized' for s in scenes)):
        raise ValueError('Real output requires recognized timings and explicit human review; project metadata alone is not acoustic proof')
    job = data.get('factoryJob')
    if not job or len(job.get('scenes', [])) != len(scenes):
        raise ValueError('Saved production job and scene count must match')
    if channel != job['niche']+'-'+job['language']:
        raise ValueError('Channel differs from the production job')
    manifest = {'format': 'video-factory-render/v1', 'id': job['id'], 'channel': channel, 'material': material,
                'alignment': {'source': 'local-asr' if material == 'real' else 'synthetic-known-times', 'reviewed': reviewed},
                'scenes': [], 'cues': [], 'clips': []}
    decoded = []
    extensions = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}
    for i, scene in enumerate(scenes):
        raw = data['images'][scene['imgIndex']]
        original = job['scenes'][i]
        if scene['text'] != original['narration'] or raw.get('prompt') != original['imagePrompt'] or raw.get('sceneIndex') != i:
            raise ValueError('Scene, image and prompt association changed')
        mime, image = decode_data(raw['url'], extensions, 30*1024*1024)
        name = f'{i+1:04}{extensions[mime]}'
        decoded.append((name, image))
        manifest['scenes'].append({'id': f's{i+1:04}', 'start': scene['start'], 'end': scene['end'],
                                   'prompt': original['imagePrompt'], 'narration': scene['text'],
                                   'image': {'path': name, 'sha256': factory.hashlib.sha256(image).hexdigest()},
                                   'sourcePromptId': raw.get('sourcePromptId'), 'originalName': raw['name']})
        words, timings = scene['text'].split(), scene.get('wordTimings', [])
        if len(words) != len(timings):
            raise ValueError('Missing word timings; synchronization must finish first')
        # Same 2–3 word grouping and 0.1 s tail as AutoVideo getSubtitleCues.
        k = 0
        shift = float(data.get('settings', {}).get('subShiftInput', 0) or 0)
        while k < len(words):
            end = k
            while end+1 < len(words) and end-k < 2 and timings[end+1]['start']-timings[end]['end'] < .45:
                end += 1
            a = max(scene['start'], timings[k]['start'])
            next_start = timings[end+1]['start'] if end+1 < len(words) else scene['end']
            b = min(scene['end'], timings[end]['end']+.1, next_start)
            b = max(b, min(a+.3, next_start, scene['end']))
            a, b = max(0, a-shift), min(float(data['duration']), b-shift)
            if b > a:
                manifest['cues'].append({'start': a, 'end': b, 'text': ' '.join(words[k:end+1])})
            k = end+1
    mime, audio = decode_data(data['voice']['data'], ['audio/wav', 'audio/x-wav', 'audio/mpeg', 'audio/mp3', 'audio/mp4', 'application/octet-stream'], 512*1024*1024)
    ext = '.mp3' if mime in ['audio/mpeg', 'audio/mp3'] else '.m4a' if mime == 'audio/mp4' else '.wav'
    decoded.append(('narration'+ext, audio))
    manifest['audio'] = {'path': 'narration'+ext, 'sha256': factory.hashlib.sha256(audio).hexdigest()}
    for i, clip in enumerate(data.get('clips', [])):
        if 0 < clip['end']-clip['start'] <= 150:
            manifest['clips'].append({'start': clip['start'], 'end': clip['end'], 'title': f'Clip {i+1}'})
    # New directories only: never overwrite original projects or user assets.
    target.mkdir(parents=True, exist_ok=False)
    for name, content in decoded:
        (target/name).write_bytes(content)
    factory.validate(manifest, target)
    factory.atomic_json(target/'render.ready.json', manifest)
    return target/'render.ready.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project'); parser.add_argument('output')
    parser.add_argument('--channel', required=True, choices=['life-ranges-es', 'life-ranges-en', 'finance-es', 'finance-en'])
    parser.add_argument('--material', choices=['real', 'synthetic'], default='real')
    parser.add_argument('--reviewed-alignment', action='store_true')
    args = parser.parse_args()
    print(convert(args.project, args.output, args.channel, args.material, args.reviewed_alignment))
