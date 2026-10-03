// Phase10 real E2E, attested disposable PostgreSQL and fake SMTP only.
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.HIATLAS_PLAYWRIGHT_MODULE||'playwright');
const origin=process.env.HIATLAS_E2E_ORIGIN,password=process.env.HIATLAS_E2E_PASSWORD;
assert(origin&&password,'Controlled environment required');
const output=path.resolve('../docs/superpowers/validation/hiatlas-platform/phase-10-visual');
mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,channel:'chrome'});
const controlled=process.env.HIATLAS_PHASE10_E2E==='controlled';
let stage='startup';
const errors=[],unsafe=[],reauthResults=[];
let diagnosticPage;
function fixture(action, options={}){
 const args=[path.resolve('../scripts/phase10_browser_fixture.py'),action];
 for(const key of ['id','context','source'])if(options[key])args.push('--'+key,options[key]);
 try{return execFileSync(path.resolve('../backend/.venv/Scripts/python.exe'),args,{cwd:path.resolve('..'),encoding:'utf8',stdio:'pipe'}).trim();}
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
 await page.goto(origin+(controlled?'/e2e/phase10-controlled.html':'/'));await page.getByLabel('E-mail',{exact:true}).fill(email);
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
 stage='Admin login and scoped maintenance catalog';
 await login(admin,'admin@example.test');const parent=await select(admin,'CTR-A');
 await admin.getByRole('button',{name:'Manutenção',exact:true}).click();
 await admin.getByRole('heading',{name:'Manutenção',exact:true}).waitFor();
 const catalog=await api(admin,'/maintenance',undefined,parent);assert.equal(catalog.status,200);
 if(!controlled){
  assert.deepEqual(catalog.body.items,[]);
  await admin.getByText('Nenhuma operação de manutenção está disponível para este contrato.',{exact:true}).waitFor();
  assert.equal(await admin.getByRole('button',{name:'Solicitar acesso de manutenção',exact:true}).count(),0);
  assert.equal((await api(admin,'/grants',{grant_type:'MAINTENANCE',reason:'Solicitação controlada',reference:'SUP-TEST-010',scopes:[{action_code:'UNREGISTERED',entity_type:'organization_node',entity_id:ids.node_a}]},parent)).status,403);
  await shot(admin,'normal-empty-light');
  await admin.getByRole('button',{name:'Tema escuro',exact:true}).click();await shot(admin,'normal-empty-dark');
  await admin.setViewportSize({width:390,height:844});await noOverflow(admin);await shot(admin,'normal-empty-mobile');
 }else{
  assert(catalog.body.items.some(action=>action.action_code==='FIXTURE_NODE_RENAME'));
  stage='Controlled known run and explicit reauthenticated MAINTENANCE';
  const source=JSON.parse(fixture('seed-run',{id:ids.node_a,context:parent}));
  const replayPayloads=[];
  admin.on('request',request=>{if(new URL(request.url()).pathname==='/api/processings/'+source.id+'/reprocess'&&request.method()==='POST')replayPayloads.push(request.postDataJSON());});
  await admin.getByRole('button',{name:'Solicitar acesso de manutenção',exact:true}).click();
  await admin.getByLabel('Entidade autorizada',{exact:true}).fill(ids.node_a);
  await admin.getByLabel('Motivo do acesso de manutenção',{exact:true}).fill('Validação controlada da infraestrutura');
  await admin.getByLabel('Referência / chamado obrigatório',{exact:true}).fill('SUP-TEST-010');
  await admin.getByLabel('Confirme sua senha',{exact:true}).fill(password);
  await admin.getByRole('button',{name:'Reautenticar e revisar',exact:true}).click();
  await admin.getByRole('button',{name:'Confirmar acesso de manutenção',exact:true}).waitFor();await shot(admin,'maintenance-grant-review');
  await admin.getByRole('button',{name:'Confirmar acesso de manutenção',exact:true}).click();
  const banner=admin.getByRole('region',{name:'Acesso temporário privilegiado',exact:true});await banner.waitFor();
  await admin.getByText('⚠ MANUTENÇÃO AUTORIZADA',{exact:true}).waitFor();
  const child=await admin.evaluate(()=>sessionStorage.getItem('hiatlas.privileged-context.v1'));
  const grant=await api(admin,'/grants/context',undefined,child);assert.equal(grant.status,200);assert.equal(grant.body.grant_type,'MAINTENANCE');
  stage='Server preview does not mutate and atomic committed correction';
  await admin.getByLabel('Novo nome',{exact:true}).fill('Nome corrigido controlado');
  await admin.getByLabel('Motivo da correção',{exact:true}).fill('Ajuste confirmado na fixture controlada');
  await admin.getByLabel('Referência da correção',{exact:true}).fill('SUP-TEST-010');
  await admin.getByRole('button',{name:'Consultar prévia',exact:true}).click();
  await admin.getByRole('heading',{name:'Antes',exact:true}).waitFor();await admin.getByRole('heading',{name:'Depois',exact:true}).waitFor();
  assert.equal(JSON.parse(fixture('inspect',{id:ids.node_a})).version,1);
  await shot(admin,'correction-preview-light');
  await admin.getByRole('button',{name:'Revisar confirmação',exact:true}).click();
  await admin.getByRole('dialog',{name:'Confirmar correção de manutenção',exact:true}).waitFor();await shot(admin,'correction-confirmation');
  await admin.getByRole('button',{name:'Confirmar correção',exact:true}).click();
  await admin.getByText('Correção concluída e auditada.',{exact:true}).waitFor();
  const first=JSON.parse(fixture('inspect',{id:ids.node_a}));assert.equal(first.version,2);assert.equal(first.name,'Nome corrigido controlado');
  stage='Concurrent second connection invalidates preview with409';
  await admin.getByLabel('Novo nome',{exact:true}).fill('Nome após revisão de conflito');
  await admin.getByRole('button',{name:'Consultar prévia',exact:true}).click();await admin.getByRole('heading',{name:'Antes',exact:true}).waitFor();
  fixture('conflict',{id:ids.node_a});
  await admin.getByRole('button',{name:'Revisar confirmação',exact:true}).click();await admin.getByRole('button',{name:'Confirmar correção',exact:true}).click();
  await admin.getByText('Os dados foram alterados desde a sua revisão.',{exact:true}).waitFor();
  assert.equal(JSON.parse(fixture('inspect',{id:ids.node_a})).version,3);await admin.evaluate(()=>window.scrollTo(0,0));await shot(admin,'correction-conflict');
  await admin.getByRole('button',{name:'Atualizar e revisar novamente',exact:true}).click();
  await admin.getByRole('button',{name:'Consultar prévia',exact:true}).click();
  await admin.getByRole('heading',{name:'Antes',exact:true}).waitFor();
  await admin.getByRole('button',{name:'Revisar confirmação',exact:true}).click();await admin.getByRole('button',{name:'Confirmar correção',exact:true}).click();
  await admin.getByText('Correção concluída e auditada.',{exact:true}).waitFor();assert.equal(JSON.parse(fixture('inspect',{id:ids.node_a})).version,4);
  stage='Known processing reprocess has one effective run for repeatedkey';
  await admin.getByRole('button',{name:'Reprocessar',exact:true}).click();
  await admin.getByLabel('Motivo do reprocessamento',{exact:true}).fill('Repetição controlada após correção');
  await admin.getByLabel('Referência do reprocessamento',{exact:true}).fill('SUP-TEST-010');
  await admin.getByRole('button',{name:'Revisar reprocessamento',exact:true}).click();await shot(admin,'reprocess-confirmation');
  await admin.getByRole('button',{name:'Confirmar reprocessamento',exact:true}).click();
  await admin.getByText('Reprocessamento concluído e auditado.',{exact:true}).waitFor();
  assert.equal(replayPayloads.length,1);
  const effect=JSON.parse(fixture('inspect',{id:ids.node_a,source:source.id}));assert.equal(effect.version,5);assert.equal(effect.reprocess_count,1);
  const repeated=await api(admin,'/processings/'+source.id+'/reprocess',replayPayloads[0],child);assert([200,201,202].includes(repeated.status));assert.equal(repeated.body.status,'SUCCEEDED');assert.equal(repeated.body.source_run_id,source.id);
  const newIntent={...replayPayloads[0],idempotency_key:'new-intent-blocked-010'};assert.equal((await api(admin,'/processings/'+source.id+'/reprocess',newIntent,child)).status,409);
  await admin.reload();await banner.waitFor();await admin.getByText('2 processamentos',{exact:true}).waitFor();assert.equal(await admin.getByRole('button',{name:'Reprocessar',exact:true}).count(),0);
  assert.equal(JSON.parse(fixture('inspect',{id:ids.node_a,source:source.id})).reprocess_count,1);
  await admin.getByRole('button',{name:'Tema escuro',exact:true}).click();await shot(admin,'maintenance-dark');
  await admin.setViewportSize({width:390,height:844});await noOverflow(admin);await shot(admin,'maintenance-mobile');
  await admin.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));const bounds=await banner.boundingBox();assert(bounds&&bounds.y>=0&&bounds.y<500);
  stage='Mobile keyboard focus stays outside sticky banner';
  await admin.getByLabel('Novo nome',{exact:true}).focus();const fieldBounds=await admin.getByLabel('Novo nome',{exact:true}).boundingBox();const focusBanner=await banner.boundingBox();assert(fieldBounds&&focusBanner&&fieldBounds.y>=focusBanner.y+focusBanner.height,'Focused field obscured by sticky context');await shot(admin,'maintenance-mobile-focus');
  stage='A/A2/B scopes and manual mutations remainclosed';
  const scopePage=await pageIn(adminContext);await scopePage.goto(origin+'/e2e/phase10-controlled.html');await scopePage.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();
  const foreign=await select(scopePage,'CTR-A2');
  assert([403,404].includes((await api(scopePage,'/maintenance/preview',{action_code:'FIXTURE_NODE_RENAME',entity_id:ids.node_a,expected_version:5,proposed_input:{name:'Forbidden'},reason:'Operação externa negada',reference:'SUP-TEST-010'},foreign)).status));
  assert([403,404].includes((await api(scopePage,'/processings/'+source.id,undefined,foreign)).status));
  assert.equal((await api(admin,'/maintenance/preview',{action_code:'FIXTURE_NODE_RENAME',entity_id:ids.node_b,expected_version:1,proposed_input:{name:'Forbidden'},reason:'Operação externa negada',reference:'SUP-TEST-010'},child)).status,403);
  assert.equal((await api(admin,'/memberships/'+ids.member_a+'/status',{active:false,expected_version:1},child,'PATCH')).status,403);
  assert.equal((await api(admin,'/maintenance/preview',{action_code:'update_whatever',entity_id:ids.node_a,expected_version:5,proposed_input:{sql:'forbidden'},reason:'Operação desconhecida negada'},child)).status,403);
  const bPage=await pageIn(adminContext);await bPage.goto(origin+'/e2e/phase10-controlled.html');await bPage.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();const contextB=await select(bPage,'CTR-B');
  assert.equal((await api(bPage,'/maintenance/corrections',{action_code:'FIXTURE_NODE_RENAME',entity_id:ids.node_a,expected_version:5,proposed_input:{name:'Forbidden'},reason:'Correção cruzada negada',preview_receipt:'invalid-foreign-receipt'},contextB)).status,403);
  assert([403,404].includes((await api(bPage,'/grants',{grant_type:'MAINTENANCE',reason:'Escopo cruzado negado',reference:'SUP-TEST-010',scopes:[{action_code:'FIXTURE_NODE_RENAME',entity_type:'organization_node',entity_id:ids.node_a}]},contextB)).status));
  await scopePage.close();
  stage='Keyboard end restoresnormal and contextualaudit verifies commits';
  await admin.getByRole('button',{name:'Encerrar acesso temporário',exact:true}).focus();await admin.keyboard.press('Enter');await admin.getByRole('dialog').waitFor();await shot(admin,'maintenance-end-confirmation');
  await admin.keyboard.press('Escape');await admin.getByRole('dialog').waitFor({state:'hidden'});
  await admin.getByRole('button',{name:'Encerrar acesso temporário',exact:true}).click();await admin.getByRole('button',{name:'Confirmar encerramento',exact:true}).click();await banner.waitFor({state:'hidden'});
  assert.equal((await api(admin,'/processings/'+source.id,undefined,child)).status,403);
  const audit=await api(admin,'/audit?limit=100',undefined,parent);assert.equal(audit.status,200);
  assert(audit.body.items.some(item=>item.action.includes('correction')));assert(audit.body.items.some(item=>item.action==='maintenance.processing.succeeded'));
  const event=audit.body.items.find(item=>item.action.includes('correction'));
  const detail=await api(admin,'/audit/'+event.id,undefined,parent);assert.equal(detail.status,200);assert(detail.body.before&&detail.body.after);
  const foreignAudit=await api(bPage,'/audit/'+event.id,undefined,contextB);assert([403,404].includes(foreignAudit.status));await bPage.close();
  await storageSafe(admin);
 }
 stage='Support forbidden maintenance API andnomenu';
 const[supportContext,support]=await fresh();await login(support,'support@example.test');const supportParent=await select(support,'CTR-A');
 assert.equal(await support.getByRole('button',{name:'Manutenção',exact:true}).count(),0);
 assert.equal((await api(support,'/maintenance',undefined,supportParent)).status,403);
 assert.equal((await api(support,'/maintenance/preview',{action_code:'FIXTURE_NODE_RENAME',entity_id:ids.node_a,expected_version:1,proposed_input:{name:'Forbidden'},reason:'Operação de suporte negada'},supportParent)).status,403);
 await shot(support,controlled?'support-controlled-denied':'support-normal-denied');await storageSafe(support);
 await supportContext.close();await adminContext.close();assert.equal(errors.length,0);assert.equal(unsafe.length,0);
 console.log('[PASS] Phase10 '+(controlled?'controlled correction/conflict/reprocess/idempotency/audit/scopes':'normal empty registry')+' real Admin/Support E2E; light/dark/mobile/keyboard/storage');
}catch(error){
 if(diagnosticPage)await diagnosticPage.screenshot({path:path.join(process.env.HIATLAS_E2E_STATE,'phase10-failure.png'),fullPage:false}).catch(()=>{});
 const line=/phase10\.mjs:(\d+):/.exec(error?.stack||'')?.[1]||'unknown';
 console.error('[FAIL] Phase10 E2E at sanitized '+stage+'; '+(error?.name||'Error')+'; harness line '+line+'; sensitive diagnostics suppressed');
 process.exitCode=1;
}finally{await browser.close();}
