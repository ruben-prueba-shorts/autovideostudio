#!/usr/bin/env python3
"""Reuse the completed Flow/Mako sample in one connected orchestrator job.

The ten-entry catalogue is explicitly synthetic, not a new viral report.
No image, voice, API inference or browser generation request is made.
"""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import factory_orchestrator as o
from orchestrator_test import report

p=argparse.ArgumentParser(description=__doc__);p.add_argument('assets');p.add_argument('workspace');a=p.parse_args()
root=Path(a.workspace).resolve();source=Path(a.assets).resolve();o.init(root)
inbox=root/'inbox'/'existing-smoke';inbox.mkdir(parents=True,exist_ok=True)
job=o.contract('job',o.read(o.REPO/'automation/real-smoke-job.json'))['job']
r=report();r['id']='existing_smoke_transport_001';r['ideas'][2].update(channel='life-ranges-es',title='Reutilización de la prueba real de fútbol',
 originalAngle='Transport validation of an already completed video; not new viral research',potentialReason='Test-only catalogue; no measured viral claim')
report_path=root/'inbox'/'test-report.json';o.render.atomic_json(report_path,r);o.import_report(root,report_path)
selected=o.select(root,r['id'],'Haz el vídeo 3',25.8,3);id=selected['id']
metadata=inbox/'metadata.json';o.render.atomic_json(metadata,{'title':'Tu vida en la élite del fútbol — prueba técnica',
 'description':'Integración con imágenes existentes y una narración ya generada. Pendiente de revisión.','tags':['fútbol','prueba técnica']})
script=inbox/'job.json';o.render.atomic_json(script,job)
entries=[('master','master-h264.mp4'),('handoff','handoff.json'),('presentation','video-real-horizontal.mp4'),('audio','mako-gemini-3.8.wav'),
 ('project','captioned.avfproject'),('bindings','numbered/bindings.json')]+[('image',f'numbered/{i:04}.jpg') for i in range(1,4)]
artifacts=[]
for role,name in entries:
 target=inbox/name;o.copy_asset(source/name,target);artifacts.append({'role':role,'path':name,'sha256':o.render.digest(target)})
ready=inbox/'assets.ready.json';o.render.atomic_json(ready,{'format':'video-factory-ready/v1','mode':'existing','material':'real','scriptSha256':o.fingerprint(job),'artifacts':artifacts})
# Envelope is written last, after every asset is complete and hashed.
o.render.atomic_json(inbox/'production.ready.json',{'format':'video-factory-inbox/v1','productionId':id,
 **{k:{'path':f.name,'sha256':o.render.digest(f)} for k,f in [('script',script),('metadata',metadata),('media',ready)]}})
scan=o.scan_inbox(root)
if not scan or not all(x['accepted'] for x in scan):raise ValueError('Inbox rejected: '+str(scan))
started=time.monotonic();result=o.run_once(root,id)
if result is None:result=json.loads(o.production(root,id)['result'])
result.update(elapsedSeconds=round(time.monotonic()-started,3),reusedExistingNarration=True,newGenerations=0,inbox=scan)
o.render.atomic_json(root/'smoke-result.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
