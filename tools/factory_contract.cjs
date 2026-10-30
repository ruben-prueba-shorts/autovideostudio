// Reuse existing editor contracts. No network or generation.
const fs=require('node:fs'),path=require('node:path');
const jobs=require('../automation/import-job.js'),media=require('../automation/media-contract.js');
let input='';process.stdin.on('data',b=>{input+=b;if(input.length>30*1024*1024)throw Error('Contract input too large');});
process.stdin.on('end',async()=>{try{
 const p=JSON.parse(input);let result;
 if(p.command==='job'){const job=jobs.validateJob(p.value);result={job,prompts:jobs.promptList(job)};}
 else if(p.command==='handoff')result=media.validateHandoff(p.value);
 else if(p.command==='bindings'){
  const files=p.files.map(f=>new File([fs.readFileSync(f.path)],path.basename(f.path)));
  result=await media.verifyBindings(files,p.job);if(!result)throw Error('Bindings required');
 }else throw Error('Unsupported offline contract');
 process.stdout.write(JSON.stringify(result));
}catch(e){process.stderr.write(e.message);process.exitCode=1;}});
