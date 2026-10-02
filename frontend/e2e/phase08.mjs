// Controlled real Phase8 E2E; no mocked HTTP, demo workspace or external SMTP.
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.HIATLAS_PLAYWRIGHT_MODULE||'playwright');
const origin=process.env.HIATLAS_E2E_ORIGIN,password=process.env.HIATLAS_E2E_PASSWORD;
assert(origin&&password,'Controlled environment required');
const output=path.resolve('../docs/superpowers/validation/hiatlas-platform/phase-08-visual');
mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,channel:'chrome'});
let stage='startup';
const errors=[],unsafe=[];
function fixture(action,id){
 try{return execFileSync(path.resolve('../backend/.venv/Scripts/python.exe'),[path.resolve('../scripts/phase08_browser_fixture.py'),action,...(id?['--id',id]:[])],{cwd:path.resolve('..'),encoding:'utf8',stdio:'pipe'}).trim();}
 catch{throw new Error('Controlled fixture failure; sensitive diagnostics suppressed');}
}
async function pageIn(context){
 const page=await context.newPage();
 page.on('pageerror',()=>errors.push('pageerror'));
 page.on('request',r=>{const u=new URL(r.url());if(u.origin!==origin||u.searchParams.has('token'))unsafe.push('unsafe');});
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
   const csrfResponse=await fetch('/api/auth/csrf');
   if(!csrfResponse.ok)return{status:csrfResponse.status,body:null};
   headers['X-CSRF-Token']=(await csrfResponse.json()).token;
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
async function startUi(page,parent,name='support-start'){
 await page.getByRole('button',{name:'Usuários',exact:true}).click();
 await page.getByLabel('Nome ou e-mail',{exact:true}).fill('member@example.test');
 await page.getByRole('button',{name:'Pesquisar usuários',exact:true}).click();
 await page.getByRole('button',{name:'Detalhes de Pessoa visualizada',exact:true}).click();
 await page.getByRole('button',{name:'Iniciar sessão de suporte',exact:true}).click();
 const dialog=page.getByRole('dialog');
 await dialog.getByLabel('Motivo do atendimento',{exact:true}).fill('Usuário relata módulo indisponível.');
 await dialog.getByLabel('Referência do chamado (opcional)',{exact:true}).fill('SUP-TEST-008');
 await shot(page,name);
 await dialog.getByRole('button',{name:'Confirmar início somente leitura',exact:true}).click();
 await page.getByRole('region',{name:'Sessão de suporte somente leitura',exact:true}).waitFor();
 await page.waitForFunction(()=>document.querySelector('[aria-label="Sessão de suporte somente leitura"]')===document.activeElement);
 assert(await page.getByRole('region',{name:'Sessão de suporte somente leitura',exact:true}).evaluate(element=>element===document.activeElement));
 const id=await page.evaluate(()=>sessionStorage.getItem('hiatlas.support-session.v1'));
 assert(id);
 const result=await api(page,'/support-sessions/'+id,undefined,parent);
 assert.equal(result.status,200);
 return result.body;
}
async function assertReadOnly(page,session,ids){
 const workspace=await api(page,'/support-sessions/'+session.id+'/workspace',undefined,session.context_id);
 assert.equal(workspace.status,200);assert.equal(workspace.body.effective_access.read_only,true);
 assert(workspace.body.effective_access.capabilities.every(code=>!/(finance|fiscal|manage|password|invite|status)/i.test(code)));
 assert(workspace.body.modules.every(module=>module.code!=='FINANCE'&&!module.operational_available));
 for(const contextId of [session.parent_context_id,session.context_id]){
  for(const [route,body,method] of [
   ['/memberships/'+ids.member_a+'/reset-password',{},'POST'],
   ['/memberships/'+ids.member_a+'/status',{active:false,expected_version:1},'PATCH'],
   ['/memberships/'+ids.member_a+'/role',{role_id:ids.role_basic,expected_version:1},'PUT'],
   ['/contexts/'+session.parent_context_id,undefined,'DELETE'],
   ['/tenants',{name:'Must never be created'},'POST'],
  ])assert.equal((await api(page,route,body,contextId,method)).status,403);
  assert.equal((await api(page,'/memberships?limit=20',undefined,contextId)).status,403);
 }
 assert.equal((await api(page,'/tenants',{name:'Must never be created'},undefined,'POST')).status,403);
 assert.equal(await page.getByRole('button',{name:'Novo usuário',exact:true}).count(),0);
 assert.equal(await page.getByRole('button',{name:'Trocar empresa/contrato',exact:true}).count(),0);
 assert.equal(await page.getByRole('button',{name:'Enviar link de redefinição',exact:true}).count(),0);
}
async function endUi(page,parent){
 await page.getByRole('button',{name:'Encerrar sessão de suporte',exact:true}).click();
 await shot(page,'support-end-confirmation');
 await page.getByRole('dialog').getByRole('button',{name:'Confirmar encerramento',exact:true}).click();
 await page.getByRole('region',{name:'Sessão de suporte somente leitura',exact:true}).waitFor({state:'hidden'});
 await page.getByRole('button',{name:'Usuários',exact:true}).waitFor();
 await page.waitForFunction(()=>document.querySelector('[data-support-return]')===document.activeElement);
 assert(await page.locator('[data-support-return]').evaluate(element=>element===document.activeElement));
 assert.equal(await page.evaluate(()=>sessionStorage.getItem('hiatlas.support-session.v1')),null);
 assert.equal((await api(page,'/memberships?limit=20',undefined,parent)).status,200);
}
try{
 const ids=JSON.parse(fixture('seed'));
 const[supportContext,support]=await fresh();
 stage='support login and selected membership';await login(support,'support@example.test');const parent=await select(support,'CTR-A');
 for(const foreignMember of [ids.member_a2,ids.member_b])assert.equal((await api(support,'/support-sessions',{membership_id:foreignMember,reason:'Atendimento em contrato incorreto'},parent)).status,404);
 stage='prepare independent normal tabs before suspending support parent';const tab2=await pageIn(supportContext);await tab2.goto(origin);await tab2.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();const a2=await select(tab2,'CTR-A2');
 const tabB=await pageIn(supportContext);await tabB.goto(origin);await tabB.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();const b=await select(tabB,'CTR-B');
 const realCookie=(await supportContext.cookies()).find(cookie=>cookie.name==='__Host-hiatlas-session')?.value;
 const session=await startUi(support,parent);assert.equal(session.mode,'READ_ONLY');
 assert.equal(session.viewed.membership_id,ids.member_a);assert.equal(session.operator.user_id,ids.support_user);assert.notEqual(session.operator.user_id,session.viewed.user_id);
 assert.equal((await supportContext.cookies()).find(cookie=>cookie.name==='__Host-hiatlas-session')?.value,realCookie);
 stage='support real workspace and direct denials';await assertReadOnly(support,session,ids);
 await support.getByRole('heading',{name:'Ambiente do usuário',exact:true}).waitFor();
 await shot(support,'support-readonly-light');
 stage='reload and sticky banner';await support.reload();await support.getByRole('region',{name:'Sessão de suporte somente leitura',exact:true}).waitFor();
 await support.getByRole('heading',{name:'Ambiente do usuário',exact:true}).waitFor();
 await support.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
 const bounds=await support.getByRole('region',{name:'Sessão de suporte somente leitura',exact:true}).boundingBox();assert(bounds&&bounds.y>=0&&bounds.y<500);
 await support.getByRole('button',{name:'Tema escuro'}).click();await shot(support,'support-readonly-dark');
 await support.setViewportSize({width:390,height:844});assert(await support.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot(support,'support-readonly-mobile');await support.setViewportSize({width:1440,height:1000});
 stage='same HTTP independent second tab and scope isolation';await tab2.reload();await tab2.getByTestId('contract-context').getByText('CTR-A2',{exact:true}).waitFor();
 assert.equal((await api(tab2,'/memberships?limit=20',undefined,a2)).status,200);
 assert([403,404].includes((await api(tab2,'/support-sessions/'+session.id,undefined,a2)).status));
 assert([403,404].includes((await api(tab2,'/support-sessions',{membership_id:ids.member_b,reason:'Atendimento fora do contrato'},a2)).status));
 assert([403,404].includes((await api(support,'/support-sessions',{membership_id:ids.member_a2,reason:'Atendimento fora do contrato'},parent)).status));
 assert.equal((await api(support,'/support-sessions/'+session.id+'/workspace',undefined,session.context_id)).status,200);
 assert.equal(await tab2.evaluate(()=>sessionStorage.getItem('hiatlas.support-session.v1')),null);
 stage='independent Contract B cannot reveal Contract A';await tabB.reload();await tabB.getByTestId('contract-context').getByText('CTR-B',{exact:true}).waitFor();
 assert.equal((await api(tabB,'/memberships?limit=20',undefined,b)).status,200);
 assert.equal((await api(tabB,'/memberships/'+ids.member_a,undefined,b)).status,404);
 assert([403,404].includes((await api(tabB,'/support-sessions/'+session.id,undefined,b)).status));
 assert.equal((await api(support,'/support-sessions/'+session.id+'/workspace',undefined,session.context_id)).status,200);
 stage='new HTTP session same operator cannot restore';const[otherContext,other]=await fresh();await login(other,'support@example.test');const otherParent=await select(other,'CTR-A');
 assert([403,404].includes((await api(other,'/support-sessions/'+session.id,undefined,session.context_id)).status));
 assert([403,404].includes((await api(other,'/support-sessions/'+session.id,undefined,otherParent)).status));await otherContext.close();
 stage='manual end and history';await endUi(support,parent);assert.equal((await api(support,'/support-sessions/'+session.id+'/end',{},parent,'POST')).status,204);
 await support.getByRole('button',{name:'Sessões de suporte',exact:true}).click();const history=await api(support,'/support-sessions?limit=20',undefined,parent);assert.equal(history.status,200);assert(history.body.items.some(row=>row.id===session.id&&row.status==='ENDED'));assert(history.body.items.every(row=>!('context_id'in row)&&!('parent_context_id'in row)));await shot(support,'support-history-dark');
 stage='support expiry and safe return';const expiring=await startUi(support,parent,'support-expiry-start');fixture('expire',expiring.id);assert([403,404].includes((await api(support,'/support-sessions/'+expiring.id+'/workspace',undefined,expiring.context_id)).status));await support.reload();await support.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();await shot(support,'support-expired');
 stage='admin same read-only restriction';const[adminContext,admin]=await fresh();await login(admin,'admin@example.test');const adminParent=await select(admin,'CTR-A');const adminSession=await startUi(admin,adminParent,'admin-start');assert.equal(adminSession.operator.platform_role,'PLATFORM_ADMIN');await assertReadOnly(admin,adminSession,ids);await shot(admin,'admin-readonly-light');
 stage='admin keyboard and end';await admin.getByRole('button',{name:'Encerrar sessão de suporte',exact:true}).focus();await admin.keyboard.press('Enter');await admin.getByRole('dialog').waitFor();await admin.keyboard.press('Escape');assert(await admin.getByRole('button',{name:'Encerrar sessão de suporte',exact:true}).evaluate(element=>element===document.activeElement));await endUi(admin,adminParent);
 stage='revoked parent clears viewed data';const revoked=await startUi(admin,adminParent,'admin-revocation-start');fixture('revoke-context',revoked.parent_context_id);await admin.evaluate(()=>window.dispatchEvent(new Event('focus')));await admin.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();await shot(admin,'support-access-denied');
 stage='storage and browser errors';for(const context of [supportContext,adminContext])for(const page of context.pages()){const stores=await page.evaluate(()=>({local:Object.keys(localStorage),session:Object.keys(sessionStorage)}));assert(stores.local.every(key=>key==='hiatlas-theme'));assert(stores.session.every(key=>['hiatlas.access-context.v1','hiatlas.support-session.v1'].includes(key)));}assert.equal(errors.length,0);assert.equal(unsafe.length,0);
 console.log('PASS Phase8: Support/Admin READ_ONLY with real operator and unchanged authentication; child/parent/contextless direct mutations denied; reload, independent tabs, exact HTTP binding, A/A2/B references, manual end/history/expiry, real unavailable workspace, sticky banner/themes/mobile/keyboard; PostgreSQL/FastAPI/React/Chrome and fake email, no external SMTP.');
}catch{
 const page=browser.contexts().at(-1)?.pages().at(-1);if(page)await page.screenshot({path:path.join(process.env.HIATLAS_E2E_STATE,'phase08-failure.png'),fullPage:true}).catch(()=>{});
 console.error('FAIL Phase8 E2E at '+stage+' (sensitive diagnostics suppressed)');process.exitCode=1;
}finally{await browser.close();}
