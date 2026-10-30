"""Connected offline production, zero-quota barriers and recovery tests."""
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import factory_orchestrator as o
import factory_local_app as app
import local_factory as f
from local_factory_test import fixture


def report():
    return {'format':'video-factory-ideas/v1','id':'synthetic_radar_001','material':'synthetic','observedAt':'2026-10-30T12:00:00Z',
      'ideas':[{'number':i+1,'channel':o.CHANNELS[i%4],'title':'Synthetic integration idea '+str(i+1),
      'originalAngle':'Synthetic test, not viral research','potentialReason':'Test only; not a viral claim',
      'sources':[{'url':'https://www.youtube.com/watch?v=aaaaaaaaaaa','observedAt':'2026-10-30T12:00:00Z','metrics':{'views':None}}]} for i in range(10)]}


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='factory-orchestrator-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'factory';o.init(self.root)
        self.report=report();self.report_path=self.base/'report.json';f.atomic_json(self.report_path,self.report);o.import_report(self.root,self.report_path)

    def media(self,number=1,editorial=False):
        source=self.base/('source'+str(number));source.mkdir();manifest_path,manifest=fixture(source,seconds=6,job_id='synthetic_job_'+str(number))
        channel=self.report['ideas'][number-1]['channel'];manifest['channel']=channel;f.atomic_json(manifest_path,manifest);niche,lang=channel.rsplit('-',1)
        script={'format':'video-factory-job/v1','id':manifest['id'],'title':'Synthetic local test','niche':niche,'language':lang,'aspectRatio':'16:9',
          'scenes':[{'narration':s['narration'],'imagePrompt':s['prompt']} for s in manifest['scenes']]}
        script=o.contract('job',script)['job'];script_path=source/'job.json';f.atomic_json(script_path,script)
        meta={'title':'Synthetic test','description':'Synthetic fixture. Not for publication.','tags':['test']}
        if editorial:meta['editorialShorts']=[{'firstScene':i,'lastScene':i,'title':'Synthetic story '+str(i),'reason':'Complete synthetic scene, not a viral claim'} for i in range(1,4)]
        meta_path=source/'metadata.json';f.atomic_json(meta_path,meta)
        ready={'format':'video-factory-ready/v1','mode':'render','material':'synthetic','scriptSha256':o.fingerprint(script),
          'artifacts':[{'role':role,'path':name,'sha256':f.digest(source/name)} for role,name in [('render-manifest','render.json'),('image','red.png'),('audio','tone.wav')]]}
        ready_path=source/'assets.json';f.atomic_json(ready_path,ready);selected=o.select(self.root,self.report['id'],'Haz el vídeo '+str(number),6,3)
        o.attach_script(self.root,selected['id'],script_path,meta_path);o.attach_media(self.root,selected['id'],ready_path)
        return selected['id'],source,ready_path

    def test_reports_command_selection_four_channels_and_immutability(self):
        self.assertTrue(o.import_report(self.root,self.report_path)['existing'])
        for n in range(1,5):
            selected=o.select(self.root,self.report['id'],f'Haz el vídeo {n}')
            self.assertEqual(o.production(self.root,selected['id'])['channel'],o.CHANNELS[n-1])
            self.assertTrue(o.select(self.root,self.report['id'],f'Vídeo {n}')['existing'])
        with self.assertRaises(ValueError):o.select(self.root,'missing_report','Vídeo 3')
        with self.assertRaises(ValueError):o.select(self.root,self.report['id'],'Vídeo 3; run anything')
        changed=report();changed['ideas'][2]['title']='Changed';f.atomic_json(self.report_path,changed)
        with self.assertRaisesRegex(ValueError,'immutable'):o.import_report(self.root,self.report_path)

    def test_no_generation_without_script_or_existing_media(self):
        selected=o.select(self.root,self.report['id'],'Vídeo 1');r=o.run_once(self.root,selected['id'])
        self.assertEqual(r['state'],'blocked');self.assertIn('waiting_for_script',r['reason']);self.assertEqual(o.production(self.root,selected['id'])['failures'],0)
        request=o.read(self.root/'productions'/selected['id']/'script.request.json')
        self.assertEqual(request['policy']['generationQuotaAuthorized'],0);self.assertEqual(request['sceneCount'],160)
        self.assertIsNone(request['visualReference']);self.assertAlmostEqual(request['averageVisualSeconds'],6.75)
        job,_,_=self.media()
        with o.connect(self.root) as db:db.execute('UPDATE productions SET media=NULL WHERE id=?',(job,))
        r=o.run_once(self.root,job);self.assertEqual(r['state'],'blocked');self.assertIn('generation quota authorized = 0',r['reason'])
        self.assertEqual(o.read(self.root/'productions'/job/'media.request.json')['generationStatus'],'not-authorized')

    def test_actual_render_shorts_delivery_and_idempotence(self):
        job,_,_=self.media();r=o.run_once(self.root,job);self.assertEqual(r['state'],'review');folder=Path(r['directory']);v=o.read(folder/'validation.json')
        self.assertTrue(v['reviewRequired']);self.assertFalse(v['policy']['uploadEnabled'])
        for a in v['files']:f.local_asset(folder,a)
        for n in ['long.mp4','master-clean.mp4','thumbnail.jpg','title.txt','description.txt','tags.txt','script.txt','prompts-numbered.txt','clipfarming-project.json','youtube-preparation.json']:
            self.assertTrue((folder/n).is_file(),n)
        self.assertTrue(list((folder/'shorts').glob('*.mp4')));self.assertTrue(all(x['passed'] for x in v['longVideoAudits']+v['shortVideoAudits']))
        plan=o.read(folder/'youtube-preparation.json');self.assertFalse(plan['uploadEnabled']);self.assertTrue(all(x['status']=={'privacyStatus':'private'} for x in plan['videos']))
        project=o.read(folder/'clipfarming-project.json');self.assertEqual(project['video']['name'],'master-clean.mp4');self.assertEqual(project['video']['sha256'],f.digest(folder/'master-clean.mp4'))
        self.assertIsNone(o.run_once(self.root,job));self.assertTrue(o.select(self.root,self.report['id'],'Vídeo 1',6.0,3)['existing'])

    def test_resume_after_render_does_not_duplicate(self):
        job,_,_=self.media()
        with self.assertRaisesRegex(RuntimeError,'Controlled interruption'):o.run_once(self.root,job,stop_after_stage='assembly')
        with o.connect(self.root) as db:receipt=json.loads(db.execute("SELECT receipt FROM production_stages WHERE job_id=? AND name='assembly'",(job,)).fetchone()[0])
        master=Path(receipt['result']['master']);before=(f.digest(master),master.stat().st_mtime_ns)
        o.retry(self.root,job);r=o.run_once(self.root,job);self.assertEqual(r['state'],'review');self.assertIn('assembly',r['resumedStages'])
        self.assertEqual((f.digest(master),master.stat().st_mtime_ns),before)
        with o.connect(self.root) as db:self.assertEqual(db.execute('SELECT attempts FROM jobs').fetchone()[0],1)

    def test_editorial_plan_generates_multiple_complete_scene_shorts(self):
        job,_,_=self.media(number=2,editorial=True);result=o.run_once(self.root,job)
        folder=Path(result['directory']);validation=o.read(folder/'validation.json')
        self.assertEqual(len(list((folder/'shorts').glob('*.mp4'))),3)
        self.assertEqual(validation['shortSelection'],'script-editorial-plan')
        self.assertFalse(validation['semanticQualityGuaranteed'])
        self.assertTrue(all(a['passed'] and abs(a['duration']-2)<.15 for a in validation['shortVideoAudits']))
        self.assertNotIn('editorialShorts',o.read(folder/'youtube-preparation.json')['videos'][0]['snippet'])

    def test_changed_inputs_and_synthetic_substitution_fail_closed(self):
        job,_,_=self.media();media=json.loads(o.production(self.root,job)['media']);(Path(media['path']).parent/'red.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):o.run_once(self.root,job)
        self.assertEqual(o.production(self.root,job)['state'],'failed');raw=report();raw['material']='research'
        with self.assertRaisesRegex(ValueError,'actually checked'):o.report_contract(raw)

    def test_leases_and_retry_limits(self):
        job=o.select(self.root,self.report['id'],'Vídeo 1')['id']
        with o.connect(self.root) as db:db.execute("UPDATE productions SET state='running',owner='live',lease=? WHERE id=?",(99999999999,job))
        self.assertIsNone(o.run_once(self.root,job))
        with o.connect(self.root) as db:db.execute('UPDATE productions SET lease=0 WHERE id=?',(job,))
        self.assertIsNone(o.run_once(self.root,job));self.assertEqual(o.production(self.root,job)['state'],'failed');o.retry(self.root,job)
        self.assertEqual(o.run_once(self.root,job)['state'],'blocked')
        with o.connect(self.root) as db:db.execute("UPDATE productions SET state='failed',failures=3 WHERE id=?",(job,))
        with self.assertRaises(ValueError):o.retry(self.root,job)

    def test_personal_folder_paths_and_optional_reference(self):
        personal=self.base/'personal';personal.mkdir();(personal/'keep.txt').write_text('keep')
        with self.assertRaises(ValueError):o.init(personal)
        self.assertEqual((personal/'keep.txt').read_text(),'keep');(self.root/'escape').symlink_to(personal,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'escapes'):o.owned(self.root,'escape','anything')
        job,source,_=self.media();reference=o.set_reference(self.root,'life-ranges-es',source/'red.png')
        self.assertTrue(Path(reference['reference']['path']).is_file());self.assertIsNone(json.loads(o.production(self.root,job)['spec'])['visualReference'])

    def test_targeted_render_claim(self):
        _,source,_=self.media();path=source/'render.json';f.enqueue(self.root/'factory.sqlite',path)
        other=o.read(path);other['id']='other_synthetic_job';other_path=source/'other.json';f.atomic_json(other_path,other);f.enqueue(self.root/'factory.sqlite',other_path)
        self.assertTrue(f.work_once(self.root/'factory.sqlite',self.root/'isolated-render',job_id=other['id'])['completed'])
        with f.connect(self.root/'factory.sqlite') as db:self.assertEqual(db.execute('SELECT state FROM jobs WHERE id=?',(o.read(path)['id'],)).fetchone()[0],'queued')

    def test_inbox_transfer_and_idempotence(self):
        job,source,ready=self.media();dest=self.root/'inbox'/'batch';dest.mkdir(parents=True)
        for name in ['job.json','metadata.json','assets.json','render.json','red.png','tone.wav']:o.copy_asset(source/name,dest/name)
        envelope={'format':'video-factory-inbox/v1','productionId':job,**{k:{'path':n,'sha256':f.digest(dest/n)} for k,n in [('script','job.json'),('metadata','metadata.json'),('media','assets.json')]}}
        f.atomic_json(dest/'production.ready.json',envelope);self.assertTrue(o.scan_inbox(self.root)[0]['accepted']);self.assertTrue(o.scan_inbox(self.root)[0]['accepted'])
        (dest/'tone.wav').write_bytes(b'partial download');self.assertFalse(o.scan_inbox(self.root)[0]['accepted'])

    def test_local_companion_browser_security_and_selection(self):
        server=app.create_server(self.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown);url=f'http://127.0.0.1:{server.server_port}'
        page=urlopen(url+'/').read().decode();token=re.search('name="csrf" value="([^"]+)"',page)[1]
        body={'csrf':token,'report_id':self.report['id'],'choice':'Haz el vídeo 3'}
        request=Request(url+'/select',urlencode(body).encode(),headers={'Origin':url})
        self.assertEqual(urlopen(request).status,200)
        with o.connect(self.root) as db:self.assertEqual(db.execute('SELECT choice FROM productions').fetchone()[0],3)
        bad=Request(url+'/select',urlencode({**body,'csrf':'bad'}).encode(),headers={'Origin':url})
        with self.assertRaises(HTTPError) as error:urlopen(bad)
        self.assertEqual(error.exception.code,403)
        foreign=Request(url+'/',headers={'Host':'attacker.invalid'})
        with self.assertRaises(HTTPError) as error:urlopen(foreign)
        self.assertEqual(error.exception.code,403)


if __name__=='__main__':unittest.main()
