#!/usr/bin/env python3
"""YouTube delivery extension. Default: review only, no network and no deletion.

Uses the existing factory database/receipts. Real transport is separate from the
state machine and requires an exact, locally approved plan; simulations cannot
authorize it. Never retries videos.insert after an ambiguous completed upload.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
import uuid
import factory_orchestrator as f

CHANNEL_ID = re.compile(r'UC[A-Za-z0-9_-]{22}')
VIDEO_ID = re.compile(r'[A-Za-z0-9_-]{11}')
GAP_SECONDS = 1800
FRESH_SECONDS = 900
STATES = ('awaiting_approval', 'upload_pending', 'uploading', 'upload_uncertain',
          'processing', 'ready_to_schedule', 'scheduling', 'scheduled', 'failed')


def connect(root):
    db = f.connect(root)
    db.executescript('''
      CREATE TABLE IF NOT EXISTS youtube_channels(role TEXT PRIMARY KEY, channel_id TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL, credential_ref TEXT NOT NULL, origin TEXT NOT NULL, confirmed REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS youtube_batches(id TEXT PRIMARY KEY, production_id TEXT UNIQUE NOT NULL,
        plan TEXT NOT NULL, sha TEXT NOT NULL, origin TEXT NOT NULL, state TEXT NOT NULL,
        approval TEXT, owner TEXT, lease REAL, error TEXT);
      CREATE TABLE IF NOT EXISTS youtube_items(id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, file TEXT NOT NULL,
        channel_id TEXT NOT NULL, publish_at REAL, state TEXT NOT NULL, video_id TEXT UNIQUE,
        session_ref TEXT, attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
        thumbnail_done INTEGER NOT NULL DEFAULT 0, evidence TEXT, checked_at REAL, error TEXT);
      CREATE TABLE IF NOT EXISTS youtube_slots(channel_id TEXT NOT NULL, publish_at REAL NOT NULL,
        item_id TEXT UNIQUE NOT NULL, PRIMARY KEY(channel_id,publish_at));
      CREATE TABLE IF NOT EXISTS youtube_media_claims(channel_id TEXT NOT NULL, sha TEXT NOT NULL,
        item_id TEXT UNIQUE NOT NULL, PRIMARY KEY(channel_id,sha));
      CREATE TABLE IF NOT EXISTS youtube_audit(seq INTEGER PRIMARY KEY, batch_id TEXT,
        item_id TEXT, event TEXT NOT NULL, at REAL NOT NULL, detail TEXT NOT NULL);
    ''')
    return db


def audit(db, batch, item, event, detail=None):
    # Never include OAuth objects, bearer tokens, upload URIs, raw HTTP errors.
    db.execute('INSERT INTO youtube_audit(batch_id,item_id,event,at,detail) VALUES(?,?,?,?,?)',
               (batch, item, event, time.time(), json.dumps(detail or {}, ensure_ascii=False)))


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('A date with explicit UTC offset is required')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Use an explicit timezone offset; ambiguous local times are refused')
    return date.timestamp()


def utc(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def bind_channel(root, role, observed, confirmed_id, credential_ref, origin='oauth'):
    if role not in f.CHANNELS or origin not in ('oauth', 'simulation'):
        raise ValueError('Unsupported role or evidence source')
    if len(observed) != 1 or observed[0].get('id') != confirmed_id or not CHANNEL_ID.fullmatch(confirmed_id):
        raise ValueError('Personally confirm the single channel returned by channels.list(mine=true)')
    f.identifier(credential_ref)
    title = observed[0].get('snippet', {}).get('title')
    if not isinstance(title, str) or not title:
        raise ValueError('Channel title required')
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT * FROM youtube_channels WHERE role=?', (role,)).fetchone()
        value = (role, confirmed_id, title, credential_ref, origin)
        if prior:
            if tuple(prior[k] for k in ('role','channel_id','title','credential_ref','origin')) != value:
                raise ValueError('Mapping is immutable; an explicit reviewed migration is required')
            return {'role': role, 'channelId': confirmed_id, 'existing': True}
        db.execute('INSERT INTO youtube_channels VALUES(?,?,?,?,?,?)', (*value, time.time()))
        audit(db, None, None, 'channel_confirmed', {'role': role, 'channelId': confirmed_id, 'origin': origin})
    return {'role': role, 'channelId': confirmed_id, 'existing': False}


def delivery(root, job_id):
    job = f.production(root, job_id)
    if job['state'] != 'review' or not job['result']:
        raise ValueError('Only a completed factory delivery can be prepared')
    path = f.owned(root, json.loads(job['result'])['directory'])
    v = f.read(path/'validation.json')
    if v.get('productionId') != job_id or v.get('channel') != job['channel']:
        raise ValueError('Delivery identity mismatch')
    # The completed package receipt is the ownership anchor, not a user-supplied list.
    with f.connect(root) as db:
        receipt = db.execute("SELECT receipt FROM production_stages WHERE job_id=? AND name='package'", (job_id,)).fetchone()
    if not receipt:
        raise ValueError('Factory package receipt required')
    receipt = json.loads(receipt['receipt'])
    anchors = {f.owned(root, a['path']).resolve(): a['sha256'] for a in receipt['files']}
    if anchors.get((path/'validation.json').resolve()) != f.render.digest(path/'validation.json'):
        raise ValueError('Delivery inventory changed since factory completion')
    return job, path, v, anchors


def prepare(root, job_id, schedule, origin='live', now=None):
    """Immutable, all-items plan; reserves calendar slots without calling YouTube."""
    now = time.time() if now is None else now
    if origin not in ('live','simulation'):
        raise ValueError('Unknown transport origin')
    job, path, v, anchors = delivery(root, job_id)
    prep = f.read(path/'youtube-preparation.json')
    if anchors.get((path/'youtube-preparation.json').resolve())!=f.render.digest(path/'youtube-preparation.json'):
        raise ValueError('YouTube preparation changed after factory validation')
    if prep.get('productionId') != job_id or prep.get('channelProfile') != job['channel']:
        raise ValueError('YouTube preparation identity mismatch')
    expected = ['long.mp4'] + sorted(a['path'] for a in v['files'] if re.fullmatch(r'shorts/short-\d+\.mp4', a['path']))
    if not expected[1:] or [i['file'] for i in prep['videos']] != expected:
        raise ValueError('Plan must include the long video and ALL delivered Shorts')
    if not isinstance(schedule, dict) or set(schedule) != {'mode','videos','review'} or schedule['mode'] not in ('private','schedule'):
        raise ValueError('Choose private review or explicitly approved future scheduling')
    review = schedule['review']
    if not isinstance(review, dict) or set(review) != {'contentApproved','madeForKids','containsSyntheticMedia','categoryId'}:
        raise ValueError('Editorial review, audience, disclosure and category must be chosen explicitly')
    if review['contentApproved'] is not True or type(review['madeForKids']) is not bool or type(review['containsSyntheticMedia']) is not bool or not re.fullmatch(r'\d{1,3}',str(review['categoryId'])):
        raise ValueError('Explicit review is required; do not invent an audience/disclosure choice')
    dates = schedule['videos']
    if not isinstance(dates, dict) or set(dates) != set(expected):
        raise ValueError('Provide an independent date (or null for private) for every required video')
    inventory = {a['path']: a for a in v['files']}
    videos = []
    for source in prep['videos']:
        name = source['file']; p = f.owned(path, name); a = inventory[name]
        if not p.is_file() or p.is_symlink() or f.render.digest(p) != a['sha256'] or anchors.get(p.resolve()) != a['sha256']:
            raise ValueError('Video differs from its factory receipt')
        when = timestamp(dates[name]) if dates[name] is not None else None
        if schedule['mode'] == 'schedule' and (when is None or when < now+300):
            raise ValueError('Schedule each video at least five minutes in the future')
        if schedule['mode'] == 'private' and when is not None:
            raise ValueError('Private review must not contain publishAt')
        body = {'snippet': {**source['snippet'], 'categoryId': str(review['categoryId']), 'defaultLanguage':job['channel'].rsplit('-',1)[1]},
                'status': {'privacyStatus':'private', 'selfDeclaredMadeForKids':review['madeForKids'],
                           'containsSyntheticMedia':review['containsSyntheticMedia'], 'license':'youtube', 'embeddable':True, 'publicStatsViewable':True}}
        if not 1 <= len(body['snippet']['title']) <= 100:
            raise ValueError('Invalid video title')
        videos.append({'file':name, 'sha256':a['sha256'], 'bytes':p.stat().st_size, 'body':body,
                       'publishAt':utc(when) if when else None,
                       'thumbnail':inventory.get('thumbnail.jpg') if name=='long.mp4' else None})
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE')
        mapping = db.execute('SELECT * FROM youtube_channels WHERE role=?',(job['channel'],)).fetchone()
        if not mapping or (origin=='live' and mapping['origin']!='oauth'):
            raise ValueError('Confirm the exact OAuth channel first; simulation mappings cannot authorize live uploads')
        plan = {'format':'video-factory-youtube-plan/v1','productionId':job_id,'directory':str(path.relative_to(Path(root).resolve())),
                'role':job['channel'],'channelId':mapping['channel_id'],'channelTitle':mapping['title'],
                'credentialRef':mapping['credential_ref'],'mode':schedule['mode'],'origin':origin,'videos':videos,
                'review':review,'policy':{'moneyEUR':0,'generationQuota':0,'uploadDefault':'private','cleanupEnabled':False}}
        sha = f.fingerprint(plan); batch = 'yt_'+sha[:24]
        prior = db.execute('SELECT * FROM youtube_batches WHERE production_id=?',(job_id,)).fetchone()
        if prior:
            if prior['sha'] != sha:
                raise ValueError('A different immutable plan exists; do not duplicate or silently reschedule')
            return {'id':prior['id'],'sha256':sha,'existing':True,'state':prior['state']}
        db.execute('INSERT INTO youtube_batches(id,production_id,plan,sha,origin,state) VALUES(?,?,?,?,?,?)',
                   (batch,job_id,json.dumps(plan,ensure_ascii=False),sha,origin,'awaiting_approval'))
        for i, video in enumerate(videos):
            item_id = batch+'_'+str(i); when = timestamp(video['publishAt']) if video['publishAt'] else None
            if db.execute('SELECT 1 FROM youtube_media_claims WHERE channel_id=? AND sha=?',(mapping['channel_id'],video['sha256'])).fetchone():
                raise ValueError('These exact video bytes are already reserved for this channel; review instead of uploading a duplicate')
            db.execute('INSERT INTO youtube_media_claims VALUES(?,?,?)',(mapping['channel_id'],video['sha256'],item_id))
            if when is not None:
                if db.execute('SELECT 1 FROM youtube_slots WHERE channel_id=? AND ABS(publish_at-?)<?',(mapping['channel_id'],when,GAP_SECONDS)).fetchone():
                    raise ValueError('Calendar conflict: keep at least thirty minutes between items on a channel')
                db.execute('INSERT INTO youtube_slots VALUES(?,?,?)',(mapping['channel_id'],when,item_id))
            db.execute('INSERT INTO youtube_items(id,batch_id,file,channel_id,publish_at,state) VALUES(?,?,?,?,?,?)',
                       (item_id,batch,video['file'],mapping['channel_id'],when,'awaiting_approval'))
        audit(db,batch,None,'plan_prepared',{'sha256':sha,'origin':origin,'items':len(videos),'mode':plan['mode']})
    return {'id':batch,'sha256':sha,'existing':False,'state':'awaiting_approval'}


def batch_info(root, batch):
    with connect(root) as db:
        row = db.execute('SELECT * FROM youtube_batches WHERE id=?',(batch,)).fetchone()
        if not row: raise ValueError('Unknown YouTube batch')
        items = [dict(r) for r in db.execute('SELECT * FROM youtube_items WHERE batch_id=? ORDER BY rowid',(batch,))]
    result = dict(row); result['plan'] = json.loads(result['plan']); result['items'] = items
    return result


def approve_simulation(root, batch):
    info = batch_info(root,batch)
    if info['origin']!='simulation': raise ValueError('A simulation cannot approve live media transfer')
    with connect(root) as db:
        db.execute("UPDATE youtube_batches SET approval=?,state='upload_pending' WHERE id=? AND approval IS NULL",(info['sha'],batch))
        db.execute("UPDATE youtube_items SET state='upload_pending' WHERE batch_id=? AND state='awaiting_approval'",(batch,))
        audit(db,batch,None,'simulation_approved')


class AmbiguousUpload(Exception): pass
class RetryLater(Exception):
    def __init__(self, seconds=60): self.seconds=max(1,min(float(seconds),86400))


def live_approval(root, info):
    """No CLI/UI creates this grant. First actual transfer needs separate user approval."""
    path = f.owned(root,'youtube-live-approval.json')
    if not path.is_file(): raise ValueError('Live uploads disabled: request review of channel, files and visibility first')
    grant = f.read(path)
    if (grant.get('format')!='video-factory-live-approval/v1' or grant.get('planSha256')!=info['sha'] or
        grant.get('channelId')!=info['plan']['channelId'] or grant.get('userApproved') is not True or
        grant.get('mode')!=info['plan']['mode'] or timestamp(grant.get('expiresAt'))<=time.time()):
        raise ValueError('An unexpired explicit user approval of this exact plan is required')


def approve_live(root, batch):
    info=batch_info(root,batch)
    if info['origin']!='live': raise ValueError('Simulation cannot become live')
    live_approval(root,info)
    with connect(root) as db:
        db.execute("UPDATE youtube_batches SET approval=?,state='upload_pending' WHERE id=? AND approval IS NULL",(info['sha'],batch))
        db.execute("UPDATE youtube_items SET state='upload_pending' WHERE batch_id=? AND state='awaiting_approval'",(batch,))
        audit(db,batch,None,'exact_plan_approved',{'sha256':info['sha']})


def check_resource(video, item, spec, scheduled=False):
    if video.get('id')!=item['video_id'] or video.get('snippet',{}).get('channelId')!=item['channel_id']:
        raise ValueError('YouTube video/channel identity mismatch')
    status=video.get('status',{}); processing=video.get('processingDetails',{}).get('processingStatus')
    if status.get('uploadStatus') in ('failed','rejected','deleted') or processing in ('failed','terminated'):
        raise ValueError('YouTube rejected or failed to process the video')
    if status.get('privacyStatus')!='private':
        raise ValueError('Unexpected visibility; stop and request review')
    done=status.get('uploadStatus')=='processed' and processing=='succeeded'
    if scheduled:
        if not spec['publishAt'] or not status.get('publishAt') or timestamp(status['publishAt'])!=timestamp(spec['publishAt']):
            raise ValueError('Future publication date not confirmed by videos.list')
        if video.get('snippet',{}).get('title')!=spec['body']['snippet']['title']:
            raise ValueError('Uploaded title differs from the reviewed plan')
        for key in ('selfDeclaredMadeForKids','containsSyntheticMedia'):
            if status.get(key) is not spec['body']['status'][key]:
                raise ValueError('Audience or synthetic-media disclosure not confirmed')
    return done


def tick(root, batch, transport, now=None):
    """One recoverable action/item/poll. Does not spin, sleep, or reinsert on error."""
    now=time.time() if now is None else now; info=batch_info(root,batch); plan=info['plan']
    if transport.origin!=info['origin'] or info['approval']!=info['sha']:
        raise ValueError('Unapproved plan or wrong transport origin')
    if info['origin']=='live': live_approval(root,info)
    owner=uuid.uuid4().hex
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT owner,lease FROM youtube_batches WHERE id=?',(batch,)).fetchone()
        if row['owner'] and row['lease']>now: raise ValueError('Another YouTube worker owns this batch')
        db.execute('UPDATE youtube_batches SET owner=?,lease=? WHERE id=?',(owner,now+300,batch))
    try:
        if transport.channel_id()!=plan['channelId']:
            raise ValueError('OAuth account/channel differs from the pinned production channel')
        for item in info['items']:
            with connect(root) as db:
                changed=db.execute('UPDATE youtube_batches SET lease=? WHERE id=? AND owner=?',(time.time()+300,batch,owner))
                if changed.rowcount!=1: raise ValueError('YouTube worker lost its lease')
            if item['state'] in ('scheduled','failed','upload_uncertain','awaiting_approval') or item['next_attempt']>now:
                continue
            spec=next(v for v in plan['videos'] if v['file']==item['file'])
            try:
                state=item['state']; path=f.owned(root,plan['directory'],item['file'])
                if state in ('upload_pending','uploading'):
                    if not path.is_file() or path.is_symlink() or path.stat().st_size!=spec['bytes'] or f.render.digest(path)!=spec['sha256']:
                        raise ValueError('Upload source changed')
                    if not item['session_ref']:
                        if state=='uploading': raise AmbiguousUpload()
                        # Persist intent before network; a crash without URI is ambiguous.
                        with connect(root) as db:
                            db.execute("UPDATE youtube_items SET state='uploading' WHERE id=?",(item['id'],));audit(db,batch,item['id'],'upload_session_requested')
                        ref=transport.start(spec,item['id'])
                        with connect(root) as db:
                            db.execute('UPDATE youtube_items SET session_ref=? WHERE id=?',(ref,item['id']));audit(db,batch,item['id'],'upload_session_saved')
                        item['session_ref']=ref
                    resource=transport.resume(item['session_ref'],path,spec)
                    if resource:
                        video_id=resource.get('id')
                        if not VIDEO_ID.fullmatch(video_id or ''): raise ValueError('Invalid completed upload ID')
                        with connect(root) as db:
                            db.execute("UPDATE youtube_items SET video_id=?,state='processing',attempts=0,error=NULL WHERE id=?",(video_id,item['id']))
                            audit(db,batch,item['id'],'upload_received',{'videoId':video_id})
                elif state in ('processing','ready_to_schedule','scheduling'):
                    resource=transport.get_video(item['video_id'])
                    if not check_resource(resource,item,spec):
                        with connect(root) as db:
                            db.execute('UPDATE youtube_items SET next_attempt=? WHERE id=?',(now+60,item['id']));audit(db,batch,item['id'],'still_processing')
                        continue
                    if not item['thumbnail_done'] and spec['thumbnail']:
                        thumb=f.owned(root,plan['directory'],spec['thumbnail']['path'])
                        if f.render.digest(thumb)!=spec['thumbnail']['sha256']: raise ValueError('Thumbnail changed')
                        transport.thumbnail(item['video_id'],thumb)
                        with connect(root) as db: db.execute('UPDATE youtube_items SET thumbnail_done=1 WHERE id=?',(item['id'],))
                        continue
                    if plan['mode']=='private':
                        with connect(root) as db:
                            db.execute("UPDATE youtube_items SET state='ready_to_schedule',evidence=?,checked_at=?,next_attempt=? WHERE id=?",(json.dumps(resource),now,now+300,item['id']))
                        continue
                    if timestamp(spec['publishAt'])<now+300:
                        raise ValueError('Schedule became too close/past: refuse immediate public release')
                    if state=='scheduling':
                        if check_resource(resource,item,spec,scheduled=True):
                            with connect(root) as db:
                                db.execute("UPDATE youtube_items SET state='scheduled',evidence=?,checked_at=?,error=NULL WHERE id=?",(json.dumps(resource),now,item['id']))
                                audit(db,batch,item['id'],'schedule_verified',{'videoId':item['video_id'],'channelId':item['channel_id'],'publishAt':spec['publishAt'],'origin':info['origin']})
                    else:
                        with connect(root) as db:
                            db.execute("UPDATE youtube_items SET state='scheduling' WHERE id=?",(item['id'],));audit(db,batch,item['id'],'schedule_requested')
                        # A successful PUT alone never advances to scheduled.
                        transport.schedule(item['video_id'],{**spec['body']['status'],'publishAt':spec['publishAt']})
            except AmbiguousUpload:
                with connect(root) as db:
                    db.execute("UPDATE youtube_items SET state='upload_uncertain',error='Upload outcome uncertain; manual reconciliation required' WHERE id=?",(item['id'],));audit(db,batch,item['id'],'upload_uncertain')
            except RetryLater as error:
                attempts=item['attempts']+1
                with connect(root) as db:
                    db.execute('UPDATE youtube_items SET attempts=?,next_attempt=?,state=CASE WHEN ?>=3 THEN ? ELSE state END,error=? WHERE id=?',
                        (attempts,now+error.seconds,attempts,'failed','Transient API/network error; bounded retry',item['id']))
                    audit(db,batch,item['id'],'retry_delayed',{'attempt':attempts,'delaySeconds':error.seconds})
            except Exception as error:
                # Never persist an exception text from an authenticated HTTP library.
                message=str(error)[:200] if isinstance(error,ValueError) else 'Transport error; explicit recovery required'
                with connect(root) as db:
                    db.execute("UPDATE youtube_items SET state='failed',error=? WHERE id=?",(message,item['id']));audit(db,batch,item['id'],'item_failed',{'type':type(error).__name__})
        with connect(root) as db:
            states=[r[0] for r in db.execute('SELECT state FROM youtube_items WHERE batch_id=?',(batch,))]
            overall='scheduled' if all(s=='scheduled' for s in states) else ('error' if any(s in ('failed','upload_uncertain') for s in states) else 'in_progress')
            db.execute('UPDATE youtube_batches SET state=?,error=NULL WHERE id=? AND owner=?',(overall,batch,owner))
    except Exception as error:
        with connect(root) as db:
            db.execute("UPDATE youtube_batches SET state='error',error=? WHERE id=? AND owner=?",('Worker stopped; review channel/authorization and audit',batch,owner))
            audit(db,batch,None,'worker_stopped',{'type':type(error).__name__})
        raise
    finally:
        with connect(root) as db: db.execute('UPDATE youtube_batches SET owner=NULL,lease=NULL WHERE id=? AND owner=?',(batch,owner))
    return batch_info(root,batch)


def refresh_verification(root,batch,transport,now=None):
    """Fresh GET evidence for every required item, even if a prior receipt passed."""
    now=time.time() if now is None else now; info=batch_info(root,batch)
    if transport.origin!=info['origin'] or transport.channel_id()!=info['plan']['channelId']:
        raise ValueError('Wrong verification account or evidence source')
    checks=[]
    for item,spec in zip(info['items'],info['plan']['videos']):
        try:
            if item['state']!='scheduled': raise ValueError('Item is not scheduled')
            resource=transport.get_video(item['video_id'])
            if not check_resource(resource,item,spec,scheduled=True): raise ValueError('Processing incomplete')
            if timestamp(spec['publishAt'])<=now: raise ValueError('Scheduled time has passed; actual publication must be reviewed separately')
            with connect(root) as db:
                db.execute('UPDATE youtube_items SET evidence=?,checked_at=? WHERE id=?',(json.dumps(resource),now,item['id']))
                audit(db,batch,item['id'],'remote_reverified',{'origin':info['origin']})
            checks.append({'id':item['id'],'passed':True})
        except Exception:
            with connect(root) as db:
                db.execute('UPDATE youtube_items SET checked_at=NULL WHERE id=?',(item['id'],));audit(db,batch,item['id'],'remote_reverification_failed')
            checks.append({'id':item['id'],'passed':False})
    return checks


def cleanup_simulation(root,batch,now=None):
    """Read/hash only. No unlink/rmtree/delete implementation exists in this phase."""
    now=time.time() if now is None else now; info=batch_info(root,batch); plan=info['plan']
    job,path,v,anchors=delivery(root,info['production_id']); reasons=[]; checks=[]
    if job['state']!='review': reasons.append('Production is active or incomplete')
    if info['owner']: reasons.append('A YouTube worker still owns this delivery')
    if plan['mode']!='schedule': reasons.append('Private upload is not confirmed public scheduling')
    if info['origin']!='live': reasons.append('Simulated YouTube evidence cannot authorize real cleanup')
    if len(info['items'])!=len(plan['videos']): reasons.append('Required item inventory differs')
    for item,spec in zip(info['items'],plan['videos']):
        passed=False
        try:
            if item['state']!='scheduled' or not item['checked_at'] or not 0<=now-item['checked_at']<=FRESH_SECONDS:
                raise ValueError('Upload/processing/schedule missing or verification stale')
            if not item['evidence'] or not check_resource(json.loads(item['evidence']),item,spec,scheduled=True):
                raise ValueError('Processing not confirmed')
            if timestamp(spec['publishAt'])<=now: raise ValueError('Publication time passed; recheck actual public status')
            passed=True
        except (ValueError,KeyError): reasons.append('Item '+item['file']+': not fully verified')
        checks.append({'file':item['file'],'videoId':item['video_id'],'channelId':item['channel_id'],'passed':passed})
    # Only finished-stage receipts may nominate files. No directory glob deletion.
    with f.connect(root) as db:
        receipts=[json.loads(r['receipt']) for r in db.execute('SELECT receipt FROM production_stages WHERE job_id=?',(job['id'],))]
        others={str(f.owned(root,a['path']).resolve()) for r in db.execute('SELECT receipt FROM production_stages WHERE job_id!=?',(job['id'],)) for a in json.loads(r['receipt'])['files']}
    known={str(f.owned(root,a['path'])):a['sha256'] for r in receipts for a in r['files']}
    candidates=[]; retained=[]; exclusions=[]
    for name,sha in sorted(known.items()):
        p=Path(name); rel=p.relative_to(Path(root).resolve()).as_posix()
        # Preserve media originals/inbox/bindings; only derived outputs/editables.
        inside_work=p.is_relative_to(f.owned(root,'productions',job['id']))
        inside_delivery=p.is_relative_to(path)
        if not (inside_work or inside_delivery) or '/sources/' in '/'+rel or '/inputs/' in '/'+rel:
            continue
        if p.suffix.lower() not in ('.mp4','.avfproject','.wav','.webm','.mkv'):
            retained.append(rel); continue
        if not p.is_file(): exclusions.append({'path':rel,'reason':'missing'}); continue
        if p.is_symlink() or any(x.is_symlink() or (hasattr(x,'is_junction') and x.is_junction()) for x in [p,*p.parents]) or p.stat().st_nlink!=1 or str(p.resolve()) in others:
            exclusions.append({'path':rel,'reason':'link, junction or referenced by another job'});continue
        if f.render.digest(p)!=sha:
            exclusions.append({'path':rel,'reason':'changed after completion'});continue
        candidates.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha,'reason':'factory-generated derived file with matching stage receipt'})
    if exclusions: reasons.append('Some nominated files changed or cannot be safely attributed')
    report={'format':'video-factory-cleanup-simulation/v1','batchId':batch,'productionId':job['id'],
            'simulatedAt':utc(now),'dryRun':True,'deletionImplemented':False,'deletionEnabled':False,
            'deletedFiles':0,'freedBytes':0,'potentialBytes':sum(a['bytes'] for a in candidates),
            'eligibleAfterRemoteChecks':not reasons,'blockers':reasons,'checks':checks,'files':candidates,
            'retainedSmallFiles':retained,'exclusions':exclusions,
            'warning':'Original images/audio and source projects retained. Deleting derived masters later can prevent lossless recovery; YouTube is not an original-file backup.'}
    output=f.owned(root,'cleanup-simulations',batch+'.json'); output.parent.mkdir(exist_ok=True); f.render.atomic_json(output,report)
    with connect(root) as db: audit(db,batch,None,'cleanup_simulated',{'potentialBytes':report['potentialBytes'],'files':len(candidates),'blockers':reasons,'deletedFiles':0})
    return report


def retry_item(root,item_id):
    """Explicit recovery only; never replaces an expired/unknown upload session."""
    with connect(root) as db:
        db.execute('BEGIN IMMEDIATE')
        item=db.execute('SELECT * FROM youtube_items WHERE id=?',(item_id,)).fetchone()
        if not item or item['state']!='failed': raise ValueError('Only a failed item can be explicitly retried')
        batch=db.execute('SELECT * FROM youtube_batches WHERE id=?',(item['batch_id'],)).fetchone()
        if batch['owner']: raise ValueError('Do not reset a worker-owned delivery')
        target='processing' if item['video_id'] else ('uploading' if item['session_ref'] else 'upload_uncertain')
        db.execute('UPDATE youtube_items SET state=?,attempts=0,next_attempt=0,checked_at=NULL,evidence=NULL,error=NULL WHERE id=?',(target,item_id))
        db.execute("UPDATE youtube_batches SET state='in_progress',error=NULL WHERE id=?",(item['batch_id'],))
        audit(db,item['batch_id'],item_id,'explicit_retry',{'target':target,'newInsertAuthorized':False})
    return {'id':item_id,'state':target}


def dashboard(root):
    with connect(root) as db:
        return {'channels':[dict(r) for r in db.execute('SELECT role,channel_id,title,origin FROM youtube_channels ORDER BY role')],
                'batches':[dict(r) for r in db.execute('SELECT id,production_id,state,origin,error FROM youtube_batches ORDER BY rowid DESC')],
                'items':[dict(r) for r in db.execute('SELECT i.id,i.batch_id,i.file,i.channel_id,i.publish_at,i.state,i.video_id,i.error,b.origin FROM youtube_items i JOIN youtube_batches b ON i.batch_id=b.id ORDER BY i.rowid DESC')],
                'freedBytes':0,'cleanupMode':'simulation-only','liveDefaultEnabled':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for name in ('status','prepare','cleanup-plan','show'):
        s=sub.add_parser(name);s.add_argument('root')
        if name!='status': s.add_argument('id')
        if name=='prepare': s.add_argument('schedule_json')
    a=p.parse_args()
    if a.command=='status': out=dashboard(a.root)
    elif a.command=='prepare': out=prepare(a.root,a.id,f.read(a.schedule_json))
    elif a.command=='show':
        info=batch_info(a.root,a.id);out={'id':info['id'],'sha256':info['sha'],'state':info['state'],'plan':info['plan']}
    else: out=cleanup_simulation(a.root,a.id)
    print(json.dumps(out,ensure_ascii=False,indent=2))
