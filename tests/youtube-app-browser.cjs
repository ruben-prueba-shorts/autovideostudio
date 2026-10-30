// Isolated UI validation, existing real local media + simulated YouTube states.
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs/promises'),assert=require('node:assert/strict');
const repo=path.resolve(__dirname,'..'),root=path.resolve(process.argv[2]||path.join(repo,'.test-artifacts/orchestrator-real-factory'));
async function main(){
 const child=spawn('python',[path.join(repo,'tools/factory_local_app.py'),'--root',root,'--port','0'],{stdio:['ignore','pipe','pipe']});let browser;
 try{
  const origin=await new Promise((resolve,reject)=>{let s='';child.stdout.on('data',b=>{s+=b;const m=/http:\/\/127\.0\.0\.1:\d+/.exec(s);if(m)resolve(m[0]);});child.on('error',reject);child.on('exit',c=>{if(c)reject(Error('Local app exited '+c));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
  const p=await browser.newPage({viewport:{width:1400,height:1000}}),external=[],errors=[];
  p.on('pageerror',e=>errors.push(e.message));await p.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():(external.push(r.request().url()),r.abort()));
  await p.goto(origin+'/');const calendar=p.getByRole('table',{name:'Calendario YouTube',exact:true});
  assert.equal(await calendar.locator('tr').count(),3);assert.match(await calendar.textContent(),/simulation · scheduled/);
  assert.match(await p.getByRole('table',{name:'Canales',exact:true}).textContent(),/SIMULATION/);
  assert.equal(await p.getByRole('button',{name:/Subir|Publicar|Borrar definitivamente/}).count(),0);
  await p.getByRole('button',{name:'Calcular sin borrar',exact:true}).click();
  await p.getByRole('heading',{name:'Simulación: no se ha borrado ningún archivo'}).waitFor();
  assert.match(await p.locator('body').textContent(),/Espacio liberado: 0 bytes/);
  assert.match(await p.locator('body').textContent(),/Simulated YouTube evidence/);
  assert.equal(await p.locator('table tr').count(),5);
  const out=path.join(repo,'.test-artifacts/youtube-local-ui.png');await p.screenshot({path:out,fullPage:true});
  assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,simulatedItems:2,cleanupCandidateFiles:4,deletedFiles:0,externalRequests:0,userWindowsTested:false}));
 }finally{if(browser)await browser.close();child.kill('SIGTERM');}
}
main().catch(e=>{console.error(e);process.exitCode=1});
