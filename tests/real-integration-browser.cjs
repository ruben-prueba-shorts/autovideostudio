// Opt-in test with existing, user-authorized assets. Never generates content.
// An isolated localhost browser is used; the connected personal browser is untouched.
const fs=require('node:fs/promises'),path=require('node:path'),http=require('node:http');
const assert=require('node:assert/strict'),{chromium}=require('playwright');
const {execFile}=require('node:child_process'),{promisify}=require('node:util'),run=promisify(execFile);
const root=path.resolve(__dirname,'..'),clipRoot=path.resolve(root,'../clipfarming');
const stage=process.argv[2],dir=path.resolve(process.argv[3]||'');
if(!['align','render','handoff','clip'].includes(stage)||!process.argv[3])throw Error('Usage: node tests/real-integration-browser.cjs align|render|handoff|clip ASSET_DIRECTORY');
const allowedModelHost=h=>['cdn.jsdelivr.net','unpkg.com','huggingface.co'].includes(h)||h.endsWith('.huggingface.co')||h.endsWith('.hf.co');
async function main(){
 const job=JSON.parse(await fs.readFile(path.join(root,'automation/real-smoke-job.json'),'utf8'));
 const network=[],errors=[];
 const server=http.createServer(async(req,res)=>{try{const url=new URL(req.url,'http://localhost'),isClip=url.pathname.startsWith('/clip/'),base=isClip?clipRoot:root;
  const rel=decodeURIComponent(url.pathname.replace(/^\/(auto|clip)\//,'')),file=path.resolve(base,rel||'index.html');
  if(!file.startsWith(base+path.sep))throw Error();const data=await fs.readFile(file);res.setHeader('Content-Type',file.endsWith('.html')?'text/html':file.endsWith('.js')?'text/javascript':'application/octet-stream');res.end(data);
 }catch{res.statusCode=404;res.end();}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 let browser,p;
 try{
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true,serviceWorkers:'block'});context.setDefaultTimeout(30000);
  await context.route('**/*',async route=>{const u=new URL(route.request().url());if(u.origin===origin)return route.continue();
   const allowed=stage==='align'&&route.request().method()==='GET'&&allowedModelHost(u.hostname);network.push({host:u.hostname,path:u.pathname,method:route.request().method(),allowed});
   if(!allowed)return route.abort();
   try{const {stdout}=await run('python3',[path.join(root,'tools/cache-public-model.py'),u.href,path.join(dir,'model-cache')],{timeout:240000,maxBuffer:4096});
    const body=await fs.readFile(stdout.trim()),type=u.pathname.endsWith('.js')?'text/javascript':u.pathname.endsWith('.json')?'application/json':u.pathname.endsWith('.wasm')?'application/wasm':'application/octet-stream';
    await route.fulfill({status:200,body,contentType:type,headers:{'access-control-allow-origin':'*'}});
   }catch(e){console.error('DEPENDENCY',u.hostname,u.pathname,String(e.stderr||e.message).slice(-1200));await route.abort();}});
  p=await context.newPage();p.on('pageerror',e=>{errors.push(e.message);console.log('PAGEERROR',e.message);});p.on('dialog',d=>d.accept());
  p.on('requestfailed',r=>console.log('REQUESTFAILED',new URL(r.url()).hostname,new URL(r.url()).pathname,r.failure()?.errorText));
  await p.goto(origin+(stage==='clip'?'/clip/':'/auto/')+'index.html');
  const save=async(name)=>{const done=p.waitForEvent('download');await p.locator('#saveProjectBtn').click();const d=await done;await d.saveAs(path.join(dir,name));};
  const open=async()=>{await p.locator('#projectInput').setInputFiles(path.join(dir,'aligned.avfproject'));await p.waitForFunction(()=>Studio._test.snapshot().verified&&!Studio.projectInfo().busy);assert.equal(await p.evaluate(()=>voiceBuffer.duration),25.8);};
  if(stage==='align'){
   await p.locator('#factoryJobPicker').setInputFiles(path.join(root,'automation/real-smoke-job.json'));
   await p.waitForFunction(id=>VideoFactoryImport.getJob()?.id===id,job.id);
   await p.locator('#factoryFolderPicker').setInputFiles(path.join(dir,'numbered'));
   await p.waitForFunction(()=>Studio._test.snapshot().images.length===3&&!Studio.projectInfo().busy);
   assert.deepEqual(await p.evaluate(()=>Studio._test.snapshot().images.map(i=>i.sourcePromptId)),['102','110','97']);
   await p.locator('#voiceInput').setInputFiles(path.join(dir,'mako-gemini-3.8.wav'));
   await p.waitForFunction(()=>voiceBuffer?.duration===25.8&&!Studio.projectInfo().busy);
   assert.equal(await p.locator('#syncEngine').inputValue(),'local');
   let previous='';const progress=setInterval(async()=>{try{const s=await p.locator('#exportStatus').textContent();if(s!==previous){console.log('SYNC',s);previous=s;}}catch{}},3000);
   let ok;try{ok=await p.evaluate(()=>autoSyncProject(false));}finally{clearInterval(progress);}
   const result=await p.evaluate(()=>({verified:Studio._test.snapshot().verified,duration:voiceBuffer.duration,status:document.getElementById('exportStatus').textContent,
    scenes:Studio._test.snapshot().scenes,cues:scenes.flatMap(getSubtitleCues),transcript:typeof speechTranscript!=='undefined'?speechTranscript:null}));
   await fs.writeFile(path.join(dir,'alignment-result.json'),JSON.stringify(result,null,2));
   assert.equal(ok,true,'Actual local acoustic alignment failed');assert.equal(result.verified,true);assert.equal(result.scenes.length,3);
   assert.deepEqual(result.scenes.map(s=>s.text),job.scenes.map(s=>s.narration));assert.deepEqual(result.scenes.map(s=>s.imgIndex),[0,1,2]);
   assert.ok(result.scenes.every(s=>s.timingSource==='recognized'));
   await save('aligned.avfproject');await p.evaluate(()=>switchTab(4));await p.screenshot({path:path.join(dir,'autovideo-aligned.png')});
   // Fresh browser context: persisted images, audio, scene associations and verified timings.
   await context.close();const fresh=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true,serviceWorkers:'block'});
   await fresh.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():r.abort());p=await fresh.newPage();await p.goto(origin+'/auto/index.html');await open();
   const disk=JSON.parse(await fs.readFile(path.join(dir,'aligned.avfproject'),'utf8'));
   assert.deepEqual(await p.evaluate(()=>Studio._test.snapshot().images.map(i=>i.url)),disk.images.map(i=>i.url));
   assert.deepEqual(await p.evaluate(()=>Studio._test.snapshot().scenes),disk.scenes);
   await p.evaluate(async()=>{for(const i of loadedImages)await i.imgObj.decode();});
   console.log('PASS real assets, local ASR, scene order, save/close/reopen and image/audio persistence');
  }else if(stage==='render'){
   await open();await p.locator('#exportMode').selectOption('realtime');await p.locator('#exportResolution').selectOption('720');await p.locator('#streamExport').uncheck();await p.locator('#subFontSelect').selectOption('segoe');
   await p.locator('#transSelect').selectOption('cut');
   const results=[];
   // Clean master for vertical reframing, plus a captioned horizontal deliverable.
   for(const [style,name] of [['none','autovideo-browser'],['minimal','autovideo-captioned-browser']]){
    await p.locator('#subsSelect').selectOption(style);
    const begin=Date.now(),done=p.waitForEvent('download',{timeout:120000});await p.evaluate(()=>exportVideoYouTubeMaster());const d=await done;await d.saveAs(path.join(dir,name+'.mp4'));
    results.push({name,elapsedSeconds:(Date.now()-begin)/1000,sourceDuration:25.8,subtitlesBurned:style!=='none'});
    await save(style==='none'?'clean-master.avfproject':'captioned.avfproject');console.log('PASS actual AutoVideo browser MP4 export',name);
   }
   await fs.writeFile(path.join(dir,'browser-render.json'),JSON.stringify(results,null,2));
  }else if(stage==='handoff'){
   await open();await p.locator('#subsSelect').selectOption('none');
   const done=p.waitForEvent('download');await p.locator('#factoryMasterPicker').setInputFiles(path.join(dir,'master-h264.mp4'));const d=await done;await d.saveAs(path.join(dir,'handoff.json'));
   console.log('PASS handoff for final H264 master');
  }else{
   await p.locator('#autoVideoPackagePicker').setInputFiles([path.join(dir,'master-h264.mp4'),path.join(dir,'handoff.json')]);
   await p.waitForFunction(()=>document.getElementById('toast').textContent.includes('vinculados'));
   const handoff=JSON.parse(await fs.readFile(path.join(dir,'handoff.json'),'utf8'));
   assert.equal(await p.evaluate(()=>mode()),'local');assert.equal(await p.evaluate(()=>state.cues.length),handoff.cues.length);
   await p.locator('#addManual').click();await p.waitForFunction(()=>state.clips.length===1);
   await p.locator('#exportEngine').selectOption('standard');await p.locator('#resolution').selectOption('720');
   await p.locator('#burnSubs').check();await p.locator('#framing').selectOption('contain');
   const settings=await p.evaluate(()=>({mode:mode(),cues:state.cues,clip:state.clips[0]}));await fs.writeFile(path.join(dir,'clip-settings.json'),JSON.stringify(settings,null,2));
   const begin=Date.now(),done=p.waitForEvent('download',{timeout:120000});await p.evaluate(()=>exportClips([state.clips[0].id],false,false));const d=await done;await d.saveAs(path.join(dir,'short-browser.mp4'));
   await fs.writeFile(path.join(dir,'clip-render.json'),JSON.stringify({elapsedSeconds:(Date.now()-begin)/1000},null,2));
   await p.evaluate(async()=>{await seek(source,2);refreshPreview();});await p.screenshot({path:path.join(dir,'clipfarming-real.png')});
   console.log('PASS actual ClipFarming import and vertical export');
  }
  assert.deepEqual(errors,[]);assert.ok(network.every(n=>n.allowed||!/(generativelanguage|flow\.google|workers\.dev)/.test(n.host)));
 }catch(e){if(p){try{await p.screenshot({path:path.join(dir,'failure-'+stage+'.png')});console.error(await p.locator('#exportStatus').textContent({timeout:1000}));}catch{}}throw e;}
 finally{await fs.writeFile(path.join(dir,'network-'+stage+'.json'),JSON.stringify({requests:network,errors},null,2));if(browser)await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
