#!/usr/bin/env python3
"""Extend the existing real delivery into a SIMULATED YouTube lifecycle.

No rerender, generation, OAuth, real upload or deletion. Uses synthetic channel
and video IDs; content-review choices here are simulated, not user approval.
"""
import argparse
import json
from pathlib import Path
import sqlite3
from contextlib import closing
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import factory_orchestrator as f
import youtube_factory as yt
from youtube_factory_test import FakeTransport,CID,schedule

p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('production_id');a=p.parse_args()
root=Path(a.root).resolve();job,path,v,_=yt.delivery(root,a.production_id)
before={str(p):[f.render.digest(p),p.stat().st_mtime_ns] for p in path.rglob('*') if p.is_file()}
backup=root/'before-youtube-extension.sqlite'
if not backup.exists():
    with closing(sqlite3.connect(root/'factory.sqlite')) as source,closing(sqlite3.connect(backup)) as destination:source.backup(destination)
yt.bind_channel(root,job['channel'],[{'id':CID,'snippet':{'title':'SIMULATION — not a user channel'}}],CID,'simulation_only','simulation')
now=time.time();data=schedule(now)
expected=f.read(path/'youtube-preparation.json')['videos']
data['videos']={item['file']:yt.utc(now+86400+i*3600) for i,item in enumerate(expected)}
with yt.connect(root) as db:prior=db.execute('SELECT id FROM youtube_batches WHERE production_id=?',(a.production_id,)).fetchone()
batch=prior['id'] if prior else yt.prepare(root,a.production_id,data,'simulation',now)['id']
yt.approve_simulation(root,batch);transport=FakeTransport()
# Persist the simulated server separately so a new client process can recover.
server_path=root/'youtube-synthetic-server.json'
if server_path.exists():
    saved=f.read(server_path)
    transport.sessions=saved['sessions'];transport.resources=saved['resources'];transport.inserts=saved['inserts']
else:
    # An older fixture run may already have saved a local session reference.
    # Reconstitute that TEST server only; never infer a real YouTube upload ID.
    existing=yt.batch_info(root,batch)
    for item,spec in zip(existing['items'],existing['plan']['videos']):
        if not item['session_ref']:continue
        ref=item['session_ref']
        if not ref.startswith('fake_session_'):raise ValueError('Not a synthetic session')
        n=int(ref.removeprefix('fake_session_'));vid='FAKE'+str(n).zfill(7)
        transport.sessions[ref]=vid;transport.inserts=max(transport.inserts,n)
        transport.resources[vid]=json.loads(item['evidence']) if item['evidence'] else {'id':vid,'snippet':{'channelId':CID,**spec['body']['snippet']},
          'status':{**spec['body']['status'],'uploadStatus':'processed'},'processingDetails':{'processingStatus':'succeeded'}}
transport.lost=True
def persist_server():f.render.atomic_json(server_path,{'sessions':transport.sessions,'resources':transport.resources,'inserts':transport.inserts})
for i in range(8):
    if yt.batch_info(root,batch)['state']=='scheduled':break
    try:yt.tick(root,batch,transport,now+i*61)
    finally:persist_server()
info=yt.batch_info(root,batch)
if info['state']!='scheduled':raise ValueError('Simulated lifecycle did not complete: '+str([x['state'] for x in info['items']]))
yt.refresh_verification(root,batch,transport,now+490)
cleanup=yt.cleanup_simulation(root,batch,now+490)
after={str(p):[f.render.digest(p),p.stat().st_mtime_ns] for p in path.rglob('*') if p.is_file()}
if before!=after:raise ValueError('Existing real delivery changed')
result={'format':'video-factory-youtube-integration-result/v1','date':'2026-10-30','media':'existing Flow/Mako real sample',
  'youtubeOrigin':'simulation','contentReviewWasSimulated':True,'userChannelsConnected':0,'oauthRequests':0,'realUploads':0,
  'newGenerations':0,'rerenders':0,'syntheticVideoItems':len(info['items']),'state':info['state'],'lostFinalResponseRecovery':True,
  'resumableSessionsCreated':transport.inserts,'expectedSessions':len(info['items']),'sourceHashesAndMtimesPreserved':True,
  'cleanup':{'dryRun':True,'eligibleAfterRemoteChecks':cleanup['eligibleAfterRemoteChecks'],'potentialBytes':cleanup['potentialBytes'],
    'candidateFiles':len(cleanup['files']),'deletedFiles':cleanup['deletedFiles'],'freedBytes':cleanup['freedBytes'],'blockers':cleanup['blockers']},
  'userWindowsTested':False,'youtubeLiveTested':False}
f.render.atomic_json(root/'youtube-integration-result.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
with yt.connect(root) as db:db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
