import type {ApiClient} from '../../api/client';
import {parseRequest,parseRequestPage,parseRequestHistory,parseCandidates} from './validate';
import type {AttachmentView,Binding,Command,DraftInput} from './types';
const root='/procurement/requests';
const id=(v:string)=>encodeURIComponent(v);
export function purchaseRequestApi(client:ApiClient){
 // Only unresolved attempts are retained. No authority or keys are persisted.
 const attempts=new Map<string,string>();
 const signature=(b:Binding,path:string,body:unknown)=>JSON.stringify([b,path,body]);
 async function mutate(b:Binding,path:string,body:unknown,signal?:AbortSignal,digest?:string){
  const s=signature(b,path,digest??body);let key=attempts.get(s);if(!key){key=crypto.randomUUID();attempts.set(s,key);}
  const result=await client.request<unknown>(path,{method:'POST',body,contextId:b.contextId,signal,idempotencyKey:key});
  const parsed=parseRequest(result,b);attempts.delete(s);return parsed;
 }
 const read=async(b:Binding,path:string,signal?:AbortSignal)=>parseRequest(await client.request(path,{contextId:b.contextId,signal}),b);
 return {
 list:async(b:Binding,filters:{visibility:'own'|'unit';status?:string;node_id?:string;cursor?:string},signal?:AbortSignal)=>{const q=new URLSearchParams({limit:'50',...filters});return parseRequestPage(await client.request(root+'?'+q,{contextId:b.contextId,signal}),b);},
 detail:(b:Binding,requestId:string,signal?:AbortSignal)=>read(b,root+'/'+id(requestId),signal),
 create:(b:Binding,body:DraftInput,signal?:AbortSignal)=>mutate(b,root,body,signal),
 updateDraft:async(b:Binding,r:string,body:DraftInput&{expected_version:number},signal?:AbortSignal)=>parseRequest(await client.request(root+'/'+id(r)+'/draft',{method:'PATCH',body,contextId:b.contextId,signal}),b),
 command:(b:Binding,r:string,command:Command,body:{expected_version:number;reason?:string},signal?:AbortSignal)=>mutate(b,root+'/'+id(r)+'/'+command,body,signal),
 assign:(b:Binding,r:string,body:{expected_version:number;buyer_membership_id:string},signal?:AbortSignal)=>mutate(b,root+'/'+id(r)+'/assignment',body,signal),
 fulfill:(b:Binding,r:string,body:{expected_version:number;item_id:string;quantity:string;evidence:string;reason:string},signal?:AbortSignal)=>mutate(b,root+'/'+id(r)+'/fulfillments',body,signal),
 reverse:(b:Binding,r:string,entry:string,body:{expected_version:number;reason:string},signal?:AbortSignal)=>mutate(b,root+'/'+id(r)+'/fulfillments/'+id(entry)+'/reverse',body,signal),
 note:(b:Binding,r:string,body:{expected_version:number;text:string},signal?:AbortSignal)=>mutate(b,root+'/'+id(r)+'/notes',body,signal),
 history:async(b:Binding,r:string,cursor?:string,signal?:AbortSignal)=>parseRequestHistory(await client.request(root+'/'+id(r)+'/history?'+new URLSearchParams({limit:'50',...(cursor?{cursor}:{})}),{contextId:b.contextId,signal}),b),
 candidates:async(b:Binding,node:string,cursor?:string,signal?:AbortSignal)=>parseCandidates(await client.request(root+'/buyer-candidates?'+new URLSearchParams({requesting_node_id:node,limit:'50',...(cursor?{cursor}:{})}),{contextId:b.contextId,signal})),
 addAttachment:async(b:Binding,r:string,version:number,file:File,item:string|null,signal?:AbortSignal)=>{const bytes=await file.arrayBuffer();const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(n=>n.toString(16).padStart(2,'0')).join('');const form=new FormData();form.set('expected_version',String(version));form.set('file',file);if(item)form.set('item_id',item);return mutate(b,root+'/'+id(r)+'/attachments',form,signal,JSON.stringify([version,file.name,file.type,file.size,item,digest]));},
 downloadAttachment:async(b:Binding,r:string,a:Pick<AttachmentView,'id'|'filename'>,signal?:AbortSignal)=>{const blob=await client.request<Blob>(root+'/'+id(r)+'/attachments/'+id(a.id)+'/download',{contextId:b.contextId,signal,responseType:'blob'});if(signal?.aborted)throw new DOMException('Cancelled','AbortError');const url=URL.createObjectURL(blob);try{const link=document.createElement('a');link.href=url;link.download=a.filename;link.click();}finally{URL.revokeObjectURL(url);}},
 removeAttachment:async(b:Binding,r:string,a:string,version:number,signal?:AbortSignal)=>parseRequest(await client.request(root+'/'+id(r)+'/attachments/'+id(a),{method:'DELETE',body:{expected_version:version},contextId:b.contextId,signal}),b)
 };
}
