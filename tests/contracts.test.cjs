const {test}=require('node:test');
const assert=require('node:assert/strict');
const media=require('../automation/media-contract.js');
const jobs=require('../automation/import-job.js');
const example=require('../automation/example-job.json');
test('accept all four channels and normalize a scene to one paragraph',()=>{
  for(const niche of ['finance','life-ranges'])for(const language of ['es','en']) {
    const job=jobs.validateJob({...example,niche,language,scenes:[{narration:'One.\nTwo.',imagePrompt:'1. A\nscene'}]});
    assert.equal(job.scenes.length,1);assert.equal(job.scenes[0].narration,'One. Two.');assert.equal(job.scenes[0].imagePrompt,'A scene');
  }
});
test('invalid jobs fail before application',()=>{
  for(const invalid of [{format:'unknown'},{language:'fr'},{niche:'unknown'},{scenes:[]},{scenes:[{narration:'test',imagePrompt:'1.'}]},{scenes:Array(301).fill(example.scenes[0])}])
    assert.throws(()=>jobs.validateJob({...example,...invalid}));
});
test('numbered images are sorted numerically, not by selection order',()=>{
  const files=[10,1,12,3,2,11,4,6,5,9,8,7].map(n=>({name:String(n).padStart(4,'0')+'.png'}));
  assert.deepEqual(media.orderImages(files,12).map(f=>f.name),Array.from({length:12},(_,i)=>String(i+1).padStart(4,'0')+'.png'));
});
test('missing, duplicated, extra, unnumbered images are rejected',()=>{
  for(const names of [['1.png'],['1.png','1 (1).png','2.png'],['1.png','2.png','3.png'],['image.png','2.png'],['0.png','2.png']])
    assert.throws(()=>media.orderImages(names.map(name=>({name})),2));
  assert.equal(media.orderImages(['2.webp','notes.txt','1.jpg'].map(name=>({name})),2)[0].name,'1.jpg');
});
const handoff={format:media.FORMAT,video:{name:'master.mp4',size:100,duration:10,sha256:'a'.repeat(64)},language:'es',subtitlesBurned:false,cues:[{start:0,end:2,text:'Hola'}],clips:[{start:0,end:5,title:'Clip'}]};
test('handoff keeps timing and rejects incompatible or invalid payloads',()=>{
  assert.equal(media.validateHandoff(handoff).cues[0].text,'Hola');
  for(const change of [{format:'bad'},{language:'fr'},{subtitlesBurned:undefined},{video:{...handoff.video,sha256:'bad'}},{clips:[{start:0,end:11,title:'bad'}]},{cues:[{start:-1,end:2,text:'bad'}]}])
    assert.throws(()=>media.validateHandoff({...handoff,...change}));
});
