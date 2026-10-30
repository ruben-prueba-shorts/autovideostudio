// Curated image selection -> a new numbered folder with tamper-evident bindings.
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const {validateJob}=require('../automation/import-job.js');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
async function bind(jobPath,selectionPath,target){
 const job=validateJob(JSON.parse(await fs.readFile(jobPath,'utf8'))),source=path.dirname(await fs.realpath(selectionPath));
 const selected=JSON.parse(await fs.readFile(selectionPath,'utf8'));
 if(selected.format!=='video-factory-selection/v1'||selected.jobId!==job.id||selected.reviewed!==true||selected.scenes?.length!==job.scenes.length)throw Error('Select and review one image for each scene before binding.');
 const prepared=[],scenes=[];let totalBytes=0;
 for(let i=0;i<job.scenes.length;i++){
  const choice=selected.scenes[i],scene=job.scenes[i];
  if(choice.sceneIndex!==i+1||choice.prompt!==scene.imagePrompt)throw Error('Selection prompt/scene differs from the job.');
  const file=await fs.realpath(path.resolve(source,choice.path));
  if(!file.startsWith(source+path.sep))throw Error('Selection must stay inside its project asset directory.');
  const ext=path.extname(file).toLowerCase();if(!['.png','.jpg','.jpeg','.webp'].includes(ext))throw Error('Use static PNG/JPEG/WebP images.');
  const stat=await fs.stat(file);if(!stat.isFile()||!stat.size||stat.size>30*1024*1024)throw Error('Image size outside import limits.');
  totalBytes+=stat.size;if(totalBytes>300*1024*1024)throw Error('Batch exceeds 300 MiB.');
  const bytes=await fs.readFile(file),sha=hash(bytes);if(sha!==choice.sha256)throw Error('Selected image hash changed.');
  const original=/^(\d+)[.)-]\s*/.exec(scene.imagePrompt);
  if(!/^\d{1,6}$/.test(String(choice.sourcePromptId))||original&&Number(original[1])!==Number(choice.sourcePromptId))throw Error('Original prompt number differs from the selected scene.');
  const name=String(i+1).padStart(4,'0')+ext;
  scenes.push({sceneIndex:i+1,promptSha256:hash(Buffer.from(scene.imagePrompt)),narrationSha256:hash(Buffer.from(scene.narration)),sourcePromptId:String(choice.sourcePromptId),image:{name,sha256:sha}});
  prepared.push({name,bytes});
 }
 if(prepared.reduce((n,p)=>n+p.bytes.length,0)>300*1024*1024)throw Error('Batch exceeds 300 MiB.');
 await fs.mkdir(target); // New directory only; originals are never modified.
 for(const item of prepared)await fs.writeFile(path.join(target,item.name),item.bytes,{flag:'wx'});
 const bindings={format:'video-factory-bindings/v1',jobId:job.id,scenes};
 await fs.writeFile(path.join(target,'bindings.json'),JSON.stringify(bindings,null,2),{flag:'wx'});
 return bindings;
}
if(require.main===module){
 const [job,selection,target]=process.argv.slice(2);
 if(!target){console.error('Usage: node tools/bind-assets.cjs JOB.json SELECTION.json NEW_FOLDER');process.exitCode=2;}
 else bind(job,selection,target).then(b=>console.log(JSON.stringify({jobId:b.jobId,count:b.scenes.length,folder:target}))).catch(e=>{console.error(e.message);process.exitCode=1;});
}
module.exports={bind};
