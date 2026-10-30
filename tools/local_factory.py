#!/usr/bin/env python3
"""Offline renderer and durable queue. Never calls a generation or upload service."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import uuid

VERSION = 1


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('xb') as f:
        f.write(encoded(value))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_format', '-show_streams',
                             '-of', 'json', str(path)], capture_output=True, check=True)
    return json.loads(result.stdout)


def local_asset(root, asset):
    if not isinstance(asset, dict) or not re.fullmatch(r'[a-f0-9]{64}', asset.get('sha256', '')):
        raise ValueError('Asset requires a SHA-256')
    relative = Path(asset['path'])
    if relative.is_absolute():
        raise ValueError('Asset paths must be relative to the bundle')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Asset missing or outside bundle')
    if digest(path) != asset['sha256']:
        raise ValueError('Asset hash mismatch: ' + asset['path'])
    return path


def validate(manifest, root):
    if manifest.get('format') != 'video-factory-render/v1':
        raise ValueError('Unsupported render manifest')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,79}', manifest.get('id', '')):
        raise ValueError('Invalid job ID')
    if manifest.get('channel') not in ['life-ranges-es', 'life-ranges-en', 'finance-es', 'finance-en']:
        raise ValueError('Choose one of the four channels')
    if manifest.get('material') not in ['real', 'synthetic']:
        raise ValueError('Identify real or synthetic material')
    alignment = manifest.get('alignment', {})
    if manifest['material'] == 'real' and (alignment.get('source') not in ['local-asr', 'manual'] or not alignment.get('reviewed')):
        raise ValueError('Real material requires reviewed alignment; estimated timings cannot be rendered as verified')
    scenes = manifest.get('scenes', [])
    if not 1 <= len(scenes) <= 300:
        raise ValueError('Expected 1–300 scenes')
    last = 0
    ids = set()
    for i, scene in enumerate(scenes):
        if scene.get('id') in ids or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', scene.get('id', '')):
            raise ValueError('Scene IDs must be unique')
        ids.add(scene['id'])
        start, end = scene['start'], scene['end']
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in [start, end]) or abs(start-last) > .001 or end <= start:
            raise ValueError('Scenes must be ordered and contiguous')
        if not scene.get('prompt') or not scene.get('narration'):
            raise ValueError('Each scene needs its prompt and narration')
        image = local_asset(root, scene['image'])
        if image.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
            raise ValueError('Use a static PNG/JPEG/WebP image')
        last = end
    audio = local_asset(root, manifest['audio'])
    if audio.suffix.lower() not in ['.wav', '.mp3', '.m4a', '.flac', '.ogg']:
        raise ValueError('Unsupported narration file extension')
    info = probe(audio)
    if len([s for s in info['streams'] if s['codec_type'] == 'audio']) != 1:
        raise ValueError('Exactly one narration track is required')
    if abs(float(info['format']['duration'])-last) > .15:
        raise ValueError('Narration duration differs from scene timeline')
    cues = manifest.get('cues', [])
    previous = 0
    for cue in cues:
        start, end = cue['start'], cue['end']
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in [start, end]) or start < previous or end <= start or end > last+.001:
            raise ValueError('Subtitle times must be ordered and inside the narration')
        if not isinstance(cue.get('text'), str) or not cue['text'].strip() or len(cue['text']) > 1000:
            raise ValueError('Invalid caption text')
        previous = end
    if not cues:
        raise ValueError('Timed captions are required (no invented speech timings)')
    clips = manifest.get('clips', [])
    if len(clips) > 250:
        raise ValueError('Too many clips')
    for clip in clips:
        if not 0 <= clip['start'] < clip['end'] <= last or clip['end']-clip['start'] > 150 or not isinstance(clip.get('title'), str) or len(clip['title']) > 140:
            raise ValueError('Invalid clip range')
    return last


def execute(args, cwd, heartbeat, stats, timeout=600):
    log = Path(cwd) / 'ffmpeg.log'
    offset = log.stat().st_size if log.exists() else 0
    with log.open('ab') as errors:
        proc = subprocess.Popen(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=errors)
        started = time.monotonic()
        try:
            while proc.poll() is None:
                heartbeat()
                if time.monotonic()-started > timeout:
                    raise TimeoutError('FFmpeg deadline exceeded')
                time.sleep(.1)
            if proc.returncode:
                raise RuntimeError('FFmpeg failed; see ' + str(log))
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
    # FFmpeg reports its own getrusage peak. PIDs exposed by a remote execution
    # harness need not map to the /proc namespace visible to Python.
    with log.open('rb') as f:
        f.seek(offset)
        memory = re.findall(rb'bench: maxrss=(\d+)kB', f.read())
    if memory:
        stats['peakFfmpegRssBytes'] = max(stats['peakFfmpegRssBytes'], max(int(x)*1024 for x in memory))


def ass_time(seconds):
    t = max(0, round(seconds*100))
    return f'{t//360000}:{t//6000%60:02}:{t//100%60:02}.{t%100:02}'


def ass_text(text):
    # ASS override tags are never accepted from scripts.
    return text.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\r', '').replace('\n', r'\N')


def captions(path, cues, start, end, w, h):
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{round(h*.045)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,40,40,{round(h*.08)},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    for cue in cues:
        a, b = max(cue['start'], start), min(cue['end'], end)
        if b > a:
            header += f"Dialogue: 0,{ass_time(a-start)},{ass_time(b-start)},Default,,0,0,0,,{ass_text(cue['text'])}\n"
    Path(path).write_text(header, encoding='utf8')


def render(manifest_path, output_root, heartbeat=lambda: None, height=720, fps=30, burn=False, stop_after=0):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    duration = validate(manifest, manifest_path.parent)
    render_config = {'manifest': manifest, 'height': height, 'fps': fps, 'burn': burn, 'version': VERSION}
    key = hashlib.sha256(encoded(render_config)).hexdigest()
    work = Path(output_root).resolve() / manifest['id'] / key[:16]
    work.mkdir(parents=True, exist_ok=True)
    checkpoint_file = work / 'checkpoint.json'
    checkpoint = json.loads(checkpoint_file.read_text()) if checkpoint_file.exists() else {'key': key, 'segments': {}}
    if checkpoint.get('key') != key:
        raise ValueError('Checkpoint identity mismatch')
    started = time.monotonic()
    stats = {'material': manifest['material'], 'scenes': len(manifest['scenes']), 'duration': duration,
             'peakFfmpegRssBytes': 0, 'memorySource': 'ffmpeg -benchmark (per-process maximum RSS)',
             'reusedSegments': 0, 'renderedSegments': 0, 'fps': fps, 'height': height}
    w, h = height*16//9, height
    common = ['ffmpeg', '-v', 'info', '-nostats', '-benchmark', '-y', '-threads', '2', '-filter_threads', '1', '-protocol_whitelist', 'file,pipe']
    segments = []
    for i, scene in enumerate(manifest['scenes']):
        heartbeat()
        scene_dir = work / f'{i+1:04}'
        scene_dir.mkdir(exist_ok=True)
        part = scene_dir / 'segment.mp4'
        cache = checkpoint['segments'].get(scene['id'])
        if cache and part.exists() and digest(part) == cache['sha256']:
            stats['reusedSegments'] += 1
        else:
            first, last = round(scene['start']*fps), round(scene['end']*fps)
            if last <= first:
                raise ValueError('Scene shorter than one video frame')
            image = local_asset(manifest_path.parent, scene['image'])
            vf = f'scale={w}:{h}:force_original_aspect_ratio=decrease:out_range=tv,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p'
            if burn:
                captions(scene_dir / 'captions.ass', manifest['cues'], first/fps, last/fps, w, h)
                vf += ',ass=captions.ass'
            temp = scene_dir / 'segment.partial.mp4'
            execute(common + ['-loop', '1', '-framerate', str(fps), '-i', str(image), '-vf', vf,
                              '-frames:v', str(last-first), '-an', '-c:v', 'libx264', '-preset', 'veryfast',
                              '-crf', '18', '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-threads', '2', str(temp)],
                    scene_dir, heartbeat, stats)
            segment_info = probe(temp)
            if abs(float(segment_info['format']['duration'])-(last-first)/fps) > 1/fps+.001:
                raise ValueError('Segment duration mismatch')
            os.replace(temp, part)
            checkpoint['segments'][scene['id']] = {'sha256': digest(part), 'frames': last-first}
            atomic_json(checkpoint_file, checkpoint)
            stats['renderedSegments'] += 1
            if stop_after and stats['renderedSegments'] >= stop_after:
                raise RuntimeError('Controlled interruption after checkpoint (test only)')
        segments.append(part)
    # Concat list contains only renderer-created relative names, never external text.
    (work / 'segments.txt').write_text(''.join(f"file '{i+1:04}/segment.mp4'\n" for i in range(len(segments))))
    audio = local_asset(manifest_path.parent, manifest['audio'])
    temp, final = work / 'master.partial.mp4', work / 'master.mp4'
    execute(common + ['-f', 'concat', '-safe', '1', '-i', 'segments.txt', '-protocol_whitelist', 'file,pipe', '-i', str(audio),
                      '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                      '-ar', '48000', '-t', str(round(duration*fps)/fps), '-movflags', '+faststart', str(temp)],
            work, heartbeat, stats)
    info = probe(temp)
    actual_duration = float(info['format']['duration'])
    if abs(actual_duration-duration) > .15:
        raise ValueError('Final duration mismatch')
    execute(common + ['-xerror', '-i', str(temp), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'],
            work, heartbeat, stats)
    os.replace(temp, final)
    captions(work / 'captions.ass', manifest['cues'], 0, duration, w, h)
    handoff = {'format': 'autovideo-clipfarming/v1', 'jobId': manifest['id'],
               'language': manifest['channel'].rsplit('-', 1)[1], 'subtitlesBurned': burn,
               'video': {'name': final.name, 'size': final.stat().st_size, 'sha256': digest(final), 'duration': actual_duration},
               'cues': manifest['cues'], 'clips': manifest.get('clips', [])}
    atomic_json(work / 'master.clipfarming.json', handoff)
    stats.update(elapsedSeconds=round(time.monotonic()-started, 3), outputBytes=final.stat().st_size,
                 actualDuration=actual_duration, master=str(final), completed=True)
    atomic_json(work / 'result.json', stats)
    return stats


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, manifest TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, lease REAL, owner TEXT, error TEXT, result TEXT)')
    return db


def enqueue(db_path, manifest_path):
    path = Path(manifest_path).resolve()
    manifest = json.loads(path.read_text())
    validate(manifest, path.parent)
    fingerprint = hashlib.sha256(encoded(manifest)).hexdigest()
    with connect(db_path) as db:
        existing = db.execute('SELECT * FROM jobs WHERE id=?', (manifest['id'],)).fetchone()
        if existing:
            if existing['fingerprint'] != fingerprint or existing['manifest'] != str(path):
                raise ValueError('Job ID already belongs to different content or bundle')
            return {'id': existing['id'], 'state': existing['state'], 'existing': True}
        db.execute('INSERT INTO jobs (id,fingerprint,manifest,state) VALUES (?,?,?,?)', (manifest['id'], fingerprint, str(path), 'queued'))
    return {'id': manifest['id'], 'state': 'queued', 'existing': False}


def work_once(db_path, output, height=720, fps=30, burn=False, stop_after=0):
    owner = uuid.uuid4().hex
    with connect(db_path) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("UPDATE jobs SET state='failed',error='Worker lease expired; explicit retry required',owner=NULL WHERE state='running' AND lease<?", (time.time(),))
        job = db.execute("SELECT * FROM jobs WHERE state='queued' AND attempts<3 ORDER BY rowid LIMIT 1").fetchone()
        if not job:
            return None
        db.execute("UPDATE jobs SET state='running',owner=?,attempts=attempts+1,lease=?,error=NULL WHERE id=?", (owner, time.time()+120, job['id']))
    last_heartbeat = [0.]

    def heartbeat():
        now = time.time()
        if now-last_heartbeat[0] < 10:
            return
        with connect(db_path) as db:
            cursor = db.execute("UPDATE jobs SET lease=? WHERE id=? AND state='running' AND owner=?", (now+120, job['id'], owner))
            if cursor.rowcount != 1:
                raise RuntimeError('Worker lost its lease')
        last_heartbeat[0] = now

    try:
        manifest = json.loads(Path(job['manifest']).read_text())
        if hashlib.sha256(encoded(manifest)).hexdigest() != job['fingerprint']:
            raise ValueError('Queued manifest was modified')
        result = render(job['manifest'], output, heartbeat, height, fps, burn, stop_after)
        with connect(db_path) as db:
            db.execute("UPDATE jobs SET state='review',result=?,lease=NULL WHERE id=? AND owner=?", (json.dumps(result), job['id'], owner))
        return result
    except BaseException as error:
        with connect(db_path) as db:
            db.execute("UPDATE jobs SET state='failed',error=?,lease=NULL WHERE id=? AND owner=?", (str(error)[:1000], job['id'], owner))
        raise


def scan(db_path, inbox):
    """Only explicitly ready bundles in an application-owned inbox are considered."""
    results = []
    for path in sorted(Path(inbox).glob('*/render.ready.json')):
        try:
            results.append({'manifest': str(path), **enqueue(db_path, path)})
        except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
            results.append({'manifest': str(path), 'state': 'rejected', 'error': str(error)})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('enqueue'); p.add_argument('database'); p.add_argument('manifest')
    p = sub.add_parser('list'); p.add_argument('database')
    p = sub.add_parser('retry'); p.add_argument('database'); p.add_argument('id')
    p = sub.add_parser('scan'); p.add_argument('database'); p.add_argument('inbox')
    p = sub.add_parser('select'); p.add_argument('database'); p.add_argument('catalog'); p.add_argument('choice')
    p = sub.add_parser('work'); p.add_argument('database'); p.add_argument('output')
    p.add_argument('--height', type=int, choices=[720, 1080], default=720)
    p.add_argument('--fps', type=int, choices=[30, 60], default=30)
    p.add_argument('--burn-subtitles', action='store_true')
    p.add_argument('--stop-after', type=int, default=0, help=argparse.SUPPRESS)
    p = sub.add_parser('render'); p.add_argument('manifest'); p.add_argument('output')
    p.add_argument('--height', type=int, choices=[720, 1080], default=720)
    p.add_argument('--fps', type=int, choices=[30, 60], default=30)
    p.add_argument('--burn-subtitles', action='store_true')
    args = parser.parse_args()
    if args.command == 'enqueue':
        result = enqueue(args.database, args.manifest)
    elif args.command == 'work':
        result = work_once(args.database, args.output, args.height, args.fps, args.burn_subtitles, args.stop_after)
    elif args.command == 'render':
        result = render(args.manifest, args.output, height=args.height, fps=args.fps, burn=args.burn_subtitles)
    elif args.command == 'list':
        with connect(args.database) as db:
            result = [dict(r) for r in db.execute('SELECT id,state,attempts,error FROM jobs ORDER BY rowid')]
    elif args.command == 'scan':
        result = scan(args.database, args.inbox)
    elif args.command == 'select':
        catalog = Path(args.catalog).resolve()
        choice = json.loads(catalog.read_text())[args.choice]
        manifest = (catalog.parent / choice['manifest']).resolve()
        if not manifest.is_relative_to(catalog.parent):
            raise ValueError('Catalog entry must remain inside the project directory')
        result = enqueue(args.database, manifest)
    else:
        with connect(args.database) as db:
            cursor = db.execute("UPDATE jobs SET state='queued',owner=NULL WHERE id=? AND state='failed' AND attempts<3", (args.id,))
            if cursor.rowcount != 1:
                raise ValueError('Retry requires a failed job with fewer than 3 attempts')
            result = {'id': args.id, 'state': 'queued'}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
