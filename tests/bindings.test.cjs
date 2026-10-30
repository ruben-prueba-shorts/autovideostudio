const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const media=require('../automation/media-contract.js'),{bind}=require('../tools/bind-assets.cjs');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
test('binds reviewed original prompt IDs, validates bytes and rejects changed narration',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'autovideo-binding-'));
 try{
  const bytes=Buffer.from('test bytes; image decoding is tested in Chromium'),image=path.join(root,'original.png');await fs.writeFile(image,bytes);
  const job={format:'video-factory-job/v1',id:'bind_001',title:'Binding test',niche:'life-ranges',language:'es',aspectRatio:'16:9',scenes:[{narration:'Exact narration',imagePrompt:'102- Exact original prompt'}]};
  const choice={format:'video-factory-selection/v1',jobId:job.id,reviewed:true,scenes:[{sceneIndex:1,path:'original.png',sha256:hash(bytes),prompt:job.scenes[0].imagePrompt,sourcePromptId:'102'}]};
  const jp=path.join(root,'job.json'),sp=path.join(root,'selection.json'),out=path.join(root,'numbered');await fs.writeFile(jp,JSON.stringify(job));await fs.writeFile(sp,JSON.stringify(choice));
  const bindings=await bind(jp,sp,out),files=[new File([bytes],'0001.png'),new File([JSON.stringify(bindings)],'bindings.json')];
  const verified=await media.verifyBindings(files,job);assert.equal(verified.scenes[0].sourcePromptId,'102');assert.match(verified.sha256,/^[a-f0-9]{64}$/);
  await assert.rejects(media.verifyBindings([new File(['changed'],'0001.png'),files[1]],job),/no coinciden/);
  const changed=structuredClone(job);changed.scenes[0].narration='Changed narration';await assert.rejects(media.verifyBindings(files,changed),/no coinciden/);
  await assert.rejects(bind(jp,sp,out),/EEXIST/);
  choice.scenes[0].sourcePromptId='110';await fs.writeFile(sp,JSON.stringify(choice));await assert.rejects(bind(jp,sp,path.join(root,'wrong')),/Original prompt number/);
  assert.equal(await fs.readFile(image,'utf8'),bytes.toString());
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
