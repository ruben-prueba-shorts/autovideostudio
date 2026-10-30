"""Offline state/HTTP-contract tests. All channel/video IDs are synthetic.

No OAuth request, upload, scheduling request or deletion reaches Google.
The optional real-media integration runner separately reuses completed assets.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import factory_orchestrator as f
import youtube_factory as yt
import youtube_official as official
from orchestrator_test import report

CID='UC'+'A'*22


def completed_fixture(root,number=1):
    """Unit fixture only: opaque bytes, no assertion that these are real MP4s."""
    f.init(root);radar=report();rp=root/'report.json';f.render.atomic_json(rp,radar);f.import_report(root,rp)
    job=f.select(root,radar['id'],f'Vídeo {number}',6,3)['id'];role=f.production(root,job)['channel']
    folder=root/'deliveries'/job;folder.mkdir(parents=True)
    files={'long.mp4':b'unit long bytes','master-clean.mp4':b'unit clean bytes','shorts/short-01.mp4':b'unit short bytes',
           'thumbnail.jpg':b'unit thumbnail','script.txt':b'preserve script','prompts-numbered.txt':b'preserve prompts',
           'sources/original.wav':b'preserve original recording'}
    prep={'format':'video-factory-youtube-preparation/v1','productionId':job,'channelProfile':role,
      'videos':[{'file':n,'snippet':{'title':'Synthetic fixture '+n,'description':'Test only','tags':['test']},'status':{'privacyStatus':'private'}} for n in ('long.mp4','shorts/short-01.mp4')]}
    for name,data in files.items():
        path=folder/name;path.parent.mkdir(exist_ok=True);path.write_bytes(data)
    f.render.atomic_json(folder/'youtube-preparation.json',prep)
    inv=[{'path':p.relative_to(folder).as_posix(),'bytes':p.stat().st_size,'sha256':f.render.digest(p)} for p in folder.rglob('*') if p.is_file()]
    val={'productionId':job,'channel':role,'files':inv,'longVideoAudits':[{'passed':True}],'shortVideoAudits':[{'passed':True}],'reviewRequired':True}
    f.render.atomic_json(folder/'validation.json',val)
    receipt={'files':[{'path':p.relative_to(root).as_posix(),'sha256':f.render.digest(p)} for p in folder.rglob('*') if p.is_file()],
             'result':{'directory':str(folder),'validation':val}}
    with f.connect(root) as db:
        db.execute("UPDATE productions SET state='review',result=? WHERE id=?",(json.dumps({'directory':str(folder)}),job))
        db.execute('INSERT INTO production_stages VALUES(?,?,?)',(job,'package',json.dumps(receipt)))
    return job,folder


def schedule(now,private=False):
    return {'mode':'private' if private else 'schedule','videos':{'long.mp4':None if private else yt.utc(now+86400),
      'shorts/short-01.mp4':None if private else yt.utc(now+90000)},
      'review':{'contentApproved':True,'madeForKids':False,'containsSyntheticMedia':True,'categoryId':'22'}}


class FakeTransport:
    origin='simulation'
    def __init__(self,cid=CID):
        self.cid=cid;self.sessions={};self.resources={};self.inserts=0;self.schedules=0;self.lost=False;self.drop_schedule=False;self.processing=False
    def channel_id(self):return self.cid
    def start(self,spec,item):
        self.inserts+=1;ref='fake_session_'+str(self.inserts);vid='FAKE'+str(self.inserts).zfill(7)
        self.sessions[ref]=vid;self.resources[vid]={'id':vid,'snippet':{'channelId':self.cid,**spec['body']['snippet']},
          'status':{**spec['body']['status'],'uploadStatus':'processed'},'processingDetails':{'processingStatus':'succeeded'}}
        return ref
    def resume(self,ref,path,spec):
        if self.lost:self.lost=False;raise yt.RetryLater(1)
        return copy.deepcopy(self.resources[self.sessions[ref]])
    def get_video(self,vid):
        r=copy.deepcopy(self.resources[vid])
        if self.processing:r['processingDetails']['processingStatus']='processing';r['status']['uploadStatus']='uploaded'
        return r
    def thumbnail(self,vid,path):pass
    def schedule(self,vid,status):
        self.schedules+=1
        if not self.drop_schedule:self.resources[vid]['status'].update(status)


class YoutubeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='factory-youtube-offline-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'factory';self.now=time.time();self.job,self.folder=completed_fixture(self.root)
        yt.bind_channel(self.root,'life-ranges-es',[{'id':CID,'snippet':{'title':'SYNTHETIC TEST CHANNEL'}}],CID,'fake_read','simulation')

    def batch(self,private=False):return yt.prepare(self.root,self.job,schedule(self.now,private),'simulation',self.now)['id']
    def complete(self,transport=None):
        batch=self.batch();yt.approve_simulation(self.root,batch);transport=transport or FakeTransport()
        for i in range(6):yt.tick(self.root,batch,transport,self.now+i*61)
        return batch,transport

    def test_default_never_calls_network_and_requires_approval(self):
        b=self.batch();fake=FakeTransport()
        with self.assertRaisesRegex(ValueError,'Unapproved'):yt.tick(self.root,b,fake)
        self.assertEqual(fake.inserts,0)
        with self.assertRaisesRegex(ValueError,'Confirm the exact OAuth'):yt.prepare(self.root,self.job,schedule(self.now),'live')
        with self.assertRaisesRegex(ValueError,'Simulation'):yt.approve_live(self.root,b)

    def test_immutable_all_item_plan_and_calendar_dedup(self):
        b=self.batch();r=yt.prepare(self.root,self.job,schedule(self.now),'simulation',self.now)
        self.assertTrue(r['existing']);self.assertEqual(r['id'],b)
        with yt.connect(self.root) as db:self.assertEqual(db.execute('SELECT count(*) FROM youtube_slots').fetchone()[0],2)
        changed=schedule(self.now);changed['videos']['long.mp4']=yt.utc(self.now+95000)
        with self.assertRaisesRegex(ValueError,'immutable'):yt.prepare(self.root,self.job,changed,'simulation',self.now)

    def test_calendar_transaction_and_minimum_gap(self):
        data=schedule(self.now);data['videos']['shorts/short-01.mp4']=data['videos']['long.mp4']
        with self.assertRaisesRegex(ValueError,'Calendar conflict'):yt.prepare(self.root,self.job,data,'simulation',self.now)
        with yt.connect(self.root) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM youtube_batches').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM youtube_slots').fetchone()[0],0)

    def test_database_transaction_releases_handle_and_rolls_back(self):
        with yt.connect(self.root) as db:db.execute('SELECT 1')
        import sqlite3
        with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
        with self.assertRaises(RuntimeError):
            with yt.connect(self.root) as db:
                db.execute('INSERT INTO youtube_slots VALUES(?,?,?)',(CID,self.now,'rolled_back'))
                raise RuntimeError('rollback test')
        with yt.connect(self.root) as db:self.assertEqual(db.execute('SELECT count(*) FROM youtube_slots').fetchone()[0],0)

    def test_same_video_bytes_cannot_be_queued_twice_for_one_channel(self):
        self.batch();second,_=completed_fixture(self.root,5)
        with self.assertRaisesRegex(ValueError,'already reserved'):yt.prepare(self.root,second,schedule(self.now+10000),'simulation',self.now)

    def test_confirm_all_four_channels_no_reuse_or_silent_remapping(self):
        for i,role in enumerate(f.CHANNELS[1:],1):
            cid='UC'+str(i)*22;yt.bind_channel(self.root,role,[{'id':cid,'snippet':{'title':'Synthetic '+role}}],cid,'fake_'+str(i),'simulation')
        self.assertEqual(len(yt.dashboard(self.root)['channels']),4)
        with self.assertRaisesRegex(ValueError,'immutable'):yt.bind_channel(self.root,'life-ranges-es',[{'id':CID,'snippet':{'title':'Changed'}}],CID,'fake_read','simulation')
        with self.assertRaisesRegex(ValueError,'single channel'):yt.bind_channel(self.root,'finance-es',[],CID,'fake_read','simulation')

    def test_private_is_not_scheduled_and_cleanup_stays_blocked(self):
        b=self.batch(True);yt.approve_simulation(self.root,b);t=FakeTransport()
        for i in range(5):yt.tick(self.root,b,t,self.now+i*61)
        self.assertEqual(t.schedules,0)
        out=yt.cleanup_simulation(self.root,b,self.now+300)
        self.assertFalse(out['eligibleAfterRemoteChecks']);self.assertIn('Private upload is not confirmed public scheduling',out['blockers']);self.assertEqual(out['deletedFiles'],0)

    def test_lost_final_response_resumes_saved_session_without_second_insert(self):
        b=self.batch();yt.approve_simulation(self.root,b);t=FakeTransport();t.lost=True
        yt.tick(self.root,b,t,self.now)
        one=yt.batch_info(self.root,b)['items'][0]
        self.assertEqual(one['state'],'uploading');self.assertTrue(one['session_ref']);self.assertIsNone(one['video_id'])
        # Reopen database via a new tick, reusing the server-side resumable state.
        for i in range(1,8):yt.tick(self.root,b,t,self.now+i*61)
        self.assertEqual(t.inserts,2);self.assertEqual(yt.batch_info(self.root,b)['state'],'scheduled')

    def test_crash_before_saved_session_never_reinserts(self):
        b=self.batch();yt.approve_simulation(self.root,b);t=FakeTransport()
        with yt.connect(self.root) as db:db.execute("UPDATE youtube_items SET state='uploading' WHERE batch_id=?",(b,))
        r=yt.tick(self.root,b,t,self.now)
        self.assertTrue(all(x['state']=='upload_uncertain' for x in r['items']));self.assertEqual(t.inserts,0)

    def test_only_fresh_matching_remote_get_can_confirm_schedule(self):
        t=FakeTransport();t.drop_schedule=True;b,t=self.complete(t)
        self.assertGreater(t.schedules,0);self.assertNotEqual(yt.batch_info(self.root,b)['state'],'scheduled')
        self.assertFalse(yt.cleanup_simulation(self.root,b,self.now+360)['eligibleAfterRemoteChecks'])

    def test_processing_blocks_scheduling_and_cleanup(self):
        b=self.batch();yt.approve_simulation(self.root,b);t=FakeTransport();t.processing=True
        for i in range(5):yt.tick(self.root,b,t,self.now+i*61)
        self.assertEqual(t.schedules,0);self.assertTrue(all(i['state']=='processing' for i in yt.batch_info(self.root,b)['items']))
        self.assertFalse(yt.cleanup_simulation(self.root,b,self.now+300)['eligibleAfterRemoteChecks'])

    def test_wrong_oauth_channel_stops_before_any_transfer(self):
        b=self.batch();yt.approve_simulation(self.root,b);t=FakeTransport('UC'+'B'*22)
        with self.assertRaisesRegex(ValueError,'differs'):yt.tick(self.root,b,t,self.now)
        self.assertEqual(t.inserts,0)

    def test_schedule_past_and_timezone_absent_refused(self):
        for value in ('2020-01-01T12:00:00Z','2030-01-01T12:00:00'):
            data=schedule(self.now);data['videos']['long.mp4']=value
            with self.assertRaises(ValueError):yt.prepare(self.root,self.job,data,'simulation',self.now)

    def test_cleanup_exact_inventory_no_deletions_and_preserved_originals(self):
        b,t=self.complete();before={p:f.render.digest(p) for p in self.folder.rglob('*') if p.is_file()}
        out=yt.cleanup_simulation(self.root,b,self.now+360)
        self.assertEqual(out['deletedFiles'],0);self.assertEqual(out['freedBytes'],0);self.assertGreater(out['potentialBytes'],0)
        self.assertFalse(out['deletionImplemented']);self.assertFalse(out['eligibleAfterRemoteChecks'])
        self.assertTrue(all('/sources/' not in a['path'] and not a['path'].endswith('.txt') for a in out['files']))
        self.assertEqual(before,{p:f.render.digest(p) for p in self.folder.rglob('*') if p.is_file()})
        self.assertTrue(all(x['passed'] for x in out['checks']))

    def test_cleanup_rejects_corruption_and_stale_or_incomplete_evidence(self):
        b,t=self.complete();(self.folder/'long.mp4').write_bytes(b'changed')
        out=yt.cleanup_simulation(self.root,b,self.now+2000)
        self.assertFalse(any(a['path'].endswith('/long.mp4') for a in out['files']));self.assertTrue(out['exclusions']);self.assertFalse(out['eligibleAfterRemoteChecks'])
        self.assertTrue(any(not a['passed'] for a in out['checks']))

    def test_cleanup_excludes_hardlinks_and_other_jobs(self):
        b,t=self.complete();external=self.root/'personal.mp4';os.link(self.folder/'long.mp4',external)
        out=yt.cleanup_simulation(self.root,b,self.now+360)
        self.assertTrue(any(x['reason'].startswith('link') for x in out['exclusions']));self.assertTrue(external.exists())

    def test_one_failed_short_blocks_the_whole_cleanup(self):
        b,t=self.complete()
        with yt.connect(self.root) as db:db.execute("UPDATE youtube_items SET state='failed' WHERE file='shorts/short-01.mp4'")
        out=yt.cleanup_simulation(self.root,b,self.now+360)
        self.assertFalse(out['eligibleAfterRemoteChecks']);self.assertTrue(any('shorts/short-01.mp4' in x for x in out['blockers']))
        self.assertTrue((self.folder/'long.mp4').exists());self.assertEqual(out['freedBytes'],0)

    def test_changed_channel_or_schedule_invalidates_remote_evidence(self):
        b,t=self.complete();vid=next(iter(t.resources));t.resources[vid]['snippet']['channelId']='UC'+'B'*22
        checks=yt.refresh_verification(self.root,b,t,self.now+360);self.assertTrue(any(not x['passed'] for x in checks))
        t.resources[vid]['snippet']['channelId']=CID;t.resources[vid]['status']['publishAt']=yt.utc(self.now+200000)
        checks=yt.refresh_verification(self.root,b,t,self.now+360);self.assertTrue(any(not x['passed'] for x in checks))

    def test_untracked_personal_file_not_in_cleanup_and_explicit_retry_reuses_session(self):
        b,t=self.complete();p=self.folder/'personal.mp4';p.write_bytes(b'do not touch')
        out=yt.cleanup_simulation(self.root,b,self.now+360);self.assertNotIn(p.name,[Path(x['path']).name for x in out['files']])
        item=yt.batch_info(self.root,b)['items'][0]
        with yt.connect(self.root) as db:db.execute("UPDATE youtube_items SET state='failed',video_id=NULL WHERE id=?",(item['id'],))
        self.assertEqual(yt.retry_item(self.root,item['id'])['state'],'uploading')
        yt.tick(self.root,b,t,self.now+400);self.assertEqual(t.inserts,2);self.assertEqual(p.read_bytes(),b'do not touch')

    def test_refresh_failure_invalidates_old_good_evidence(self):
        b,t=self.complete()
        with patch.object(t,'get_video',side_effect=RuntimeError('offline')):checks=yt.refresh_verification(self.root,b,t,self.now+360)
        self.assertTrue(all(not x['passed'] for x in checks))
        self.assertTrue(all(i['checked_at'] is None for i in yt.batch_info(self.root,b)['items']))

    def test_lease_and_bounded_retries(self):
        b=self.batch();yt.approve_simulation(self.root,b);t=FakeTransport()
        with yt.connect(self.root) as db:db.execute('UPDATE youtube_batches SET owner=?,lease=? WHERE id=?',('other',self.now+1000,b))
        with self.assertRaisesRegex(ValueError,'owns'):yt.tick(self.root,b,t,self.now)
        with yt.connect(self.root) as db:db.execute('UPDATE youtube_batches SET owner=NULL,lease=NULL WHERE id=?',(b,))
        with patch.object(t,'resume',side_effect=yt.RetryLater(1)):
            for i in range(3):yt.tick(self.root,b,t,self.now+i*61)
        self.assertTrue(all(i['state']=='failed' and i['attempts']==3 for i in yt.batch_info(self.root,b)['items']))
        self.assertEqual(t.inserts,2)


class Response:
    def __init__(self,code=200,data=None,headers=None):self.status_code=code;self.data=data or {};self.headers=headers or {}
    def json(self):return self.data


class ProtocolTests(unittest.TestCase):
    def client(self,responses):
        class Session:
            def __init__(self):self.responses=list(responses);self.calls=[]
            def put(self,url,**kw):self.calls.append(('PUT',url,kw));return self.responses.pop(0)
        class Vault:
            def load(self,ref):return {'uri':'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=synthetic'}
        client=object.__new__(official.OfficialTransport);client.session=Session();client.vault=Vault();return client

    def test_lost_final_response_returns_same_video_without_new_bytes(self):
        client=self.client([Response(201,{'id':'FAKE0000001'})]);self.assertEqual(client.resume('fake',Path('not-opened'),{'bytes':20})['id'],'FAKE0000001')
        self.assertEqual(len(client.session.calls),1);self.assertEqual(client.session.calls[0][2]['headers']['Content-Range'],'bytes */20')

    def test_partial_resume_obeys_server_offset(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fake.mp4';p.write_bytes(b'A'*262144+b'FINAL')
            client=self.client([Response(308,headers={'Range':'bytes=0-262143'}),Response(201,{'id':'FAKE0000001'})])
            client.resume('fake',p,{'bytes':p.stat().st_size});sent=client.session.calls[1][2]
            self.assertEqual(sent['data'],b'FINAL');self.assertEqual(sent['headers']['Content-Range'],'bytes 262144-262148/262149')

    def test_expired_session_never_initiates_another_upload(self):
        client=self.client([Response(404)])
        with self.assertRaises(yt.AmbiguousUpload):client.resume('fake',Path('missing'),{'bytes':20})
        self.assertEqual(len(client.session.calls),1)

    def test_session_uri_allowlist_rate_limit_and_credential_storage(self):
        for uri in ('http://www.googleapis.com/upload/youtube/v3/videos','https://evil.test/upload/youtube/v3/videos','https://www.googleapis.com.evil.test/upload/youtube/x'):
            with self.assertRaises(ValueError):official.OfficialTransport.validate_uri(uri)
        with self.assertRaises(yt.RetryLater):official.checked_response(Response(429,headers={'Retry-After':'120'}))
        if os.name!='nt':
            with self.assertRaisesRegex(ValueError,'no plaintext'):official.dpapi(b'not-a-real-token')


if __name__=='__main__':unittest.main()
