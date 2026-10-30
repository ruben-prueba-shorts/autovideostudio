// Normalize an existing render to H.264/AAC, then audit before exposing output.
// Offline, no generation, no overwrite, no upload and no automatic retries.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const [inputArg,outputArg,secondsArg,orientation]=process.argv.slice(2);
const expected=Number(secondsArg);
if(!inputArg||!outputArg||!Number.isFinite(expected)||expected<=0||!['horizontal','vertical'].includes(orientation)){
 console.error('Usage: node tools/finalize-mp4.cjs INPUT.mp4 NEW_OUTPUT.mp4 EXPECTED_SECONDS horizontal|vertical');process.exit(2);
}
const input=path.resolve(inputArg),output=path.resolve(outputArg),receipt=output+'.audit.json',temporary=output+'.'+process.pid+'.part.mp4';
function hash(file){const digest=crypto.createHash('sha256'),fd=fs.openSync(file,'r'),buffer=Buffer.alloc(1024*1024);try{let length;while((length=fs.readSync(fd,buffer,0,buffer.length,null))>0)digest.update(buffer.subarray(0,length));return digest.digest('hex');}finally{fs.closeSync(fd);}}
function run(exe,args){const r=spawnSync(exe,args,{encoding:'utf8',maxBuffer:8*1024*1024});if(r.error)throw r.error;if(r.status!==0)throw Error(r.stderr||r.stdout||exe+' failed');return r.stdout;}
let ownsTemporary=false;
try{
 if(input===output||!fs.statSync(input).isFile()||fs.existsSync(output)||fs.existsSync(receipt)||fs.existsSync(temporary))throw Error('Input must exist; output and receipt must be new files.');
 const sourceSha256=hash(input),started=Date.now();
 // The temporary output is owned by this invocation; -n prevents overwriting it.
 ownsTemporary=true;
 run('ffmpeg',['-v','error','-n','-i',input,'-map','0:v:0','-map','0:a:0','-vf','fps=30,scale=in_range=auto:out_range=tv','-c:v','libx264','-pix_fmt','yuv420p','-color_range','tv','-crf','18','-preset','medium','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',temporary]);
 const audit=JSON.parse(run(process.execPath,[path.join(__dirname,'audit-mp4.cjs'),temporary,String(expected),orientation]));
 if(hash(input)!==sourceSha256)throw Error('Source changed during finalization.');
 const sha256=hash(temporary);
 // Hard-link with exclusive creation avoids replacing a concurrently created output.
 fs.linkSync(temporary,output);fs.unlinkSync(temporary);ownsTemporary=false;audit.file=output;
 const result={format:'video-factory-finalized-mp4/v1',source:{name:path.basename(input),sha256:sourceSha256},output:{name:path.basename(output),sha256,bytes:fs.statSync(output).size},elapsedSeconds:(Date.now()-started)/1000,audit};
 fs.writeFileSync(receipt,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(result,null,2));
}catch(e){if(ownsTemporary&&fs.existsSync(temporary))fs.unlinkSync(temporary);console.error(e.message);process.exitCode=1;}
