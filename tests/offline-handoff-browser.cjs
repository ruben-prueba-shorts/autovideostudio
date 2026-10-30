// Import a locally rendered H.264/AAC master into the actual ClipFarming UI.
const fs=require('node:fs/promises'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const {chromium}=require('playwright');
const master=path.resolve(process.argv[2]),clipRoot=path.resolve(process.env.CLIPFARMING_DIR||'../clipfarming'),root=path.resolve(__dirname,'..'),out=path.join(root,'.test-artifacts');
async function main(){
 const handoff=path.join(path.dirname(master),'master.clipfarming.json'),pkg=JSON.parse(await fs.readFile(handoff,'utf8'));
 const server=http.createServer(async(req,res)=>{try{const file=path.resolve(clipRoot,new URL(req.url,'http://localhost').pathname.slice(1)||'index.html');if(!file.startsWith(clipRoot+path.sep))throw Error();res.setHeader('Content-Type',file.endsWith('.html')?'text/html':file.endsWith('.js')?'text/javascript':'application/octet-stream');res.end(await fs.readFile(file));}catch{res.statusCode=404;res.end();}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
 const context=await browser.newContext({acceptDownloads:true}),errors=[],external=[];context.setDefaultTimeout(30000);
 await context.route('**/*',r=>{if(r.request().url().startsWith(origin+'/'))return r.continue();external.push(r.request().url());return r.abort();});
 const p=await context.newPage();p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());
 try{
  await p.goto(origin+'/');await p.locator('#autoVideoPackagePicker').setInputFiles([master,handoff]);
  await p.waitForFunction(()=>document.getElementById('toast').textContent.includes('vinculados'));
  assert.equal(await p.evaluate(()=>state.factoryJobId),pkg.jobId);assert.equal(await p.evaluate(()=>mode()),'local');
  assert.equal(await p.evaluate(()=>state.cues.length),pkg.cues.length);
  await p.locator('#exportEngine').selectOption('standard');await p.locator('#resolution').selectOption('720');
  const dl=p.waitForEvent('download',{timeout:120000}),started=Date.now();
  await p.evaluate(()=>exportClips([state.clips[0].id],false,false));const download=await dl;
  const output=path.join(out,'offline-handoff-short.mp4');await download.saveAs(output);
  const probe=JSON.parse(execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',output],{encoding:'utf8'}));
  assert.ok(Math.abs(Number(probe.format.duration)-(pkg.clips[0].end-pkg.clips[0].start))<.15);
  const video=probe.streams.find(s=>s.codec_type==='video');assert.equal(video.width,720);assert.equal(video.height,1280);assert.ok(probe.streams.some(s=>s.codec_type==='audio'));
  await p.evaluate(async()=>{await seek(source,1);refreshPreview();});await p.screenshot({path:path.join(out,'offline-handoff-short.png')});
  assert.deepEqual(errors,[]);assert.equal(external.filter(u=>/generativelanguage|workers\.dev/.test(u)).length,0);
  const result={material:'synthetic',passed:true,source:master,short:output,elapsedSeconds:(Date.now()-started)/1000,duration:Number(probe.format.duration),videoCodec:video.codec_name,audioCodec:probe.streams.find(s=>s.codec_type==='audio').codec_name,width:video.width,height:video.height,cues:pkg.cues.length};
  await fs.writeFile(path.join(out,'offline-handoff-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }catch(e){console.error(await p.locator('#bannerText').textContent());throw e;}
 finally{await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
