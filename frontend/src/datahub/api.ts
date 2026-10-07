import type {ApiClient} from '../api/client';
import type {Catalog,ImportSummary,ImportDetail,Page,ImportRow,Issue} from './types';
export function dataHubApi(client:ApiClient){return {
 catalog:(signal:AbortSignal)=>client.request<Catalog>('/datahub/templates',{signal}),
 uploadExcel:(file:File,signal:AbortSignal)=>{const body=new FormData();body.append('file',file);return client.request<ImportSummary>('/datahub/imports',{method:'POST',body,signal});},
 confirmImport:(id:string,expectedVersion:number,key:string,signal:AbortSignal)=>client.request<ImportSummary>(`/datahub/imports/${encodeURIComponent(id)}/confirm`,{method:'POST',body:{expected_version:expectedVersion,idempotency_key:key},signal}),
 history:(page:number,signal:AbortSignal)=>client.request<Page<ImportDetail>>(`/datahub/imports?page=${page}&page_size=10`,{signal}),
 detail:(id:string,signal:AbortSignal)=>client.request<ImportDetail>(`/datahub/imports/${encodeURIComponent(id)}`,{signal}),
 rows:(id:string,page:number,signal:AbortSignal)=>client.request<Page<ImportRow>>(`/datahub/imports/${encodeURIComponent(id)}/rows?page=${page}&page_size=20`,{signal}),
 issues:(id:string,page:number,signal:AbortSignal)=>client.request<Page<Issue>>(`/datahub/imports/${encodeURIComponent(id)}/issues?page=${page}&page_size=20`,{signal}),
 downloadTemplate:(id:string,version:number,nodes:string[],signal:AbortSignal)=>client.request<Blob>(`/datahub/templates/${encodeURIComponent(id)}/download`,{method:'POST',body:{template_version:version,node_ids:nodes},responseType:'blob',signal}),
 exportExcel:(id:string,version:number,nodes:string[],signal:AbortSignal)=>client.request<Blob>('/datahub/exports',{method:'POST',body:{template_id:id,template_version:version,node_ids:nodes},responseType:'blob',signal}),
};}
export function saveWorkbook(blob:Blob,filename:string){const url=URL.createObjectURL(blob);try{const link=document.createElement('a');link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();}finally{URL.revokeObjectURL(url);}}
