// Phase9 real E2E, attested disposable PostgreSQL and fake SMTP only.
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.HIATLAS_PLAYWRIGHT_MODULE||'playwright');
const origin=process.env.HIATLAS_E2E_ORIGIN,password=process.env.HIATLAS_E2E_PASSWORD;
assert(origin&&password,'Controlled environment required');
const output=path.resolve('../docs/superpowers/validation/hiatlas-platform/phase-09-visual');
mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,channel:'chrome'});
let stage='startup';
const errors=[],unsafe=[],reauthResults=[];
let diagnosticPage;
function fixture(action,id){
 try{return execFileSync(path.resolve('../backend/.venv/Scripts/python.exe'),[path.resolve('../scripts/phase09_browser_fixture.py'),action,...(id?['--id',id]:[])],{cwd:path.resolve('..'),encoding:'utf8',stdio:'pipe'}).trim();}
 catch{throw new Error('Controlled fixture failure; sensitive diagnostics suppressed');}
}
async function pageIn(context){
 const page=await context.newPage();
 page.on('pageerror',()=>errors.push('pageerror'));
 page.on('response',async response=>{if(new URL(response.url()).pathname==='/api/auth/reauthenticate'){let code='';try{const data=await response.json();if(/^[A-Z_]{1,80}$/.test(data.code))code=data.code;}catch{}reauthResults.push({status:response.status(),code});}});
 page.on('request',request=>{const url=new URL(request.url());if(url.origin!==origin||url.searchParams.has('token'))unsafe.push('unsafe');});
 return page;
}
async function fresh(){const context=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1000}});return[context,await pageIn(context)];}
async function api(page,route,body,contextId,method){
 return page.evaluate(async({route,body,contextId,method})=>{
  const headers={Accept:'application/json'};
  if(contextId)headers['X-HiAtlas-Context']=contextId;
  if(body!==undefined)headers['Content-Type']='application/json';
  const verb=method||(body===undefined?'GET':'POST');
  if(verb!=='GET'){
   const csrf=await fetch('/api/auth/csrf');
   if(!csrf.ok)return{status:csrf.status,body:null};
   headers['X-CSRF-Token']=(await csrf.json()).token;
  }
  const response=await fetch('/api'+route,{method:verb,headers,body:body===undefined?undefined:JSON.stringify(body)});
  return{status:response.status,body:response.status===204?null:await response.json()};
 },{route,body,contextId,method});
}
async function login(page,email){
 await page.goto(origin);await page.getByLabel('E-mail',{exact:true}).fill(email);
 await page.getByLabel('Senha',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Entrar no HiAtlas',exact:true}).click();
 await page.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();
}
async function select(page,code){
 await page.getByRole('button',{name:'Acessar contrato '+code,exact:true}).click();
 await page.getByTestId('contract-context').getByText(code,{exact:true}).waitFor();
 return page.evaluate(()=>sessionStorage.getItem('hiatlas.access-context.v1'));
}
async function shot(page,name){
 await page.locator('img').evaluateAll(images=>Promise.all(images.map(image=>image.decode().catch(()=>{}))));
 await page.screenshot({path:path.join(output,name+'.png'),fullPage:false});
}
async function noOverflow(page){
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'External overflow');
}
async function storageSafe(page){
 const values=await page.evaluate(()=>({session:Object.fromEntries(Object.keys(sessionStorage).map(k=>[k,sessionStorage.getItem(k)])),local:Object.fromEntries(Object.keys(localStorage).map(k=>[k,localStorage.getItem(k)]))}));
 for(const[k,v]of Object.entries(values.session)){
  assert(/^hiatlas\.(access-context|privileged-context|support-session)\.v1$/.test(k),'Unexpected persisted business state');
  assert(/^[0-9a-f-]{36}$/i.test(v),'Only opaque identifiers may persist');
 }
 for(const k of Object.keys(values.local))assert.equal(k,'hiatlas-theme');
}
try{
 const ids=JSON.parse(fixture('seed'));
 const[adminContext,admin]=await fresh();diagnosticPage=admin;
 stage='admin login';await login(admin,'admin@example.test');let parent=await select(admin,'CTR-A');
 stage='normal contexts do not inherit exception';
 const normal=await pageIn(adminContext);await normal.goto(origin);
 await normal.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();const normalParent=await select(normal,'CTR-A');
 const a2Page=await pageIn(adminContext);await a2Page.goto(origin);await a2Page.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();const a2=await select(a2Page,'CTR-A2');
 const bPage=await pageIn(adminContext);await bPage.goto(origin);await bPage.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();const b=await select(bPage,'CTR-B');
 stage='financial request, stale reauthentication, contextual confirmation';
 assert(parent&&normalParent&&a2&&b&&ids.admin_user);
 await admin.getByRole('button',{name:'Acessos Temporários',exact:true}).click();
 await admin.getByRole('heading',{name:'Acessos Temporários',exact:true}).waitFor();
 await admin.getByText('Nenhuma operação de manutenção está disponível nesta versão.',{exact:true}).waitFor();
 assert.deepEqual((await api(admin,'/grants/maintenance-actions',undefined,parent)).body.items,[]);
 fixture('stale-reauth');
 const payload={grant_type:'FINANCIAL_FISCAL',reason:'Investigação controlada de teste',reference:'SUP-TEST-009',scopes:[]};
 assert.equal((await api(admin,'/grants',payload,parent)).status,403);
 await admin.getByRole('button',{name:'Solicitar acesso Financeiro/Fiscal',exact:true}).click();
 let dialog=admin.getByRole('dialog');
 await dialog.getByLabel('Motivo do acesso temporário',{exact:true}).fill(payload.reason);
 await dialog.getByLabel('Referência / chamado (opcional)',{exact:true}).fill(payload.reference);
 stage='wrong reauthentication password retains real authenticated operator';
 await dialog.getByLabel('Confirme sua senha',{exact:true}).fill(password+'-wrong');
 await dialog.getByRole('button',{name:'Reautenticar e revisar',exact:true}).click();
 await dialog.getByRole('alert').waitFor();
 assert.equal(await admin.getByRole('heading',{name:'Bem-vindo à HiAtlas',exact:true}).count(),0);
 assert.equal(await admin.evaluate(()=>sessionStorage.getItem('hiatlas.access-context.v1')),parent);
 await shot(admin,'financial-reauth-denied');
 await dialog.getByLabel('Confirme sua senha',{exact:true}).fill(password);
 await shot(admin,'financial-reauth');
 await dialog.getByRole('button',{name:'Reautenticar e revisar',exact:true}).click();
 await dialog.getByRole('button',{name:'Confirmar acesso temporário',exact:true}).waitFor();
 await shot(admin,'financial-confirmation');
 const operatorCookie=(await adminContext.cookies()).find(cookie=>cookie.name==='__Host-hiatlas-session')?.value;
 await dialog.getByRole('button',{name:'Confirmar acesso temporário',exact:true}).click();
 const banner=admin.getByRole('region',{name:'Acesso temporário privilegiado',exact:true});
 await banner.waitFor();
 await admin.getByText('Módulo operacional ainda indisponível.',{exact:true}).waitFor();
 const privileged=await admin.evaluate(()=>sessionStorage.getItem('hiatlas.privileged-context.v1'));
 assert(privileged&&privileged!==parent);
 const grant=(await api(admin,'/grants/context',undefined,privileged)).body;
 assert.equal(grant.operator.user_id,ids.admin_user);assert.equal(grant.parent_context_id,parent);assert.equal(grant.context_id,privileged);assert.equal(grant.grant_type,'FINANCIAL_FISCAL');assert.equal(grant.status,'ACTIVE');
 assert.equal((await adminContext.cookies()).find(cookie=>cookie.name==='__Host-hiatlas-session')?.value,operatorCookie);
 assert.equal(await admin.evaluate(()=>sessionStorage.getItem('hiatlas.access-context.v1')),parent);
 await storageSafe(admin);await shot(admin,'financial-light');
 stage='ordinary contexts and cross-contract isolation';
 assert.equal((await api(normal,'/grants/context',undefined,normalParent)).status,403);
 const ordinary=(await api(normal,'/context',undefined,normalParent)).body;
 assert(!ordinary.capabilities.includes('finance.read')&&!ordinary.capabilities.includes('fiscal.read'));
 assert.equal(await normal.getByRole('region',{name:'Acesso temporário privilegiado',exact:true}).count(),0);
 for(const foreign of[a2,b]){
  assert([403,404].includes((await api(admin,'/grants/'+grant.id+'/end',{expected_version:grant.version},foreign)).status));
  const history=await api(admin,'/grants?limit=20&offset=0',undefined,foreign);
  assert.equal(history.status,200);assert(!history.body.items.some(row=>row.id===grant.id));
 }
 stage='derived context does not release generic mutation or management reads';
 for(const[route,body,method]of[
  ['/memberships/'+ids.member_a+'/reset-password',{},'POST'],
  ['/memberships/'+ids.member_a+'/status',{active:false,expected_version:1},'PATCH'],
  ['/memberships/'+ids.member_a+'/role',{role_id:ids.role_basic,expected_version:1},'PUT'],
  ['/contexts/'+parent,undefined,'DELETE'],
  ['/tenants',{name:'Never created'},'POST'],
 ])assert.equal((await api(admin,route,body,privileged,method)).status,403);
 assert.equal((await api(admin,'/memberships?limit=20',undefined,privileged)).status,403);
 const modules=await api(admin,'/contract/modules',undefined,parent);
 assert.equal(modules.status,200);assert(modules.body.items.every(module=>!module.operational_available));
 stage='exact new HTTP session binding';
 const[newContext,newAdmin]=await fresh();await login(newAdmin,'admin@example.test');await select(newAdmin,'CTR-A');
 assert.equal((await api(newAdmin,'/grants/context',undefined,privileged)).status,403);
 await newContext.close();
 stage='reload, unchanged expiry, keyboard, light dark mobile sticky';
 await admin.reload();await banner.waitFor();
 const restored=await api(admin,'/grants/context',undefined,privileged);
 assert.equal(restored.status,200);assert.equal(restored.body.expires_at,grant.expires_at);
 await admin.getByRole('button',{name:'Tema escuro',exact:true}).click();await shot(admin,'financial-dark');
 await admin.setViewportSize({width:390,height:844});await noOverflow(admin);await shot(admin,'financial-mobile');
 await admin.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
 const bounds=await banner.boundingBox();assert(bounds&&bounds.y>=0&&bounds.y<500);
 await admin.getByRole('button',{name:'Encerrar acesso temporário',exact:true}).focus();
 await admin.keyboard.press('Enter');dialog=admin.getByRole('dialog');await dialog.waitFor();await shot(admin,'financial-end-confirmation');
 await admin.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
 await admin.getByRole('button',{name:'Encerrar acesso temporário',exact:true}).click();
 await admin.getByRole('dialog').getByRole('button',{name:'Confirmar encerramento',exact:true}).click();
 await banner.waitFor({state:'hidden'});
 assert.equal(await admin.evaluate(()=>sessionStorage.getItem('hiatlas.privileged-context.v1')),null);
 assert.equal(await admin.evaluate(()=>sessionStorage.getItem('hiatlas.access-context.v1')),parent);
 assert.equal((await api(admin,'/memberships?limit=20',undefined,parent)).status,200);
 assert.equal((await api(admin,'/grants/context',undefined,privileged)).status,403);
 await shot(admin,'financial-ended');
 stage='expiry and parent revocation clear privileged state';
 await admin.setViewportSize({width:1440,height:1000});
 async function startAgain(){
  const response=await api(admin,'/grants',payload,parent);assert.equal(response.status,201);
  await admin.evaluate(context=>sessionStorage.setItem('hiatlas.privileged-context.v1',context),response.body.context_id);
  await admin.reload();await banner.waitFor();return response.body;
 }
 let next=await startAgain();fixture('expire',next.id);
 await admin.reload();await banner.waitFor({state:'hidden'});
 assert.equal((await api(admin,'/grants/context',undefined,next.context_id)).status,403);
 await shot(admin,'financial-expired');
 // The safe parent remains usable after grant expiry.
 assert.equal((await api(admin,'/context',undefined,parent)).status,200);
 await admin.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();parent=await select(admin,'CTR-A');
 next=await startAgain();fixture('revoke-context',parent);
 await admin.reload();await banner.waitFor({state:'hidden'});
 await admin.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();
 assert.equal(await admin.evaluate(()=>sessionStorage.getItem('hiatlas.privileged-context.v1')),null);
 await shot(admin,'financial-revoked');
 stage='Support has neither menu nor privilege, even stolen context';
 const[supportContext,support]=await fresh();await login(support,'support@example.test');const supportParent=await select(support,'CTR-A');
 assert.equal(await support.getByRole('button',{name:'Acessos Temporários',exact:true}).count(),0);
 assert.equal((await api(support,'/grants',payload,supportParent)).status,403);
 assert.equal((await api(support,'/grants?limit=20',undefined,supportParent)).status,403);
 assert.equal((await api(support,'/grants/context',undefined,next.context_id)).status,403);
 assert.equal((await api(support,'/grants/'+next.id+'/end',{expected_version:next.version},supportParent)).status,403);
 await shot(support,'support-no-privilege');
 stage='READ_ONLY never silently becomes privileged';
 const supportSession=await api(support,'/support-sessions',{membership_id:ids.member_a,reason:'Atendimento controlado sem elevação'},supportParent);
 assert.equal(supportSession.status,201);
 assert.equal((await api(support,'/grants',payload,supportSession.body.context_id)).status,403);
 assert.equal((await api(support,'/grants',{grant_type:'MAINTENANCE',reason:'Ação inválida',reference:'SUP-TEST-009',scopes:[{action_code:'UNREGISTERED',entity_type:'organization_node',entity_id:null}]},supportSession.body.context_id)).status,403);
 assert.equal((await api(support,'/support-sessions/'+supportSession.body.id+'/end',{},supportParent)).status,204);
 await supportContext.close();
 stage='sanitized real contextual history/audit and maintenance unavailable';
 const freshParent=await select(admin,'CTR-A');
 await admin.getByRole('button',{name:'Acessos Temporários',exact:true}).click();
 await admin.getByText('Nenhuma operação de manutenção está disponível nesta versão.',{exact:true}).waitFor();
 const history=await api(admin,'/grants?limit=20&offset=0',undefined,freshParent);
 assert.equal(history.status,200);assert(history.body.items.some(row=>row.id===grant.id&&row.status==='ENDED'));
 const audit=await api(admin,'/audit?limit=20&offset=0',undefined,freshParent);
 assert.equal(audit.status,200);assert(audit.body.items.some(row=>row.action.startsWith('privileged_grant.')));
 await shot(admin,'maintenance-unavailable');
 await storageSafe(admin);assert.equal(errors.length,0);assert.equal(unsafe.length,0);
 await adminContext.close();
 console.log('[PASS] Phase9 real Admin/Support E2E, exact HTTP/contract isolation, reauth, lifecycle, unavailable modules/maintenance, themes/mobile/keyboard/storage');
}catch(error){
 if(diagnosticPage)await diagnosticPage.screenshot({path:path.join(process.env.HIATLAS_E2E_STATE,'failure.png'),fullPage:false}).catch(()=>{});
 console.error('Sanitized reauthentication results: '+JSON.stringify(reauthResults));
 const at=String(error?.stack??'').match(/phase09[.]mjs:(\d+):(\d+)/);
 console.error('[FAIL] Phase9 E2E at '+stage+'; '+String(error?.name??'Error')+'; harness line '+(at?.[1]??'unknown')+'; sensitive diagnostics suppressed');
 process.exitCode=1;
}finally{await browser.close();}
