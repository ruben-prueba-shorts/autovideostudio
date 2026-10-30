#!/usr/bin/env python3
"""Run on the chosen PC: synthetic delivery + interrupted assembly recovery.

Reuses the existing renderer test fixture, never Flow/AI Studio. Keeps proof in
the dedicated factory folder; does not delete anything or contact YouTube.
"""
import argparse
import json
from pathlib import Path
import platform
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from local_factory_test import fixture
from orchestrator_test import report
import factory_orchestrator as f
from factory_local_app import doctor


def run(root):
    root=Path(root).resolve(); f.init(root); health=doctor()
    if not all(health['requirements'].values()) or not health['clipFarmingCheckout']:
        raise ValueError('Install the missing dependencies/checkouts before the local test')
    base=f.owned(root,'diagnostics','smoke_'+uuid.uuid4().hex);base.mkdir(parents=True)
    work=base/'factory';f.init(work);source=base/'synthetic-source';source.mkdir()
    manifest_path,manifest=fixture(source,seconds=6,job_id='windows_synthetic_001')
    radar=report();path=base/'test-report.json';f.render.atomic_json(path,radar);f.import_report(work,path)
    selected=f.select(work,radar['id'],'Haz el vídeo 1',6,3);job=selected['id']
    script=f.contract('job',{'format':'video-factory-job/v1','id':manifest['id'],'title':'Prueba local sintética',
      'niche':'life-ranges','language':'es','aspectRatio':'16:9',
      'scenes':[{'narration':s['narration'],'imagePrompt':s['prompt']} for s in manifest['scenes']]})['job']
    script_path=base/'job.json';meta_path=base/'metadata.json';f.render.atomic_json(script_path,script)
    f.render.atomic_json(meta_path,{'title':'Prueba sintética del ordenador','description':'Tonos y colores, no narración real. No publicar.','tags':['prueba']})
    f.attach_script(work,job,script_path,meta_path)
    ready=source/'ready.json';f.render.atomic_json(ready,{'format':'video-factory-ready/v1','mode':'render','material':'synthetic','scriptSha256':f.fingerprint(script),
      'artifacts':[{'role':role,'path':name,'sha256':f.render.digest(source/name)} for role,name in [('render-manifest','render.json'),('image','red.png'),('audio','tone.wav')]]})
    f.attach_media(work,job,ready)
    try: f.run_once(work,job,stop_after_stage='assembly')
    except RuntimeError as error:
        if 'Controlled interruption' not in str(error): raise
    else: raise ValueError('Controlled interruption did not run')
    with f.connect(work) as db: receipt=json.loads(db.execute("SELECT receipt FROM production_stages WHERE job_id=? AND name='assembly'",(job,)).fetchone()[0])
    master=Path(receipt['result']['master']);before=(f.render.digest(master),master.stat().st_mtime_ns)
    f.retry(work,job);result=f.run_once(work,job)
    if before!=(f.render.digest(master),master.stat().st_mtime_ns): raise ValueError('Recovery unnecessarily changed the completed master')
    validation=f.read(Path(result['directory'])/'validation.json')
    if not all(x['passed'] for x in validation['longVideoAudits']+validation['shortVideoAudits']): raise ValueError('Output audit failed')
    proof={'format':'video-factory-pc-smoke/v1','passed':True,'platform':platform.system(),
      'userPcFolderTested':platform.system()=='Windows','health':health,'delivery':result['directory'],
      'masterHashAndMtimePreserved':True,'state':result['state'],'material':'synthetic','newGenerationQuota':0,
      'uploadRequests':0,'deletedFiles':0,'bytesWritten':sum(p.stat().st_size for p in base.rglob('*') if p.is_file())}
    f.render.atomic_json(base/'pc-proof.json',proof);return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');a=parser.parse_args()
    print(json.dumps(run(a.root),ensure_ascii=False,indent=2))
