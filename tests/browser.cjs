// Real isolated Chromium. All requests outside this local server are blocked.
const fs=require('node:fs/promises'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict'),zlib=require('node:zlib');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),clipRoot=process.env.CLIPFARMING_DIR&&path.resolve(process.env.CLIPFARMING_DIR);
const renderSeconds=Number(process.env.SYNTHETIC_RENDER_SECONDS||0);
if(!Number.isFinite(renderSeconds)||renderSeconds<0||renderSeconds>1200)throw Error('Invalid synthetic test duration');
const out=path.join(root,'.test-artifacts',renderSeconds?'browser-render-'+renderSeconds:'');
const example=require('../automation/example-job.json');
function png(color){
  function crc(b){let c=-1;for(const v of b){c^=v;for(let i=0;i<8;i++)c=(c>>>1)^((c&1)?0xedb88320:0);}return (c^-1)>>>0;}
  function chunk(type,b){const t=Buffer.from(type),head=Buffer.alloc(4),tail=Buffer.alloc(4);head.writeUInt32BE(b.length);tail.writeUInt32BE(crc(Buffer.concat([t,b])));return Buffer.concat([head,t,b,tail]);}
  const h=Buffer.alloc(13);h.writeUInt32BE(32,0);h.writeUInt32BE(24,4);h[8]=8;h[9]=2;
  const rows=Buffer.concat(Array.from({length:24},()=>Buffer.concat([Buffer.from([0]),Buffer.from(Array.from({length:32},()=>color).flat())])));
  return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',h),chunk('IDAT',zlib.deflateSync(rows)),chunk('IEND',Buffer.alloc(0))]);
}
async function main(){
  await fs.mkdir(out,{recursive:true});
  const images=[];for(let i=1;i<=12;i++){const p=path.join(out,String(i).padStart(4,'0')+'.png');await fs.writeFile(p,png(i%2?[220,30,40]:[20,60,220]));images.push(p);}
  const server=http.createServer(async(req,res)=>{try{const url=new URL(req.url,'http://localhost');const isClip=url.pathname.startsWith('/clip/'),base=isClip?clipRoot:root;if(!base)throw Error();const rel=decodeURIComponent(url.pathname.replace(/^\/(auto|clip)\//,''));const file=path.resolve(base,rel||'index.html');if(!file.startsWith(base+path.sep))throw Error();const data=await fs.readFile(file);res.setHeader('Content-Type',file.endsWith('.html')?'text/html':file.endsWith('.js')?'text/javascript':'application/octet-stream');res.end(data);}catch{res.statusCode=404;res.end();}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
  let browser,context,p;const errors=[],network=[];
  async function start(){browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{channel:'chromium'}),args:['--no-sandbox']});context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});context.setDefaultTimeout(15000);await context.route('**/*',route=>{const u=route.request().url();if(u.startsWith(origin+'/'))return route.continue();network.push(u);return route.abort();});}
  async function pageAt(app='auto'){const p=await context.newPage();p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());await p.goto(origin+'/'+app+'/index.html');await p.waitForSelector(app==='auto'?'#factoryJobImportBtn':'#importAutoVideoBtn');return p;}
  async function uploadJob(page,job){await page.locator('#factoryJobPicker').setInputFiles({name:'job.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(job))});await page.waitForFunction(id=>VideoFactoryImport.getJob()?.id===id,job.id);}
  async function save(page,name){const done=page.waitForEvent('download');await page.locator('#saveProjectBtn').click();const d=await done,p=path.join(out,name);await d.saveAs(p);return p;}
  try {
    await start();
    if(!process.env.HANDOFF_ONLY){
    for(const niche of ['finance','life-ranges'])for(const language of ['es','en']){
      const p=await pageAt();await uploadJob(p,{...example,niche,language});
      assert.deepEqual(await p.evaluate(()=>[VideoFactoryImport.getJob().niche,VideoFactoryImport.getJob().language,document.getElementById('syncEngine').value,document.getElementById('voiceEngine').value]),[niche,language,'local','upload']);await p.close();
    }
    console.log('PASS: UI imports all four channel profiles without provider calls.');
    // A curated batch binds image bytes, prompt and narration, preserving its
    // original Flow prompt ID independently of the new scene number.
    p=await pageAt();const boundJob={...example,id:'bound_scene_001',scenes:[{narration:'Known synthetic narration.',imagePrompt:'102- Known synthetic red image.'}]};await uploadJob(p,boundJob);
    const hash=b=>require('node:crypto').createHash('sha256').update(b).digest('hex');
    const bindings={format:'video-factory-bindings/v1',jobId:boundJob.id,scenes:[{sceneIndex:1,promptSha256:hash(boundJob.scenes[0].imagePrompt),narrationSha256:hash(boundJob.scenes[0].narration),sourcePromptId:'102',image:{name:'0001.png',sha256:hash(await fs.readFile(images[0]))}}]};
    const wrongBinding=structuredClone(bindings);wrongBinding.scenes[0].image.sha256='0'.repeat(64);
    await p.locator('#factoryImagesPicker').setInputFiles([{name:'0001.png',mimeType:'image/png',buffer:await fs.readFile(images[0])},{name:'bindings.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(wrongBinding))}]);
    await p.waitForFunction(()=>document.getElementById('studioToast').textContent.includes('no coinciden'));assert.equal(await p.evaluate(()=>Studio._test.snapshot().images.length),0);await p.waitForFunction(()=>!Studio.projectInfo().busy);
    await p.locator('#factoryImagesPicker').setInputFiles([{name:'0001.png',mimeType:'image/png',buffer:await fs.readFile(images[0])},{name:'bindings.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(bindings))}]);
    await p.waitForFunction(()=>Studio._test.snapshot().images.length===1);await p.waitForFunction(()=>!Studio.projectInfo().busy);await p.evaluate(()=>autoSyncProject(false));
    const bound=await save(p,'bound.avfproject');await p.close();p=await pageAt();await p.locator('#projectInput').setInputFiles(bound);await p.waitForFunction(()=>Studio._test.snapshot().images.length===1);
    assert.equal(await p.evaluate(()=>Studio._test.snapshot().images[0].sourcePromptId),'102');assert.match(await p.evaluate(()=>Studio._test.snapshot().images[0].bindingSha256),/^[a-f0-9]{64}$/);await p.close();
    console.log('PASS: binding mismatch rejected atomically and verified source prompt ID survives save/reopen.');
    p=await pageAt();const job={...example,id:'ordered_012',scenes:Array.from({length:12},(_,i)=>({narration:'Scene '+(i+1)+'. More words.',imagePrompt:'Prompt '+(i+1)}))};await uploadJob(p,job);
    await p.locator('#nav3').click();const promptsDone=p.waitForEvent('download');await p.locator('#factoryFlowPromptsBtn').click();const promptDownload=await promptsDone;const prompts=await fs.readFile(await promptDownload.path(),'utf8');assert.deepEqual(prompts.split('\n'),job.scenes.map(s=>s.imagePrompt));
    // Missing batch must leave the state untouched.
    await p.locator('#factoryImagesPicker').setInputFiles(images.slice(0,11));await p.waitForFunction(()=>document.getElementById('studioToast').textContent.includes('Faltan imágenes'));assert.equal(await p.evaluate(()=>Studio._test.snapshot().images.length),0);
    await p.locator('#factoryImagesPicker').setInputFiles([images[9],images[0],images[11],...images.slice(1,9),images[10]]);
    await p.waitForFunction(()=>Studio._test.snapshot().images.length===12);
    await p.evaluate(()=>autoSyncProject(false));
    let state=await p.evaluate(()=>Studio._test.snapshot());assert.deepEqual(state.images.map(x=>x.name),images.map(x=>path.basename(x)));assert.deepEqual(state.images.map(x=>x.prompt),job.scenes.map(x=>x.imagePrompt));
    assert.deepEqual(state.scenes.map(x=>x.text),job.scenes.map(x=>x.narration));
    const mapping=state.scenes.map(x=>x.imgIndex);await p.evaluate(()=>fitImagesToScenes());
    assert.deepEqual(await p.evaluate(()=>Studio._test.snapshot().scenes.map(x=>x.imgIndex)),mapping);
    assert.equal(await p.locator('#autoImageFit').isChecked(),false);assert.equal(await p.locator('#aiImageFit').isChecked(),false);
    const saved=await save(p,'roundtrip.avfproject');const disk=JSON.parse(await fs.readFile(saved,'utf8'));assert.ok(disk.images.every(x=>x.url.startsWith('data:image/png;base64,')));assert.equal(disk.factoryJob.id,job.id);
    await browser.close();await start();p=await pageAt();await p.locator('#projectInput').setInputFiles(saved);await p.waitForFunction(()=>Studio._test.snapshot().images.length===12);
    state=await p.evaluate(()=>Studio._test.snapshot());assert.deepEqual(state.images.map(x=>x.url),disk.images.map(x=>x.url));assert.equal(state.factoryJob.id,job.id);
    const pixels=await p.evaluate(async()=>{const values=[];for(const item of Studio._test.snapshot().images){const img=new Image();img.src=item.url;await img.decode();const c=document.createElement('canvas');c.width=c.height=1;c.getContext('2d').drawImage(img,0,0,1,1);values.push([...c.getContext('2d').getImageData(0,0,1,1).data]);}return values;});
    assert.deepEqual(pixels[0],[220,30,40,255]);assert.deepEqual(pixels[1],[20,60,220,255]);await p.screenshot({path:path.join(out,'reopened-project.png')});
    console.log('PASS: save to disk, close Chromium, relaunch with fresh storage, reopen, decode and compare all 12 images and scene associations.');
    // Draft recovery also survives a new page and object-URL lifetime.
    await p.waitForFunction(()=>document.getElementById('saveState').textContent.includes('Borrador local guardado'));
    await p.close();p=await pageAt();await p.locator('#restoreDraftBtn').click();await p.waitForFunction(()=>Studio._test.snapshot().images.length===12);await p.close();
    console.log('PASS: IndexedDB draft recovery.');
    // Actual folder picker, and a one-scene job with more than one sentence.
    const folder=path.join(out,'one-scene-batch');await fs.mkdir(folder,{recursive:true});await fs.copyFile(images[0],path.join(folder,'0001.png'));
    p=await pageAt();const single={...example,id:'single_001',scenes:[{narration:'First sentence. Second sentence.',imagePrompt:'A single red scene.'}]};await uploadJob(p,single);
    await p.locator('#factoryFolderPicker').setInputFiles(folder);await p.waitForFunction(()=>Studio._test.snapshot().images.length===1);await p.evaluate(()=>autoSyncProject(false));
    assert.deepEqual(await p.evaluate(()=>Studio._test.snapshot().scenes.map(x=>x.text)),[single.scenes[0].narration]);await p.close();
    console.log('PASS: folder import and single-scene narration preservation.');
    // Generic import, without a production job, also persists images and is atomic.
    p=await pageAt();await p.locator('#imgInput').setInputFiles([{name:'good.png',mimeType:'image/png',buffer:png([30,200,40])},{name:'bad.png',mimeType:'image/png',buffer:Buffer.from('invalid')}]);
    await p.waitForFunction(()=>document.getElementById('studioToast').textContent.includes('decodificar'));assert.equal(await p.evaluate(()=>Studio._test.snapshot().images.length),0);
    await p.locator('#imgInput').setInputFiles(images.slice(0,2));await p.waitForFunction(()=>Studio._test.snapshot().images.length===2);await p.evaluate(()=>autoSyncProject(false));const generic=await save(p,'generic.avfproject');await p.close();p=await pageAt();await p.locator('#projectInput').setInputFiles(generic);await p.waitForFunction(()=>Studio._test.snapshot().images.length===2);assert.equal(await p.evaluate(()=>Studio._test.snapshot().factoryJob),null);await p.close();
    console.log('PASS: generic image import round-trip and corrupt-batch rollback.');
    }
    if(clipRoot){
      p=await pageAt();await uploadJob(p,example);await p.locator('#factoryImagesPicker').setInputFiles(images.slice(0,2));await p.waitForFunction(()=>Studio._test.snapshot().images.length===2);await p.evaluate(()=>autoSyncProject(false));
      // Completed test project with a synthetic tone and known scene times.
      // This tests media transport/rendering, not speech recognition or real narration alignment.
      const completed=await p.evaluate(()=>Studio._test.snapshot());
      if(renderSeconds){const scale=renderSeconds/completed.duration;completed.scenes.forEach(s=>{s.start*=scale;s.end*=scale;for(const w of s.wordTimings||[]){w.start*=scale;w.end*=scale;}});completed.duration=renderSeconds;}
      const frames=Math.round(completed.duration*24000),wav=Buffer.alloc(44+frames*2);
      wav.write('RIFF');wav.writeUInt32LE(36+frames*2,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(24000,24);wav.writeUInt32LE(48000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(frames*2,40);
      for(let i=0;i<frames;i++)wav.writeInt16LE(Math.round(2500*Math.sin(2*Math.PI*440*i/24000)),44+i*2);
      completed.voice={name:'synthetic.wav',data:'data:audio/wav;base64,'+wav.toString('base64')};completed.verified=true;
      await p.locator('#projectInput').setInputFiles({name:'completed.avfproject',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(completed))});
      await p.waitForFunction(()=>Studio._test.snapshot().verified===true);
      // Use the app's real MediaRecorder path; no CDN codec/model downloads.
      await p.locator('#exportMode').selectOption('realtime');await p.locator('#exportResolution').selectOption('720');await p.locator('#streamExport').uncheck();await p.locator('#subFontSelect').selectOption('segoe');await p.locator('#subsSelect').selectOption('none');
      const renderStarted=Date.now(),done=p.waitForEvent('download',{timeout:Math.max(60000,completed.duration*1500+60000)});await p.evaluate(()=>exportVideoYouTubeMaster());const d=await done,master=path.join(out,d.suggestedFilename());await d.saveAs(master);assert.ok((await fs.stat(master)).size>1000);
      if(renderSeconds){const info=JSON.parse(require('node:child_process').execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',master],{encoding:'utf8'})),passed=Math.abs(Number(info.format.duration)-renderSeconds)<.15;await fs.writeFile(path.join(out,'render-result.json'),JSON.stringify({material:'synthetic',duration:renderSeconds,passed,elapsedSeconds:(Date.now()-renderStarted)/1000,probe:info},null,2));assert.ok(passed,'Browser export exceeds the .15 s duration tolerance');}
      const packageDone=p.waitForEvent('download');await p.locator('#factoryMasterPicker').setInputFiles(master);const pd=await packageDone,packagePath=path.join(out,pd.suggestedFilename());await pd.saveAs(packagePath);
      const handoff=JSON.parse(await fs.readFile(packagePath,'utf8'));assert.ok(handoff.cues.length>0);assert.equal(handoff.jobId,example.id);
      console.log('PASS: real AutoVideo MP4 render and handoff JSON generation.');
      await p.close();const c=await pageAt('clip');
      const wrong=JSON.parse(JSON.stringify(handoff));wrong.video.sha256='0'.repeat(64);await c.locator('#autoVideoPackagePicker').setInputFiles([{name:path.basename(master),mimeType:'video/mp4',buffer:await fs.readFile(master)},{name:'wrong.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(wrong))}]);await c.waitForFunction(()=>document.getElementById('bannerText').textContent.includes('huella'));assert.equal(await c.evaluate(()=>state.file),null);
      await c.locator('#autoVideoPackagePicker').setInputFiles([master,packagePath]);await c.waitForFunction(()=>document.getElementById('toast').textContent.includes('vinculados'));
      assert.equal(await c.evaluate(()=>state.cues.length),handoff.cues.length);assert.equal(await c.evaluate(()=>mode()),'local');assert.equal(await c.evaluate(()=>state.factoryJobId),example.id);
      await c.locator('#addManual').click();await c.waitForFunction(()=>state.clips.length===1);await c.locator('#exportEngine').selectOption('standard');await c.locator('#resolution').selectOption('720');
      // Avoid folder permission dialog: export to browser download, not a directory.
      const clipDone=c.waitForEvent('download',{timeout:60000});await c.evaluate(()=>exportClips([state.clips[0].id],false,false));const cd=await clipDone;await cd.saveAs(path.join(out,'clip-'+cd.suggestedFilename()));
      await c.evaluate(async()=>{await seek(source,1);refreshPreview();});await c.screenshot({path:path.join(out,'clipfarming-import.png')});
      console.log('PASS: ClipFarming rejects wrong hash, imports master+cues, and exports an actual local clip.');
    }else console.log('SKIP: cross-repo video test (set CLIPFARMING_DIR).');
    assert.deepEqual(errors,[]);assert.deepEqual(network.filter(u=>/workers\.dev|generativelanguage|flow\.google|labs\.google|huggingface/.test(u)),[]);
    console.log('PASS: no browser runtime errors and no generation/transcription provider requests.');
  } catch(e) {
    if(context) for(const [i,page] of context.pages().entries()) {
      try {await fs.writeFile(path.join(out,'failure-'+i+'.json'),JSON.stringify(await page.evaluate(()=>({toast:document.getElementById('studioToast')?.textContent,exportStatus:document.getElementById('exportStatus')?.textContent,banner:document.getElementById('bannerText')?.textContent,project:window.Studio?Studio._test.snapshot():null})),null,2));await page.screenshot({path:path.join(out,'failure-'+i+'.png')});}catch{}
    }
    throw e;
  } finally {if(browser)await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
