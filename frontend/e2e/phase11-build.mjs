// Real production bundle under the actual HTML/asset CSP, without API mocks or seed.
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.HIATLAS_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,channel:'chrome'});
try{
 const context=await browser.newContext({ignoreHTTPSErrors:true});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',()=>errors.push('pageerror'));
 await page.addInitScript(()=>{window.__phase11CspViolations=[];document.addEventListener('securitypolicyviolation',event=>window.__phase11CspViolations.push(event.violatedDirective));});
 const response=await page.goto(process.env.HIATLAS_E2E_ORIGIN);assert.equal(response.status(),200);
 const expected="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'";
 for(const [key,value] of Object.entries({'content-security-policy':expected,'referrer-policy':'no-referrer','x-content-type-options':'nosniff','x-frame-options':'DENY','strict-transport-security':'max-age=31536000'}))assert.equal(response.headers()[key],value);
 await page.getByLabel('E-mail',{exact:true}).waitFor();
 const scripts=await page.locator('script[src]').evaluateAll(nodes=>nodes.map(node=>new URL(node.src).pathname));assert(scripts.length>0&&scripts.every(value=>value.startsWith('/assets/')&&value.endsWith('.js')));
 for(const script of scripts){const asset=await context.request.get(process.env.HIATLAS_E2E_ORIGIN+script);assert.equal(asset.status(),200);assert.equal(asset.headers()['x-content-type-options'],'nosniff');assert.equal(asset.headers()['content-security-policy'],expected);const body=await asset.text();assert(!body.includes('FIXTURE_NODE_RENAME'));}
 assert.equal(errors.length,0);assert.deepEqual(await page.evaluate(()=>window.__phase11CspViolations),[]);
 console.log('PASS production bundle HTML/assets exact CSP, referrer/nosniff/frame/HSTS, no fixture marker, no CSP violations/pageerror');
}finally{await browser.close();}
