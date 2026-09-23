// Real HTTPS/API/PostgreSQL acceptance checks. No route mocks or production data.
import { createRequire } from 'node:module'
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
const require=createRequire(import.meta.url)
const {chromium}=require(process.env.HIATLAS_PLAYWRIGHT_MODULE || 'playwright')
const origin=process.env.HIATLAS_E2E_ORIGIN || 'https://localhost:5175'
const output=path.resolve(process.env.HIATLAS_E2E_OUTPUT || '../docs/superpowers/validation/hiatlas-platform/phase-04-visual')
const password=process.env.HIATLAS_E2E_PASSWORD
assert(password,'Set HIATLAS_E2E_PASSWORD for disposable identities')
mkdirSync(output,{recursive:true})
const browser=await chromium.launch({headless:true,channel:'chrome'})
// Only the disposable localhost certificate is self-signed; no application protection is relaxed.
const context=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1000}})
const page=await context.newPage()
const errors=[]
page.on('pageerror',e=>errors.push(e.message))
const key='hiatlas.access-context.v1'
async function shot(name,target=page){await target.locator('img').evaluateAll(images=>Promise.all(images.map(img=>img.decode().catch(()=>{}))));await target.screenshot({path:path.join(output,`${name}.png`),fullPage:true})}
async function login(target,email='admin@example.test'){
 await target.getByLabel('E-mail',{exact:true}).fill(email)
 await target.getByLabel('Senha',{exact:true}).fill(password)
 await target.getByRole('button',{name:'Entrar no HiAtlas',exact:true}).click()
 await target.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor()
}
async function select(target,code='CTR-2026-001'){
 await target.getByRole('button',{name:`Acessar contrato ${code}`,exact:true}).click()
 await target.getByTestId('contract-context').waitFor()
 assert((await target.getByTestId('contract-context').innerText()).includes(code))
}
function fixture(action,id){
 const python=path.resolve('../backend/.venv/Scripts/python.exe')
 const args=[path.resolve('../scripts/phase04-browser-fixture.py'),action]
 if(id)args.push('--context-id',id)
 execFileSync(python,args,{cwd:path.resolve('..'),stdio:'pipe'})
}
try{
 // Wait for the independently started API/proxy before exercising login.
 let ready=false
 for(let attempt=0;attempt<60;attempt++){
  const response=await context.request.get(origin + '/api/auth/me').catch(()=>null)
  if(response?.status()===401){ready=true;break}
  await new Promise(resolve=>setTimeout(resolve,500))
 }
 assert(ready,'HTTPS API must be ready before browser acceptance checks')
 await page.goto(origin)
 await page.getByLabel('E-mail',{exact:true}).waitFor()
 assert.equal(await page.getByRole('combobox').count(),0)
 await shot('login-light')
 await page.setViewportSize({width:390,height:844});await shot('login-mobile');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await page.setViewportSize({width:1440,height:1000})
 await page.getByRole('button',{name:'Tema escuro'}).click();await shot('login-dark')
 await page.getByLabel('E-mail',{exact:true}).fill('unknown@example.test')
 await page.getByLabel('Senha',{exact:true}).fill('invalid')
 await page.getByRole('button',{name:'Entrar no HiAtlas',exact:true}).click()
 await page.getByText('E-mail ou senha inválidos.',{exact:true}).waitFor()
 await login(page)
 await page.getByRole('button',{name:'Acessar contrato CTR-2026-001',exact:true}).waitFor()
 await shot('selection-dark')
 await page.getByRole('button',{name:'Tema claro'}).click();await shot('selection-light')
 await page.setViewportSize({width:390,height:844});await shot('selection-mobile');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await page.setViewportSize({width:1440,height:1000})
 await page.getByLabel('Pesquisar empresa ou código do contrato').fill('does-not-exist')
 await page.getByText('Nenhum contrato disponível para esta pesquisa.',{exact:true}).waitFor()
 await page.getByLabel('Pesquisar empresa ou código do contrato').fill('')
 await select(page)
 await page.getByRole('heading',{name:'Administração HiAtlas',exact:true}).waitFor()
 await shot('admin-light')
 await page.getByRole('button',{name:'Tema escuro'}).click();await shot('admin-dark')
 const idA=await page.evaluate(k=>sessionStorage.getItem(k),key)
 assert(idA)
 assert.equal(await page.evaluate(k=>localStorage.getItem(k),key),null)
 const cookies=await context.cookies()
 const session=cookies.find(c=>c.name==='__Host-hiatlas-session')
 assert(session?.secure&&session?.httpOnly&&session?.sameSite==='Strict')
 await page.reload();await page.getByTestId('contract-context').waitFor()
 assert.equal(await page.evaluate(k=>sessionStorage.getItem(k),key),idA)
 const tab=await context.newPage();await tab.goto(origin)
 await tab.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor();await select(tab,'CTR-B')
 const idB=await tab.evaluate(k=>sessionStorage.getItem(k),key)
 assert.notEqual(idA,idB)
 assert.equal(await page.evaluate(k=>sessionStorage.getItem(k),key),idA)
 await shot('second-tab',tab)
 await page.getByRole('button',{name:'Trocar empresa/contrato',exact:true}).click()
 await page.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor()
 assert.equal(await page.evaluate(k=>sessionStorage.getItem(k),key),null)
 const oldStatus=await page.evaluate(async id=>(await fetch('/api/context',{headers:{'X-HiAtlas-Context':id}})).status,idA)
 assert.equal(oldStatus,403)
 assert.equal(await tab.evaluate(k=>sessionStorage.getItem(k),key),idB)
 assert.equal(await tab.evaluate(async id=>(await fetch('/api/context',{headers:{'X-HiAtlas-Context':id}})).status,idB),200)
 await select(page,'CTR-A2')
 await page.setViewportSize({width:390,height:844});await shot('admin-mobile')
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth))
 await page.setViewportSize({width:390,height:400});await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));assert((await page.getByTestId('contract-context').boundingBox()).y>=0);await page.setViewportSize({width:1440,height:1000})
 const current=await page.evaluate(k=>sessionStorage.getItem(k),key)
 fixture('invalidate',current)
 await page.reload();await page.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor()
 assert.equal(await page.evaluate(k=>sessionStorage.getItem(k),key),null)
 await shot('invalid-context')
 await page.evaluate(k=>sessionStorage.setItem(k,'malformed'),key)
 await page.reload();await page.getByRole('heading',{name:'Selecionar ambiente',exact:true}).waitFor()
 assert.equal(await page.evaluate(k=>sessionStorage.getItem(k),key),null)
 await select(page)
 fixture('expire')
 await page.reload();await page.getByLabel('E-mail',{exact:true}).waitFor()
 assert.equal(await page.evaluate(k=>sessionStorage.getItem(k),key),null)
 await shot('expired-session')
 await login(page,'support@example.test');await select(page)
 await page.getByRole('heading',{name:'Suporte HiAtlas',exact:true}).waitFor()
 await page.getByRole('button',{name:'Tema claro'}).click();await shot('support-light')
 await page.getByRole('button',{name:'Tema escuro'}).click();await shot('support-dark')
 // Local presentation changes cannot grant server capabilities.
 const denied=await page.evaluate(async()=>{
  localStorage.setItem('platform_role','PLATFORM_ADMIN')
  const {token}=await (await fetch('/api/auth/csrf')).json()
  return (await fetch('/api/tenants',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':token,'X-Platform-Role':'PLATFORM_ADMIN'},body:JSON.stringify({name:'Forbidden from support'})})).status
 })
 assert.equal(denied,403)
 await page.getByRole('button',{name:'Sair',exact:true}).click()
 await page.getByLabel('E-mail',{exact:true}).waitFor()
 assert.equal(await page.evaluate(async()=>(await fetch('/api/auth/me')).status),401)
 assert.equal(await page.evaluate(k=>sessionStorage.getItem(k),key),null)
 await page.goto(`${origin}/demo`);await page.getByLabel('E-mail',{exact:true}).waitFor()
 assert.equal(await page.getByRole('combobox').count(),0)
 await page.getByLabel('E-mail',{exact:true}).focus();assert.equal(await page.getByLabel('E-mail',{exact:true}).evaluate(el=>el===document.activeElement),true)
 await page.keyboard.press('Tab');assert.equal(await page.getByLabel('Senha',{exact:true}).evaluate(el=>el===document.activeElement),true)
 assert.deepEqual(errors,[])
 console.log('PASS: real login, neutral errors, admin/support, HTTPS cookies, CSRF, search/empty, restore, two tabs, server close, invalid context, malformed context, expired session, denied role escalation, logout, demo disabled, light/dark, mobile, keyboard; no page errors.')
}finally{await browser.close()}
