// Run against an explicitly enabled development /demo entry.
import { createRequire } from 'node:module'
import assert from 'node:assert/strict'
const {chromium}=createRequire(import.meta.url)(process.env.HIATLAS_PLAYWRIGHT_MODULE || 'playwright')
const browser=await chromium.launch({headless:true,channel:'chrome'})
try{
 const page=await browser.newPage({ignoreHTTPSErrors:true})
 let requests=0
 page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/'))requests++})
 await page.goto(`${process.env.HIATLAS_DEMO_ORIGIN || 'http://127.0.0.1:5176'}/demo`)
 await page.getByText('DEMONSTRAÇÃO — dados fictícios',{exact:true}).waitFor()
 await page.getByText('Opções de demonstração',{exact:true}).click()
 await page.getByLabel('Perfil de acesso').selectOption('administrador')
 await page.getByRole('button',{name:'Entrar no HiAtlas'}).click()
 await page.getByRole('button',{name:'Sair',exact:true}).waitFor()
 assert.equal(requests,0)
 console.log('PASS: enabled demo preserves prototype with zero API requests')
}finally{await browser.close()}
