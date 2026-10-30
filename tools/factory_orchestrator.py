#!/usr/bin/env python3
"""Local zero-service-cost orchestrator. No generation/login/upload client.

ChatGPT supplies versioned reports and scripts through files. Missing content
blocks the job, never triggers a paid fallback. Existing renderer/queue reused.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit, parse_qs
import uuid
import local_factory as render

REPO = Path(__file__).resolve().parents[1]
CHANNELS = ('life-ranges-es', 'life-ranges-en', 'finance-es', 'finance-en')
STAGES = ('brief', 'script', 'media', 'assembly', 'shorts', 'package')
POLICY = {'economicBudgetEUR': 0, 'generationQuotaAuthorized': 0, 'networkGenerationEnabled': False,
          'paidApiEnabled': False, 'uploadEnabled': False, 'publishEnabled': False}


class Blocked(Exception):
    pass


def read(path, limit=30*1024*1024):
    path = Path(path)
    if path.stat().st_size > limit:
        raise ValueError('JSON exceeds input limit')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def fingerprint(value):
    return hashlib.sha256(render.encoded(value)).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,79}', value):
        raise ValueError('Invalid stable identifier')
    return value


def iso(value):
    if not isinstance(value, str) or datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('Evidence needs a timestamp with timezone')
    return value


def contract(command, value=None, **kwargs):
    p = subprocess.run(['node', str(REPO/'tools/factory_contract.cjs')], input=render.encoded({'command': command, 'value': value, **kwargs}),
                       capture_output=True, timeout=60)
    if p.returncode:
        raise ValueError(p.stderr.decode(errors='replace')[:1500])
    return json.loads(p.stdout)


def report_contract(data):
    if data.get('format') != 'video-factory-ideas/v1' or data.get('material') not in ('research', 'synthetic'):
        raise ValueError('Identify a research report or synthetic test explicitly')
    identifier(data.get('id')); iso(data.get('observedAt')); items = data.get('ideas', [])
    if len(items) != 10 or [i.get('number') for i in items] != list(range(1, 11)) or any(type(i.get('number')) is not int for i in items):
        raise ValueError('Exactly ten numbered ideas in stable order are required')
    for idea in items:
        if idea.get('channel') not in CHANNELS or not isinstance(idea.get('title'), str) or not 1 <= len(idea['title']) <= 180:
            raise ValueError('An idea needs a supported channel and title')
        if not idea.get('originalAngle') or not idea.get('potentialReason'):
            raise ValueError('Record an original angle and distinguish potential from facts')
        if not isinstance(idea.get('sources'), list) or not idea['sources']:
            raise ValueError('References required; unknown metrics stay null')
        for source in idea['sources']:
            u = urlsplit(source.get('url', ''))
            if u.scheme != 'https' or u.username or u.password or u.hostname not in ('www.youtube.com', 'youtube.com', 'youtu.be'):
                raise ValueError('Reference must be an HTTPS YouTube video URL')
            vid = u.path.strip('/') if u.hostname == 'youtu.be' else parse_qs(u.query).get('v', [''])[0]
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
                raise ValueError('Reference needs a video ID, not a search URL')
            if data['material'] == 'research' and not source.get('verification'):
                raise ValueError('Record how a reference was actually checked')
            iso(source.get('observedAt'))
            for name, value in source.get('metrics', {}).items():
                if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0):
                    raise ValueError('Invalid metric: '+name)
    return data


def connect(root):
    root = Path(root).resolve(); marker = read(root/'.factory-owned.json')
    if marker.get('format') != 'video-factory-workspace/v1' or marker.get('policy') != POLICY:
        raise ValueError('Dedicated factory folder with zero-cost policy required')
    db = render.connect(root/'factory.sqlite')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS idea_reports(id TEXT PRIMARY KEY, sha TEXT NOT NULL, content TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS productions(id TEXT PRIMARY KEY, report_id TEXT NOT NULL, choice INTEGER NOT NULL,
        channel TEXT NOT NULL, spec TEXT NOT NULL, state TEXT NOT NULL, owner TEXT, lease REAL,
        failures INTEGER NOT NULL DEFAULT 0, error TEXT, result TEXT, script TEXT, media TEXT);
      CREATE TABLE IF NOT EXISTS production_stages(job_id TEXT, name TEXT, receipt TEXT NOT NULL, PRIMARY KEY(job_id,name));
      CREATE TABLE IF NOT EXISTS factory_events(seq INTEGER PRIMARY KEY, job_id TEXT, event TEXT, at REAL, detail TEXT);
      CREATE TABLE IF NOT EXISTS channel_references(channel TEXT PRIMARY KEY, content TEXT NOT NULL);
    ''')
    return db


def init(root):
    root = Path(root).resolve()
    if root.exists() and any(root.iterdir()) and not (root/'.factory-owned.json').is_file():
        raise ValueError('Choose a new/empty dedicated folder; personal contents are never replaced')
    root.mkdir(parents=True, exist_ok=True)
    if not (root/'.factory-owned.json').exists():
        render.atomic_json(root/'.factory-owned.json', {'format': 'video-factory-workspace/v1', 'policy': POLICY})
    with connect(root):
        pass
    return {'workspace': str(root), 'policy': POLICY}


def owned(root, *parts):
    root = Path(root).resolve(); path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes the dedicated workspace')
    return path


def event(db, job, name, detail=None):
    db.execute('INSERT INTO factory_events(job_id,event,at,detail) VALUES(?,?,?,?)', (job, name, time.time(), json.dumps(detail, ensure_ascii=False)))


def import_report(root, path):
    report = report_contract(read(path)); sha = fingerprint(report)
    with connect(root) as db:
        prior = db.execute('SELECT sha FROM idea_reports WHERE id=?', (report['id'],)).fetchone()
        if prior and prior['sha'] != sha:
            raise ValueError('Report IDs are immutable; use a new version')
        db.execute('INSERT OR IGNORE INTO idea_reports VALUES(?,?,?)', (report['id'], sha, json.dumps(report, ensure_ascii=False)))
    return {'report': report['id'], 'ideas': 10, 'existing': bool(prior)}


def select(root, report_id, command, seconds=1080, scene_count=160):
    seconds = round(float(seconds), 3)
    m = re.fullmatch(r'\s*(?:haz\s+el\s+)?v[ií]deo\s+(10|[1-9])\s*[.!]?\s*', command, re.I)
    if not m:
        raise ValueError('Use exactly “Haz el vídeo 3”, with an explicit report ID')
    if not 0 < seconds <= 3600 or not 1 <= scene_count <= 300:
        raise ValueError('Invalid production duration/scene count')
    with connect(root) as db:
        row = db.execute('SELECT * FROM idea_reports WHERE id=?', (report_id,)).fetchone()
        if not row:
            raise ValueError('Import the report first; never guess a prior idea')
        report = json.loads(row['content']); number = int(m[1]); idea = report['ideas'][number-1]
        reference = db.execute('SELECT content FROM channel_references WHERE channel=?', (idea['channel'],)).fetchone()
        voice = read(REPO/'automation/channel-profiles.json')
        spec = {'reportSha256': row['sha'], 'idea': idea, 'material': report['material'], 'targetSeconds': seconds,
                'sceneCount': scene_count, 'policy': POLICY, 'voice': {'model': voice['model'], **voice['channels'][idea['channel']]},
                'visualReference': json.loads(reference['content']) if reference else None}
        job_id = 'prod_'+fingerprint({'report': row['sha'], 'number': number, 'channel': idea['channel'], 'seconds': seconds, 'count': scene_count})[:24]
        prior = db.execute('SELECT * FROM productions WHERE id=?', (job_id,)).fetchone()
        if not prior:
            db.execute('INSERT INTO productions(id,report_id,choice,channel,spec,state) VALUES(?,?,?,?,?,?)',
                       (job_id, report_id, number, idea['channel'], json.dumps(spec, ensure_ascii=False), 'queued'))
            event(db, job_id, 'selected', {'report': report_id, 'number': number, 'policy': POLICY})
    return {'id': job_id, 'state': prior['state'] if prior else 'queued', 'existing': bool(prior)}


def production(root, job_id):
    identifier(job_id)
    with connect(root) as db:
        row = db.execute('SELECT * FROM productions WHERE id=?', (job_id,)).fetchone()
    if not row:
        raise ValueError('Unknown production')
    return dict(row)


def copy_asset(source, target, heartbeat=lambda: None):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if render.digest(target) == render.digest(source):
            return
        raise ValueError('Destination exists with different content: '+target.name)
    temp = target.with_name(target.name+'.'+uuid.uuid4().hex+'.partial')
    try:
        with Path(source).open('rb') as src, temp.open('xb') as dst:
            for chunk in iter(lambda: src.read(1024*1024), b''):
                heartbeat(); dst.write(chunk)
            dst.flush(); os.fsync(dst.fileno())
        os.link(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def attach_script(root, job_id, script_path, metadata_path):
    job = production(root, job_id); spec = json.loads(job['spec']); validated = contract('job', read(script_path, 2*1024*1024))
    script = validated['job']; meta = read(metadata_path)
    if script['niche']+'-'+script['language'] != job['channel'] or len(script['scenes']) != spec['sceneCount']:
        raise ValueError('Script channel or scene count differs from selected production')
    if script['aspectRatio'] != '16:9' or not isinstance(meta.get('title'), str) or not 1 <= len(meta['title']) <= 100:
        raise ValueError('Landscape script and title up to 100 characters required')
    if not isinstance(meta.get('description'), str) or len(meta['description']) > 5000 or not isinstance(meta.get('tags'), list) or any(not isinstance(t, str) for t in meta['tags']) or sum(len(t) for t in meta['tags']) > 450:
        raise ValueError('Invalid description/tags')
    planned = meta.get('editorialShorts', [])
    if not isinstance(planned, list) or len(planned)>12:
        raise ValueError('At most twelve editorial Shorts may be planned')
    for clip in planned:
        a, b = clip.get('firstScene'), clip.get('lastScene')
        if type(a) is not int or type(b) is not int or not 1 <= a <= b <= len(script['scenes']) or not isinstance(clip.get('title'), str) or not 1 <= len(clip['title']) <= 100 or not clip.get('reason'):
            raise ValueError('Editorial Shorts require complete scene ranges, title and reason')
    payload = {'job': script, 'metadata': meta, 'sha256': fingerprint(script)}
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE'); current = db.execute('SELECT state,script FROM productions WHERE id=?', (job_id,)).fetchone()
        if current['script']:
            if json.loads(current['script']) != payload:
                raise ValueError('Committed script is immutable; use a new report version')
            return {'id': job_id, 'existing': True}
        if current['state'] not in ('queued', 'blocked'):
            raise ValueError('Do not attach inputs to active/completed production')
        db.execute("UPDATE productions SET script=?,state='queued',error=NULL WHERE id=?", (json.dumps(payload, ensure_ascii=False), job_id))
        event(db, job_id, 'script_attached', {'sha256': payload['sha256']})
    return {'id': job_id, 'scriptSha256': payload['sha256']}


def media_contract(ready, root, script, spec):
    if ready.get('format') != 'video-factory-ready/v1' or ready.get('scriptSha256') != fingerprint(script):
        raise ValueError('Media must bind the exact normalized script hash')
    if ready.get('material') not in ('real', 'synthetic'):
        raise ValueError('Label media real/synthetic')
    if spec['material'] == 'research' and ready['material'] != 'real':
        raise ValueError('Synthetic media cannot replace a real production')
    paths, seen = [], set()
    for item in ready.get('artifacts', []):
        relative = Path(item.get('path', ''))
        if relative.is_absolute() or '..' in relative.parts or str(relative) in seen or str(relative) in ('ready.json', '.'):
            raise ValueError('Use distinct normalized relative artifact paths')
        seen.add(str(relative)); identifier(item.get('role')); paths.append((render.local_asset(root, item), item))
    roles = {}
    for path, item in paths:
        roles.setdefault(item['role'], []).append(path)
    def one(role):
        if len(roles.get(role, [])) != 1:
            raise ValueError('Exactly one '+role+' artifact required')
        return roles[role][0]
    if ready.get('mode') == 'existing':
        master = one('master'); h = contract('handoff', read(one('handoff')))
        if h['video']['name'] != master.name or h['video']['sha256'] != render.digest(master) or h['video']['size'] != master.stat().st_size:
            raise ValueError('Master differs from final handoff')
        if h['jobId'] != script['id'] or h['language'] != script['language'] or h['subtitlesBurned']:
            raise ValueError('Clean master/handoff must belong to this script/language')
        if len(roles.get('image', [])) != len(script['scenes']):
            raise ValueError('Image required for each scene')
        contract('bindings', job=script, files=[{'path': str(x)} for x in [*roles['image'], one('bindings')]])
        one('audio'); one('project'); one('presentation'); duration = h['video']['duration']
    elif ready.get('mode') == 'render':
        manifest = read(one('render-manifest')); duration = render.validate(manifest, one('render-manifest').parent)
        if manifest['id'] != script['id'] or manifest['channel'] != script['niche']+'-'+script['language'] or manifest['material'] != ready['material']:
            raise ValueError('Render identity differs from script')
        if [(s['narration'], s['prompt']) for s in manifest['scenes']] != [(s['narration'], s['imagePrompt']) for s in script['scenes']]:
            raise ValueError('Render scene text/prompts differ from selected script')
        expected = [render.local_asset(one('render-manifest').parent, s['image']) for s in manifest['scenes']]+[render.local_asset(one('render-manifest').parent, manifest['audio'])]
        if any(p not in [x[0] for x in paths] for p in expected):
            raise ValueError('Ready artifacts must enumerate all render dependencies')
    else:
        raise ValueError('Only existing/render modes; no generation adapter enabled')
    if abs(duration-spec['targetSeconds']) > max(.15, spec['targetSeconds']*.15):
        raise ValueError('Duration differs from target; do not relabel smoke test as 18 minutes')
    return paths


def attach_media(root, job_id, ready_path):
    job = production(root, job_id)
    if not job['script']:
        raise ValueError('Attach exact script before media')
    ready_path = Path(ready_path).resolve(); data = read(ready_path); script = json.loads(job['script'])['job']
    paths = media_contract(data, ready_path.parent, script, json.loads(job['spec'])); pin = fingerprint(data)
    target = owned(root, 'productions', job_id, 'inputs', pin)
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE'); current = db.execute('SELECT state,media FROM productions WHERE id=?', (job_id,)).fetchone()
        if current['media']:
            if json.loads(current['media'])['sha256'] != pin:
                raise ValueError('Media snapshot is immutable')
            return {'id': job_id, 'existing': True}
        if current['state'] not in ('queued', 'blocked'):
            raise ValueError('Do not attach media while a worker owns production')
        for path, item in paths:
            copy_asset(path, owned(target, item['path']))
        media_contract(data, target, script, json.loads(job['spec'])); render.atomic_json(target/'ready.json', data)
        db.execute("UPDATE productions SET media=?,state='queued',error=NULL WHERE id=?", (json.dumps({'path': str(target/'ready.json'), 'sha256': pin}), job_id))
        event(db, job_id, 'media_attached', {'sha256': pin, 'mode': data['mode']})
    return {'id': job_id, 'snapshotSha256': pin}


def set_reference(root, channel, path):
    if channel not in CHANNELS:
        raise ValueError('Unknown channel')
    path = Path(path).resolve()
    if path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp') or path.stat().st_size > 30*1024*1024:
        raise ValueError('Reference must be a static image up to 30 MiB')
    if not any(s.get('width', 0)>0 and s.get('height', 0)>0 for s in render.probe(path)['streams']):
        raise ValueError('Cannot decode reference')
    sha = render.digest(path); target = owned(root, 'references', channel, sha+path.suffix.lower()); copy_asset(path, target)
    value = {'path': str(target), 'sha256': sha}
    with connect(root) as db:
        db.execute('INSERT OR REPLACE INTO channel_references VALUES(?,?)', (channel, json.dumps(value)))
    return {'channel': channel, 'reference': value, 'scope': 'new selections only'}


def scan_inbox(root):
    """Consume only explicitly ready envelopes in the dedicated inbox, idempotently.

    Producers write assets first, the envelope last via atomic rename. Partial
    downloads or hash mismatches never start a render or a generation retry.
    """
    results = []
    for path in sorted(owned(root, 'inbox').glob('*/production.ready.json')):
        try:
            owned(root, path)
            envelope = read(path)
            if envelope.get('format') != 'video-factory-inbox/v1':
                raise ValueError('Unsupported inbox envelope')
            job_id = identifier(envelope.get('productionId'))
            script = render.local_asset(path.parent, envelope['script'])
            metadata = render.local_asset(path.parent, envelope['metadata'])
            ready = render.local_asset(path.parent, envelope['media'])
            attach_script(root, job_id, script, metadata)
            attach_media(root, job_id, ready)
            results.append({'id': job_id, 'accepted': True})
        except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
            results.append({'file': path.name, 'accepted': False, 'error': str(error)[:1000]})
    return results


def audit(path, duration, orientation):
    p = subprocess.run(['node', str(REPO/'tools/audit-mp4.cjs'), str(path), str(duration), orientation], capture_output=True, timeout=max(120, duration*2))
    if p.returncode:
        raise ValueError('MP4 failed audit: '+(p.stderr or p.stdout).decode(errors='replace')[:1000])
    data = json.loads(p.stdout); data['file'] = Path(path).name
    return data


def execute_stage(root, job, stage, outputs, heartbeat):
    spec = json.loads(job['spec']); work = owned(root, 'productions', job['id']); work.mkdir(parents=True, exist_ok=True)
    if stage == 'brief':
        request = {'format': 'video-factory-script-request/v1', 'productionId': job['id'], **spec,
          'targetWords': round(spec['targetSeconds']/60*(138 if job['channel'].endswith('-es') else 145)),
          'averageVisualSeconds': spec['targetSeconds']/spec['sceneCount'],
          'requiredAnalysis': ['hook', 'pacing', 'pointOfView', 'formality', 'humor', 'suspense', 'transitions', 'ending'],
          'instructions': 'Write an original script using verified facts. Analyse techniques, never copy creators. Missing metrics remain unknown. Supply job JSON and title/description/tags. No remote API or quota authorized.'}
        path = work/'script.request.json'; render.atomic_json(path, request)
        return {'request': str(path)}, [path]
    if stage == 'script':
        if not job['script']:
            raise Blocked('waiting_for_script: ChatGPT/local author supplies script; no paid API fallback')
        content = json.loads(job['script']); validated = contract('job', content['job'])
        paths = [work/'job.json', work/'metadata.json', work/'script.txt', work/'prompts-numbered.txt', work/'media.request.json']
        render.atomic_json(paths[0], content['job']); render.atomic_json(paths[1], content['metadata'])
        paths[2].write_text('\n\n'.join(s['narration'] for s in content['job']['scenes']), encoding='utf8'); paths[3].write_text(validated['prompts'], encoding='utf8')
        render.atomic_json(paths[4], {'format': 'video-factory-media-request/v1', 'scriptSha256': content['sha256'], 'sceneCount': spec['sceneCount'],
          'voice': spec['voice'], 'visualReference': spec['visualReference'], 'generationStatus': 'not-authorized', 'policy': POLICY,
          'instructions': 'Reuse existing/synthetic assets. Never Run/Preview generation, activate billing or evade quotas. Supply image bindings, audio and reviewed alignment or an existing audited master.'})
        return {'scriptSha256': content['sha256'], 'jobPath': str(paths[0])}, paths
    if stage == 'media':
        if not job['media']:
            raise Blocked('waiting_for_existing_media: generation quota authorized = 0; see media.request.json')
        source = json.loads(job['media']); ready_path = Path(source['path']); ready = read(ready_path)
        if fingerprint(ready) != source['sha256']:
            raise ValueError('Media snapshot changed')
        paths = media_contract(ready, ready_path.parent, json.loads(job['script'])['job'], spec)
        return {'ready': str(ready_path)}, [ready_path, *[x[0] for x in paths]]
    ready_path = Path(outputs['media']['ready']); ready = read(ready_path)
    roles = {role: [render.local_asset(ready_path.parent, a) for a in ready['artifacts'] if a['role']==role] for role in {a['role'] for a in ready['artifacts']}}
    if stage == 'assembly':
        if ready['mode'] == 'existing':
            master, presentation, handoff_path = roles['master'][0], roles['presentation'][0], roles['handoff'][0]
            h = contract('handoff', read(handoff_path)); duration = h['video']['duration']
        else:
            manifest_path = roles['render-manifest'][0]; manifest = read(manifest_path); render.enqueue(Path(root)/'factory.sqlite', manifest_path)
            with render.connect(Path(root)/'factory.sqlite') as db:
                q = db.execute('SELECT * FROM jobs WHERE id=?', (manifest['id'],)).fetchone()
            if q['state'] == 'failed':
                raise ValueError('Render failed; explicit production retry required')
            if q['state'] == 'running':
                raise Blocked('render_owned_by_another_worker')
            r = json.loads(q['result']) if q['state']=='review' else render.work_once(Path(root)/'factory.sqlite', work/'renders', job_id=manifest['id'], external_heartbeat=heartbeat)
            if not r:
                raise Blocked('render_not_available')
            master = Path(r['master']); handoff_path = master.with_name('master.clipfarming.json'); h = contract('handoff', read(handoff_path)); duration = h['video']['duration']
            presentation = Path(render.render(manifest_path, work/'renders', heartbeat, burn=True)['master'])
        checks = [audit(master, duration, 'horizontal'), audit(presentation, duration, 'horizontal')]
        return {'master': str(master), 'presentation': str(presentation), 'handoff': str(handoff_path), 'audits': checks}, [master, presentation, handoff_path]
    if stage == 'shorts':
        location = REPO.parent/'clipfarming/tools/local_shorts.py'
        if not location.is_file():
            raise Blocked('Install ClipFarming development checkout beside AutoVideo')
        module_spec = importlib.util.spec_from_file_location('clipfarming_local_shorts', location); module = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
        assembly = outputs['assembly']; h = read(assembly['handoff'])
        content = json.loads(job['script']); planned = content['metadata'].get('editorialShorts', []); editorial = None
        if planned:
            if ready['mode']=='render':
                timeline = read(roles['render-manifest'][0])['scenes']
            else:
                project = read(roles['project'][0], 600*1024*1024)
                if contract('job', project['factoryJob'])['job'] != content['job']:
                    raise ValueError('Editable project differs from the selected script')
                timeline = project['scenes']
                if [s['text'] for s in timeline] != [s['narration'] for s in content['job']['scenes']]:
                    raise ValueError('Editable project scene order differs from the script')
            editorial = [{'start': timeline[c['firstScene']-1]['start'], 'end': timeline[c['lastScene']-1]['end'],
                          'title': c['title'], 'reason': c['reason']} for c in planned]
        clips = module.export(assembly['master'], h, work/'shorts', heartbeat, count=3, target=min(60, spec['targetSeconds']),
                              flex=min(20, max(1, spec['targetSeconds']/4)), editorial=editorial)
        editable = work/'clipfarming-local-project.json'
        render.atomic_json(editable, {'format': 'corta-studio/v1', 'factoryJobId': h['jobId'], 'video': h['video'], 'settings':
          {'mode': 'local', 'aspect': 'vertical', 'framing': 'contain', 'resolution': '720', 'fps': '30', 'burnSubs': True},
          'cues': h['cues'], 'clips': [c['selection'] for c in clips], 'subtitleName': 'AutoVideo cues'})
        return {'clips': clips, 'project': str(editable), 'selection': 'script-editorial-plan' if planned else 'shared-ClipFarming-local-heuristics', 'needsEditorialReview': True}, [editable, *[Path(c['path']) for c in clips]]
    if stage != 'package':
        raise ValueError('Unsupported stage')
    return package(root, job, outputs, ready, ready_path.parent, heartbeat)


def package(root, job, outputs, ready, input_root, heartbeat):
    work = owned(root, 'productions', job['id']); spec = json.loads(job['spec']); content = json.loads(job['script']); niche, language = job['channel'].rsplit('-', 1)
    final = owned(root, 'deliveries', niche, language, job['report_id'], f"video-{job['choice']:02}-{job['id']}")
    if final.exists():
        validation = read(final/'validation.json')
        if validation['productionId'] != job['id']:
            raise ValueError('Delivery belongs to another production')
        for a in validation['files']:
            render.local_asset(final, a)
        return {'directory': str(final), 'validation': validation}, [final/'validation.json', *[final/a['path'] for a in validation['files']]]
    staging = owned(root, 'delivery-staging', job['id']); staging.mkdir(parents=True, exist_ok=True)
    copies = [(outputs['assembly']['presentation'], 'long.mp4'), (outputs['assembly']['master'], 'master-clean.mp4'), (work/'script.txt', 'script.txt'),
      (work/'prompts-numbered.txt', 'prompts-numbered.txt'), (work/'job.json', 'job.json'), (work/'metadata.json', 'metadata.json')]
    copies += [(c['path'], f'shorts/short-{i+1:02}.mp4') for i, c in enumerate(outputs['shorts']['clips'])]
    copies += [(render.local_asset(input_root, a), 'sources/'+a['path']) for a in ready['artifacts']]
    for source, name in copies:
        copy_asset(Path(source), owned(staging, name), heartbeat)
    h = read(outputs['assembly']['handoff']); h['video'] = {**h['video'], 'name': 'master-clean.mp4'}
    render.atomic_json(staging/'master-clean.clipfarming.json', contract('handoff', h))
    editable = read(outputs['shorts']['project']); editable['video'] = h['video']; render.atomic_json(staging/'clipfarming-project.json', editable)
    for name, text in [('title.txt', content['metadata']['title']), ('description.txt', content['metadata']['description']), ('tags.txt', ', '.join(content['metadata']['tags']))]:
        (staging/name).write_text(text, encoding='utf8')
    thumb = staging/'thumbnail.jpg'
    if not thumb.exists():
        temp = staging/'thumbnail.partial.jpg'
        render.execute(['ffmpeg', '-v', 'error', '-y', '-protocol_whitelist', 'file,pipe', '-ss', '0.5', '-i', str(staging/'long.mp4'),
          '-frames:v', '1', '-vf', 'scale=1280:720', '-q:v', '2', '-threads', '1', str(temp)], staging, heartbeat, {'peakFfmpegRssBytes': 0})
        if not any(s.get('width')==1280 and s.get('height')==720 for s in render.probe(temp)['streams']):
            raise ValueError('Thumbnail decode failed')
        temp.replace(thumb)
    plan = {'format': 'video-factory-youtube-preparation/v1', 'productionId': job['id'], 'channelProfile': job['channel'], 'channelId': None,
      'uploadEnabled': False, 'publishEnabled': False,
      'videos': [{'file': 'long.mp4', 'snippet': {k:content['metadata'][k] for k in ('title','description','tags')}, 'status': {'privacyStatus': 'private'}}]+
        [{'file': f'shorts/short-{i+1:02}.mp4', 'snippet': {'title': c['selection']['title'][:100], 'description': content['metadata']['description'], 'tags': content['metadata']['tags']}, 'status': {'privacyStatus': 'private'}} for i, c in enumerate(outputs['shorts']['clips'])],
      'pending': ['Authorize exact YouTube channel via official OAuth', 'Review content, audience and synthetic-media disclosure', 'Explicitly approve the exact upload plan; optional official client remains disabled']}
    render.atomic_json(staging/'youtube-preparation.json', plan)
    files = [{'path': str(p.relative_to(staging)).replace(os.sep, '/'), 'sha256': render.digest(p), 'bytes': p.stat().st_size}
      for p in sorted(staging.rglob('*')) if p.is_file() and p.name not in ('validation.json', 'ffmpeg.log')]
    validation = {'format': 'video-factory-delivery/v1', 'productionId': job['id'], 'reportId': job['report_id'], 'ideaNumber': job['choice'], 'channel': job['channel'],
      'sourceReportMaterial': spec['material'], 'mediaMaterial': ready['material'], 'policy': POLICY, 'files': files,
      'longVideoAudits': outputs['assembly']['audits'], 'shortVideoAudits': [c['audit'] for c in outputs['shorts']['clips']],
      'reviewRequired': True, 'humanListeningApproved': False, 'thumbnail': 'frame-extraction-not-a-generated-or-CTR-tested-design',
      'shortSelection': outputs['shorts']['selection'], 'semanticQualityGuaranteed': False, 'userPcFolderTested': False}
    render.atomic_json(staging/'validation.json', validation); heartbeat(); final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        raise ValueError('Delivery appeared concurrently; refuse overwrite')
    staging.rename(final)
    return {'directory': str(final), 'validation': validation}, [final/'validation.json', *[final/a['path'] for a in files]]


def run_once(root, job_id=None, stop_after_stage=None):
    owner = uuid.uuid4().hex
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE')
        for r in db.execute("SELECT id FROM productions WHERE state='running' AND lease<?", (time.time(),)).fetchall():
            db.execute("UPDATE productions SET state='failed',owner=NULL,lease=NULL,failures=failures+1,error='Worker lease expired; explicit retry required' WHERE id=?", (r['id'],)); event(db, r['id'], 'lease_expired')
        query = "SELECT * FROM productions WHERE state='queued' AND failures<3"
        row = db.execute(query+(' AND id=?' if job_id else '')+' ORDER BY rowid LIMIT 1', (job_id,) if job_id else ()).fetchone()
        if not row:
            return None
        job = dict(row); db.execute("UPDATE productions SET state='running',owner=?,lease=?,error=NULL WHERE id=?", (owner, time.time()+120, job['id'])); event(db, job['id'], 'worker_claimed')
    last = [0.]
    def heartbeat():
        if time.time()-last[0] < 5:
            return
        with connect(root) as db:
            c = db.execute("UPDATE productions SET lease=? WHERE id=? AND state='running' AND owner=?", (time.time()+120, job['id'], owner))
            if c.rowcount != 1:
                raise RuntimeError('Production worker lost its lease')
        last[0] = time.time()
    outputs, resumed = {}, []
    try:
        for stage in STAGES:
            heartbeat()
            with connect(root) as db:
                prior = db.execute('SELECT receipt FROM production_stages WHERE job_id=? AND name=?', (job['id'], stage)).fetchone()
            if prior:
                receipt = json.loads(prior['receipt'])
                for a in receipt['files']:
                    p = owned(root, a['path'])
                    if not p.is_file() or render.digest(p) != a['sha256']:
                        raise ValueError('Completed stage artifact changed; explicit repair required: '+stage)
                outputs[stage] = receipt['result']; resumed.append(stage); continue
            result, paths = execute_stage(root, job, stage, outputs, heartbeat)
            receipt = {'result': result, 'files': [{'path': str(owned(root, p).relative_to(Path(root).resolve())), 'sha256': render.digest(p)} for p in paths]}
            last[0] = 0; heartbeat()
            with connect(root) as db:
                db.execute('INSERT INTO production_stages VALUES(?,?,?)', (job['id'], stage, json.dumps(receipt, ensure_ascii=False))); event(db, job['id'], 'stage_completed', {'stage': stage})
            outputs[stage] = result
            if stage == stop_after_stage:
                raise RuntimeError('Controlled interruption after stage '+stage)
        last[0] = 0; heartbeat(); result = {'id': job['id'], 'state': 'review', 'directory': outputs['package']['directory'], 'resumedStages': resumed, 'policy': POLICY}
        with connect(root) as db:
            db.execute("UPDATE productions SET state='review',owner=NULL,lease=NULL,result=? WHERE id=? AND owner=?", (json.dumps(result), job['id'], owner)); event(db, job['id'], 'ready_for_review')
        return result
    except Blocked as error:
        with connect(root) as db:
            db.execute("UPDATE productions SET state='blocked',owner=NULL,lease=NULL,error=? WHERE id=? AND owner=?", (str(error), job['id'], owner)); event(db, job['id'], 'blocked', {'reason': str(error)})
        return {'id': job['id'], 'state': 'blocked', 'reason': str(error), 'resumedStages': resumed}
    except BaseException as error:
        with connect(root) as db:
            db.execute("UPDATE productions SET state='failed',owner=NULL,lease=NULL,failures=failures+1,error=? WHERE id=? AND owner=?", (str(error)[:1000], job['id'], owner)); event(db, job['id'], 'failed', {'stage': stage, 'reason': str(error)[:1000]})
        raise


def retry(root, job_id, reset_from=None):
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE'); row = db.execute('SELECT * FROM productions WHERE id=?', (job_id,)).fetchone()
        if not row or row['state'] not in ('failed', 'blocked') or row['failures'] >= 3:
            raise ValueError('Explicit retry requires failed/blocked job with fewer than three failures')
        if reset_from:
            if reset_from not in STAGES:
                raise ValueError('Unknown stage')
            for stage in STAGES[STAGES.index(reset_from):]:
                db.execute('DELETE FROM production_stages WHERE job_id=? AND name=?', (job_id, stage))
        if row['script']:
            db.execute("UPDATE jobs SET state='queued',owner=NULL WHERE id=? AND state='failed' AND attempts<3", (json.loads(row['script'])['job']['id'],))
        db.execute("UPDATE productions SET state='queued',error=NULL,owner=NULL,lease=NULL WHERE id=?", (job_id,)); event(db, job_id, 'explicit_retry', {'resetFrom': reset_from})
    return {'id': job_id, 'state': 'queued'}


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='cmd', required=True)
    for name in ['init', 'status', 'scan']:
        q = sub.add_parser(name); q.add_argument('root')
    q = sub.add_parser('import-report'); q.add_argument('root'); q.add_argument('report')
    q = sub.add_parser('select'); q.add_argument('root'); q.add_argument('report_id'); q.add_argument('choice'); q.add_argument('--seconds', type=float, default=1080); q.add_argument('--scenes', type=int, default=160)
    q = sub.add_parser('attach-script'); q.add_argument('root'); q.add_argument('id'); q.add_argument('script'); q.add_argument('metadata')
    q = sub.add_parser('attach-media'); q.add_argument('root'); q.add_argument('id'); q.add_argument('ready')
    q = sub.add_parser('reference'); q.add_argument('root'); q.add_argument('channel', choices=CHANNELS); q.add_argument('image')
    q = sub.add_parser('work'); q.add_argument('root'); q.add_argument('--id'); q.add_argument('--watch', action='store_true')
    q = sub.add_parser('retry'); q.add_argument('root'); q.add_argument('id'); q.add_argument('--reset-from', choices=STAGES)
    a = p.parse_args()
    if a.cmd == 'init': result = init(a.root)
    elif a.cmd == 'import-report': result = import_report(a.root, a.report)
    elif a.cmd == 'select': result = select(a.root, a.report_id, a.choice, a.seconds, a.scenes)
    elif a.cmd == 'attach-script': result = attach_script(a.root, a.id, a.script, a.metadata)
    elif a.cmd == 'attach-media': result = attach_media(a.root, a.id, a.ready)
    elif a.cmd == 'reference': result = set_reference(a.root, a.channel, a.image)
    elif a.cmd == 'scan': result = scan_inbox(a.root)
    elif a.cmd == 'retry': result = retry(a.root, a.id, a.reset_from)
    elif a.cmd == 'work':
        while True:
            if a.watch: scan_inbox(a.root)
            result = run_once(a.root, a.id)
            if not a.watch: break
            if result: print(json.dumps(result, ensure_ascii=False), flush=True)
            time.sleep(5)
    else:
        with connect(a.root) as db:
            result = [dict(r) for r in db.execute('SELECT id,channel,report_id,choice,state,failures,error FROM productions ORDER BY rowid')]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
