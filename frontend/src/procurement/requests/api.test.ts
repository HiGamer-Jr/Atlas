import {afterEach,expect,it,vi} from 'vitest';
import {ApiClient} from '../../api/client';
import {purchaseRequestApi} from './api';
import {request} from './fixtures';
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});
it('actions_quantities_and_retry_keys',async()=>{
 const sent:RequestInit[]=[];let fail=true;
 vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{if(url==='/api/auth/csrf')return new Response(JSON.stringify({token:'csrf'}));sent.push(init);if(fail){fail=false;throw new TypeError('lost response');}return new Response(JSON.stringify(request()));}));
 const client=new ApiClient();client.setContext('ctx');const api=purchaseRequestApi(client);const binding={contextId:'ctx',tenantId:'tenant',contractId:'contract'};
 const body={requesting_node_id:'unit',title:'Need',items:[{description:'Need',specification:'',requested_quantity:'0.000001',uom_code:'UN' as const}]};
 await expect(api.create(binding,body)).rejects.toThrow();await api.create(binding,body);
 expect(new Headers(sent[1].headers).get('Idempotency-Key')).toBe(new Headers(sent[0].headers).get('Idempotency-Key'));expect(new Headers(sent[1].headers).get('X-HiAtlas-Context')).toBe('ctx');expect(JSON.parse(sent[1].body as string)).not.toHaveProperty('tenant_id');expect(JSON.parse(sent[1].body as string).items[0].requested_quantity).toBe('0.000001');
 await api.create(binding,{...body,title:'Other intention'});expect(new Headers(sent[2].headers).get('Idempotency-Key')).not.toBe(new Headers(sent[0].headers).get('Idempotency-Key'));
});
it('private_blob_download_revoked',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('private bytes')));const create=vi.fn(()=> 'blob:private'),revoke=vi.fn();vi.stubGlobal('URL',class extends URL {static createObjectURL=create;static revokeObjectURL=revoke;});vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
 const client=new ApiClient();client.setContext('ctx');await purchaseRequestApi(client).downloadAttachment({contextId:'ctx',tenantId:'tenant',contractId:'contract'},'request',{id:'file',filename:'evidence.txt'});expect(create).toHaveBeenCalled();expect(revoke).toHaveBeenCalledWith('blob:private');
});

it('uses approved draft and assignment routes with server versions',async()=>{
 const calls:{url:string;body:unknown}[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{if(url==='/api/auth/csrf')return new Response(JSON.stringify({token:'csrf'}));calls.push({url,body:JSON.parse(init.body as string)});return new Response(JSON.stringify(request()));}));
 const api=purchaseRequestApi(new ApiClient()),b={contextId:'ctx',tenantId:'tenant',contractId:'contract'};
 await api.updateDraft(b,'request',{expected_version:3,requesting_node_id:'unit',title:'Need',items:[]});await api.assign(b,'request',{expected_version:4,buyer_membership_id:'buyer'});
 expect(calls).toEqual([{url:'/api/procurement/requests/request/draft',body:{expected_version:3,requesting_node_id:'unit',title:'Need',items:[]}},{url:'/api/procurement/requests/request/assignment',body:{expected_version:4,buyer_membership_id:'buyer'}}]);
});
it('attachment retries bind key to bytes plus metadata and exact version',async()=>{
 const keys:string[]=[];let fail=true;vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{if(url==='/api/auth/csrf')return new Response(JSON.stringify({token:'csrf'}));keys.push(new Headers(init.headers).get('Idempotency-Key')!);expect((init.body as FormData).get('expected_version')).toBe('7');if(fail){fail=false;throw new TypeError('lost');}return new Response(JSON.stringify(request()));}));
 const api=purchaseRequestApi(new ApiClient()),b={contextId:'ctx',tenantId:'tenant',contractId:'contract'};
 const file=(content:string)=>{const f=new File([content],'evidence.txt',{type:'text/plain'});Object.defineProperty(f,'arrayBuffer',{value:async()=>new TextEncoder().encode(content).buffer});return f;};
 const first=file('original');await expect(api.addAttachment(b,'request',7,first,null)).rejects.toThrow();await api.addAttachment(b,'request',7,file('original'),null);await api.addAttachment(b,'request',7,file('different'),null);expect(keys[1]).toBe(keys[0]);expect(keys[2]).not.toBe(keys[0]);
});


it('late private download after context change never creates an object URL',async()=>{
 let complete!:(v:Response)=>void;vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(done=>{complete=done;})));const create=vi.fn(()=> 'blob:old');vi.stubGlobal('URL',class extends URL {static createObjectURL=create;static revokeObjectURL=vi.fn();});
 const client=new ApiClient();client.setContext('ctx');const pending=purchaseRequestApi(client).downloadAttachment({contextId:'ctx',tenantId:'tenant',contractId:'contract'},'request',{id:'file',filename:'private.txt'});const rejected=expect(pending).rejects.toMatchObject({name:'AbortError'});client.setContext('ctxB');complete(new Response('old bytes'));await rejected;expect(create).not.toHaveBeenCalled();
});
it('upload aborted while digest is pending never sends a mutation',async()=>{
 let complete!:(v:ArrayBuffer)=>void;const file=new File(['bytes'],'private.txt',{type:'text/plain'});Object.defineProperty(file,'arrayBuffer',{value:()=>new Promise<ArrayBuffer>(done=>{complete=done;})});const transport=vi.fn();vi.stubGlobal('fetch',transport);const controller=new AbortController(),client=new ApiClient();client.setContext('ctx');const pending=purchaseRequestApi(client).addAttachment({contextId:'ctx',tenantId:'tenant',contractId:'contract'},'request',1,file,null,controller.signal);const rejected=expect(pending).rejects.toMatchObject({name:'AbortError'});controller.abort();client.setContext('ctxB');complete(new TextEncoder().encode('bytes').buffer);await rejected;expect(transport).not.toHaveBeenCalled();
});
