// Synthetic project capacity, not acoustic synchronization or long video export.
const fs=require('node:fs/promises'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),fixtures=path.resolve(process.argv[2]||'.test-artifacts/browser-fixtures/1080');
const out=path.join(root,'.test-artifacts');
async function main(){
 const assets=(await fs.readdir(fixtures)).filter(f=>/^\d{4}\.jpg$/.test(f)).sort();assert.equal(assets.length,160);
 const server=http.createServer(async(req,res)=>{try{const file=path.resolve(root,decodeURIComponent(new URL(req.url,'http://localhost').pathname.slice(1))||'index.html');if(!file.startsWith(root+path.sep))throw Error();res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');res.end(await fs.readFile(file));}catch{res.statusCode=404;res.end();}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port,results=[];
 let browser;
 try{
  for(const [duration,count] of [[120,18],[300,44],[600,89],[1080,160]]){
   const start=Date.now(),errors=[],external=[];let peakJsHeap=0,peakRss=null;
   browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
   const context=await browser.newContext({acceptDownloads:true});context.setDefaultTimeout(120000);
   await context.route('**/*',route=>{if(route.request().url().startsWith(origin+'/'))return route.continue();external.push(route.request().url());return route.abort();});
   const p=await context.newPage();p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());
   const cdp=await context.newCDPSession(p),system=await browser.newBrowserCDPSession();await cdp.send('Performance.enable');
   let measuring=false;
   async function measure(){if(measuring)return;measuring=true;try{const metrics=await cdp.send('Performance.getMetrics');peakJsHeap=Math.max(peakJsHeap,metrics.metrics.find(m=>m.name==='JSHeapUsedSize')?.value||0);
    const processes=(await system.send('SystemInfo.getProcessInfo')).processInfo;let rss=0,valid=true;
    for(const process of processes){try{const s=await fs.readFile('/proc/'+process.id+'/status','utf8');if(!/^Name:\s*(chrom|chrome)/m.test(s)){valid=false;break;}rss+=Number(/VmRSS:\s+(\d+)/.exec(s)?.[1]||0)*1024;}catch{valid=false;break;}}
    if(valid&&rss)peakRss=Math.max(peakRss||0,rss);
   }catch{}finally{measuring=false;}}
   const interval=setInterval(()=>measure(),500);
   try{
    await p.goto(origin+'/index.html');await p.waitForSelector('#factoryJobImportBtn');
    const job={format:'video-factory-job/v1',id:'browser_load_'+duration,title:'SYNTHETIC '+duration,language:'es',niche:'life-ranges',aspectRatio:'16:9',scenes:Array.from({length:count},(_,i)=>({narration:'Synthetic scene '+(i+1),imagePrompt:'Known synthetic image '+(i+1)}))};
    await p.locator('#factoryJobPicker').setInputFiles({name:'job.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(job))});
    await p.locator('#factoryImagesPicker').setInputFiles(assets.slice(0,count).reverse().map(f=>path.join(fixtures,f)));
    await p.waitForFunction(n=>Studio._test.snapshot().images.length===n,count);
    await p.waitForFunction(()=>!Studio.projectInfo().busy);
    await p.evaluate(()=>autoSyncProject(false));
    assert.deepEqual(await p.evaluate(()=>Studio._test.snapshot().images.map(i=>i.name)),assets.slice(0,count));
    // Adjust synthetic timeline within the page: do not shuttle hundreds of MiB
    // through the automation protocol just to change scene timing metadata.
    await p.evaluate(async duration=>{const project=Studio._test.snapshot();project.duration=duration;project.scenes.forEach((s,i)=>{s.start=i*duration/project.scenes.length;s.end=(i+1)*duration/project.scenes.length;s.wordTimings=[];});await Studio._test.restore(project);},duration);
    await p.waitForFunction(d=>Studio._test.snapshot().duration===d,duration);
    assert.deepEqual(await p.evaluate(()=>Studio._test.snapshot().scenes.map(s=>s.imgIndex)),Array.from({length:count},(_,i)=>i));
    let bytes=null;
    if(count===160){
     const dl=p.waitForEvent('download');await p.locator('#saveProjectBtn').click();const saved=await dl,file=path.join(out,'load-160.avfproject');await saved.saveAs(file);bytes=(await fs.stat(file)).size;
     await p.close();const reopen=await context.newPage();reopen.on('pageerror',e=>errors.push(e.message));reopen.on('dialog',d=>d.accept());await reopen.goto(origin+'/index.html');await reopen.locator('#projectInput').setInputFiles(file);
     await reopen.waitForFunction(()=>Studio._test.snapshot().images.length===160);
     const restored=await reopen.evaluate(async()=>{const p=Studio._test.snapshot(),hashes=[];for(const image of p.images){const binary=atob(image.url.split(',')[1]);const data=Uint8Array.from(binary,c=>c.charCodeAt(0));hashes.push(Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),b=>b.toString(16).padStart(2,'0')).join(''));}return {hashes,duration:p.duration,jobId:p.factoryJob.id};});
     const crypto=require('node:crypto'),expected=[];for(const file of assets)expected.push(crypto.createHash('sha256').update(await fs.readFile(path.join(fixtures,file))).digest('hex'));
     assert.deepEqual(restored.hashes,expected);assert.equal(restored.duration,1080);assert.equal(restored.jobId,job.id);
     const dimensions=await reopen.evaluate(()=>loadedImages.map(i=>[i.imgObj.naturalWidth,i.imgObj.naturalHeight]));assert.ok(dimensions.every(d=>d[0]===1920&&d[1]===1080));
    }
    await measure();assert.deepEqual(errors,[]);assert.equal(external.filter(u=>/workers\.dev|generativelanguage|flow\.google|huggingface/.test(u)).length,0);
    const result={material:'synthetic',duration,count,passed:true,elapsedSeconds:(Date.now()-start)/1000,projectBytes:bytes,peakJsHeapBytes:peakJsHeap,peakBrowserRssBytes:peakRss,memoryCaveat:'JS heap excludes native decoded images; RSS is null when process namespaces cannot be matched. No narration alignment or full-duration browser export was tested.'};
    results.push(result);await fs.writeFile(path.join(out,'browser-load-results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(result));
   }finally{clearInterval(interval);await browser.close();browser=null;}
  }
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
