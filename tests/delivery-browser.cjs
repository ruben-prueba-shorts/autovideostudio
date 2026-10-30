// Verify the orchestrator's actual delivered files in ClipFarming, no re-render.
const fs=require('node:fs/promises'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const folder=path.resolve(process.argv[2]),clipRoot=path.resolve(__dirname,'../../clipfarming');
async function main(){
 const server=http.createServer(async(req,res)=>{try{const f=path.resolve(clipRoot,new URL(req.url,'http://localhost').pathname.slice(1)||'index.html');if(!f.startsWith(clipRoot+path.sep))throw Error();res.setHeader('Content-Type',f.endsWith('.html')?'text/html':f.endsWith('.js')?'text/javascript':'application/octet-stream');res.end(await fs.readFile(f));}catch{res.statusCode=404;res.end();}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 let browser;const errors=[],external=[];
 try{
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});const p=await browser.newPage({viewport:{width:1440,height:1000}});
  await p.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():(external.push(r.request().url()),r.abort()));p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());
  await p.goto(origin+'/');await p.locator('#autoVideoPackagePicker').setInputFiles([path.join(folder,'master-clean.mp4'),path.join(folder,'master-clean.clipfarming.json')]);
  await p.waitForFunction(()=>document.getElementById('toast').textContent.includes('vinculados'));
  const handoff=JSON.parse(await fs.readFile(path.join(folder,'master-clean.clipfarming.json'),'utf8'));
  assert.equal(await p.evaluate(()=>state.cues.length),handoff.cues.length);assert.equal(await p.evaluate(()=>mode()),'local');
  await p.locator('#importProjectFile').setInputFiles(path.join(folder,'clipfarming-project.json'));
  await p.waitForFunction(()=>state.clips.length>0);assert.equal(await p.evaluate(()=>state.clips.length),JSON.parse(await fs.readFile(path.join(folder,'clipfarming-project.json'),'utf8')).clips.length);
  await p.evaluate(async()=>{await seek(source,10.7);refreshPreview();});await p.screenshot({path:path.join(path.dirname(path.dirname(folder)),'clipfarming-delivery.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  const result={passed:true,masterIdentityPassed:true,editableProjectRestored:true,cues:handoff.cues.length,externalRequests:0};
  await fs.writeFile(path.join(__dirname,'../.test-artifacts/delivery-ui-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1});
