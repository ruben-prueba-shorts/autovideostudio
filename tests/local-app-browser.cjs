// Isolated localhost UI test; never controls the personal Brave browser.
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs/promises'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),dir=path.join(root,'.test-artifacts','local-app-ui-'+Date.now());
async function main(){
 await fs.mkdir(dir,{recursive:true});
 const server=spawn('python3',[path.join(root,'tools/factory_local_app.py'),'--root',path.join(dir,'factory'),'--port','0'],{cwd:root,stdio:['ignore','pipe','pipe']});
 let browser;const external=[],errors=[];
 try{
  const origin=await new Promise((resolve,reject)=>{let text='';server.stdout.on('data',b=>{text+=b;const m=/http:\/\/127\.0\.0\.1:\d+/.exec(text);if(m)resolve(m[0]);});server.on('error',reject);server.on('exit',c=>{if(c)reject(Error('Local app exited '+c));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
  const p=await browser.newPage({viewport:{width:1280,height:1000}});p.on('pageerror',e=>errors.push(e.message));
  await p.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():(external.push(r.request().url()),r.abort()));
  const report={format:'video-factory-ideas/v1',id:'synthetic_browser_report',material:'synthetic',observedAt:'2026-10-30T12:00:00Z',ideas:Array.from({length:10},(_,i)=>({number:i+1,channel:['life-ranges-es','life-ranges-en','finance-es','finance-en'][i%4],title:'Synthetic idea '+(i+1),originalAngle:'Test only',potentialReason:'Not viral research',sources:[{url:'https://www.youtube.com/watch?v=aaaaaaaaaaa',observedAt:'2026-10-30T12:00:00Z',metrics:{views:null}}]}))};
  await p.goto(origin+'/');await p.getByLabel('Informe JSON',{exact:true}).fill(JSON.stringify(report));await p.getByRole('button',{name:'Guardar informe',exact:true}).click();
  await p.getByLabel('Tu elección',{exact:true}).fill('Haz el vídeo 3');await p.getByRole('button',{name:'Preparar vídeo',exact:true}).click();
  assert.equal(await p.locator('table tr').count(),2);
  await p.getByRole('button',{name:'Preparar vídeo',exact:true}).click();assert.equal(await p.locator('table tr').count(),2);
  await p.getByRole('button',{name:'Procesar siguiente vídeo',exact:true}).click();
  for(let i=0;i<30;i++){await p.reload();if((await p.locator('table').textContent()).includes('blocked'))break;await new Promise(r=>setTimeout(r,100));}
  assert.ok((await p.locator('table').textContent()).includes('waiting_for_script'));
  await p.screenshot({path:path.join(dir,'local-app.png'),fullPage:true});assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  const result={passed:true,selection:3,duplicateSelectionDidNotDuplicate:true,blockedWithoutScript:true,externalRequests:0,localHostOnly:true,userPcFolderTested:false};
  await fs.writeFile(path.join(root,'.test-artifacts','local-app-ui-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
}
main().catch(e=>{console.error(e);process.exitCode=1});
