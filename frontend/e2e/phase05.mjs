// Real HTTPS + PostgreSQL E2E. Fake delivery only; no token-bearing traces or logs.
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.HIATLAS_PLAYWRIGHT_MODULE || 'playwright');
const origin=process.env.HIATLAS_E2E_ORIGIN;
const password=process.env.HIATLAS_E2E_PASSWORD;
assert(origin && password, 'Disposable E2E origin/password required');
const output=path.resolve(process.env.HIATLAS_E2E_OUTPUT || '../docs/superpowers/validation/hiatlas-platform/phase-05-visual');
mkdirSync(output,{recursive:true});
function fixture(action, recipient){
 const args=[path.resolve('../scripts/phase05_browser_fixture.py'),action];
 if(recipient)args.push('--recipient',recipient);
 try {return execFileSync(path.resolve('../backend/.venv/Scripts/python.exe'),args,{cwd:path.resolve('..'),stdio:'pipe',encoding:'utf8'}).trim();}
 catch {throw new Error('Controlled fixture failed (details withheld to protect delivery content)');}
}
function deliveryLink(recipient){
 const {text}=JSON.parse(fixture('deliver',recipient));
 const link=text.split(/\s+/).find(word=>word.startsWith(origin+'/'));
 if(!link)throw new Error('Controlled email lacks expected public-origin link');
 return link;
}
const browser=await chromium.launch({headless:true,channel:'chrome'});
const errors=[];
const unsafeRequests=[];
let stage='startup';
const options={ignoreHTTPSErrors:true,viewport:{width:1440,height:1000}};
async function fresh(){const ctx=await browser.newContext(options);const p=await ctx.newPage();p.on('pageerror',()=>errors.push('pageerror'));p.on('request',r=>{const u=new URL(r.url());if(u.origin!==origin||u.searchParams.has('token'))unsafeRequests.push('unsafe request');});return [ctx,p];}
async function shot(p,name){await p.locator('img').evaluateAll(images=>Promise.all(images.map(img=>img.decode().catch(()=>{}))));await p.screenshot({path:path.join(output,name+'.png'),fullPage:true});}
async function api(p,route,body,contextId){
 return p.evaluate(async ({route,body,contextId})=>{
  const headers={'Content-Type':'application/json'};
  if(contextId)headers['X-HiAtlas-Context']=contextId;
  if(body!==undefined){const csrf=await (await fetch('/api/auth/csrf')).json();headers['X-CSRF-Token']=csrf.token;}
  const r=await fetch('/api'+route,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body)});
  return {status:r.status,body:r.status===204?null:await r.json()};
 },{route,body,contextId});
}
async function login(p,email,pw= password){
 await p.getByLabel('E-mail',{exact:true}).fill(email);
 await p.getByLabel('Senha',{exact:true}).fill(pw);
 await p.getByRole('button',{name:'Entrar no HiAtlas',exact:true}).click();
}
async function assertSecretAbsent(p,secret){
 const state=await p.evaluate(()=>({url:location.href,local:JSON.stringify(localStorage),session:JSON.stringify(sessionStorage),text:document.body.innerText,referrer:document.querySelector('meta[name="referrer"]')?.content}));
 for(const key of ['url','local','session','text'])assert(!state[key].includes(secret),'Sensitive token escaped memory');
 assert.equal(state.referrer,'no-referrer');
}
try{
 const ids=JSON.parse(fixture('seed'));
 const [oldContext,oldPage]=await fresh();
 await oldPage.goto(origin);
 await login(oldPage,'admin@example.test');
 await oldPage.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();
 const selected=await api(oldPage,'/contexts',{contract_id:ids.contract_a});
 assert.equal(selected.status,201);
 const oldContextId=selected.body.id;
 const [resetContext,page]=await fresh();
 stage='neutral recovery and theme/mobile';
 await page.goto(origin);
 await page.getByRole('link',{name:'Esqueci minha senha',exact:true}).click();
 await page.getByLabel('E-mail',{exact:true}).fill('admin@example.test');
 await page.getByRole('button',{name:'Solicitar recuperação',exact:true}).click();
 await page.getByText(/Se houver uma conta elegível/).waitFor();
 await shot(page,'recovery-requested-light');
 const unknown=await api(page,'/auth/recovery',{email:'absent@example.test'});
 const known=await api(page,'/auth/recovery',{email:'admin@example.test'});
 assert.equal(unknown.status,known.status);assert.deepEqual(unknown.body,known.body);
 await page.getByRole('button',{name:'Tema escuro'}).click();await shot(page,'recovery-requested-dark');
 await page.setViewportSize({width:390,height:844});await shot(page,'recovery-mobile');
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 stage='consume reset and revoke old sessions';
 const link=deliveryLink('admin@example.test');const resetToken=new URLSearchParams(new URL(link).hash.slice(1)).get('token');
 await page.goto(link);
 await page.getByLabel('Nova senha',{exact:true}).waitFor();
 await assertSecretAbsent(page,resetToken);
 await shot(page,'reset-mobile-dark');
 const newPassword=password+'-renewed';
 await page.getByLabel('Nova senha',{exact:true}).fill(newPassword);
 await page.getByLabel('Confirmar nova senha',{exact:true}).fill(newPassword);
 await page.getByRole('button',{name:'Redefinir senha',exact:true}).click();
 await page.getByText('Senha redefinida.',{exact:true}).waitFor();await shot(page,'reset-complete');
 assert.equal((await api(oldPage,'/auth/me')).status,401);
 assert.notEqual((await api(oldPage,'/context',undefined,oldContextId)).status,200);
 await page.getByRole('link',{name:'Voltar ao login',exact:true}).click();
 await login(page,'admin@example.test',newPassword);
 await page.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();
 stage='issue and accept invitation';
 const scope=await api(page,'/contexts',{contract_id:ids.contract_a});assert.equal(scope.status,201);
 const invitation=await api(page,'/memberships',{email:'invited@example.test',display_name:'Convidado de teste',role_id:ids.role_basic},scope.body.id);
 assert.equal(invitation.status,202);
 const pendingMembers=await api(page,'/memberships?search=invited%40example.test',undefined,scope.body.id);
 assert.equal(pendingMembers.status,200);assert.equal(pendingMembers.body.items.length,1);assert.equal(pendingMembers.body.items[0].invitation_pending,true);
 const inviteLink=deliveryLink('invited@example.test');const inviteToken=new URLSearchParams(new URL(inviteLink).hash.slice(1)).get('token');
 const [inviteContext,invitePage]=await fresh();
 await invitePage.goto(inviteLink);
 await invitePage.getByLabel('Nova senha',{exact:true}).waitFor();
 await assertSecretAbsent(invitePage,inviteToken);
 await shot(invitePage,'invite-light');
 await invitePage.getByRole('button',{name:'Tema escuro'}).click();await shot(invitePage,'invite-dark');
 await invitePage.setViewportSize({width:390,height:844});await shot(invitePage,'invite-mobile');
 assert(await invitePage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await invitePage.getByLabel('Nova senha',{exact:true}).focus();assert(await invitePage.getByLabel('Nova senha',{exact:true}).evaluate(el=>el===document.activeElement));
 await invitePage.getByLabel('Nova senha',{exact:true}).fill(newPassword);
 await invitePage.getByLabel('Confirmar nova senha',{exact:true}).fill(newPassword);
 await invitePage.getByRole('button',{name:'Aceitar convite',exact:true}).click();
 await invitePage.getByText('Convite aceito.',{exact:true}).waitFor();await shot(invitePage,'invite-complete');
 await assertSecretAbsent(invitePage,inviteToken);
 await invitePage.getByRole('link',{name:'Voltar ao login',exact:true}).click();
 await login(invitePage,'invited@example.test',newPassword);
 await invitePage.getByRole('heading',{name:'Acesso indisponível',exact:true}).waitFor();
 assert.equal((await api(invitePage,'/auth/me')).status,200);
 stage='reject invitation replay';
 await invitePage.goto(inviteLink);
 await invitePage.getByText(/Link inválido/).waitFor();await shot(invitePage,'invite-reused');
 stage='reject expired reset';
 assert.equal((await api(page,'/auth/recovery',{email:'admin@example.test'})).status,202);
 const expiredLink=deliveryLink('admin@example.test');fixture('expire');
 await invitePage.goto(expiredLink);await invitePage.getByText(/Link expirado/).waitFor();await shot(invitePage,'token-expired');
 stage='email unavailable without false success';
 fixture('email-off');
 await invitePage.goto(origin+'/password/forgot');
 await invitePage.getByLabel('E-mail',{exact:true}).fill('admin@example.test');
 await invitePage.getByRole('button',{name:'Solicitar recuperação',exact:true}).click();
 await invitePage.getByText('Serviço de e-mail indisponível. Tente novamente mais tarde.',{exact:true}).waitFor();
 await shot(invitePage,'email-unavailable');
 const unavailableKnown=await api(invitePage,'/auth/recovery',{email:'admin@example.test'});
 const unavailableUnknown=await api(invitePage,'/auth/recovery',{email:'unknown@example.test'});
 assert.equal(unavailableKnown.status,503);assert.equal(unavailableUnknown.status,503);
 assert.equal(unavailableKnown.body.code,unavailableUnknown.body.code);assert.equal(unavailableKnown.body.message,unavailableUnknown.body.message);
 fixture('email-on');
 assert.deepEqual(errors,[]);assert.deepEqual(unsafeRequests,[]);
 await oldContext.close();await resetContext.close();await inviteContext.close();
 console.log('PASS: recovery neutral; reset consumed; new-password login; old session/context denied; invitation accepted; invited login; invitation replay denied; expired token; unavailable email; token absent from URL/storage/UI; light/dark; mobile; keyboard; no page errors; fake delivery only.');
}catch{
 // Never print Playwright call logs, request payloads, URLs, tokens or passwords.
 const contexts=browser.contexts();const pages=contexts.at(-1)?.pages();const failedPage=pages?.at(-1);
 if(failedPage)await failedPage.screenshot({path:path.join(process.env.HIATLAS_E2E_STATE,'e2e-failure.png'),fullPage:true}).catch(()=>{});
 console.error('FAIL: phase05 E2E at '+stage+' (sensitive diagnostics suppressed)');
 process.exitCode=1;
}finally{fixture('email-on');await browser.close();}
