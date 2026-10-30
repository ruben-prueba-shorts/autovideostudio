"""Repair and interrupt an isolated copy of a completed synthetic render."""
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import local_factory as factory

manifest, source, target = map(Path, sys.argv[1:4])
job = json.loads(manifest.read_text())
if job['material'] != 'synthetic':
    raise ValueError('This destructive test accepts only synthetic render copies')
destination = target/job['id']/source.name
destination.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(source, destination)  # Fails if target already exists.
part = destination/f'{max(1,len(job["scenes"])//2):04}'/'segment.mp4'
part.write_bytes(b'controlled corruption of a test copy')
interrupted = False
try:
    factory.render(manifest, target, burn=True, stop_after=1)
except RuntimeError as error:
    if 'Controlled interruption' not in str(error):
        raise
    interrupted = True
assert interrupted
result = factory.render(manifest, target, burn=True)
assert result['reusedSegments'] == len(job['scenes']) and result['renderedSegments'] == 0
result.update(controlledCorruptionRepaired=True, interruptedAfterCheckpoint=True, passed=True,
              matchesOriginalSha256=factory.digest(result['master']) == factory.digest(source/'master.mp4'))
factory.atomic_json(target/'recovery-result.json', result)
print(json.dumps(result), flush=True)
