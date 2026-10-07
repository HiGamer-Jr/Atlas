import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {useAuth} from '../auth/state';
import {useAccessContext} from '../platform/state';
import {ApiError,isAbort} from '../api/errors';
import {dataHubApi,saveWorkbook} from './api';
import type {Catalog,ImportSummary,ImportDetail,ImportRow,Issue,Page,Template} from './types';

export function useDataHub(){
 const {api}=useAuth();const {selected}=useAccessContext();const hub=useMemo(()=>dataHubApi(api),[api]);
 const [catalog,setCatalog]=useState<Catalog|null>(null),[history,setHistory]=useState<Page<ImportDetail>|null>(null),[preview,setPreview]=useState<ImportSummary|null>(null);
 const [rows,setRows]=useState<Page<ImportRow>|null>(null),[issues,setIssues]=useState<Page<Issue>|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null),[notice,setNotice]=useState('');
 const controllers=useRef(new Set<AbortController>()),locked=useRef(false),key=useRef<string|null>(null),epoch=useRef(0);
 const run=useCallback(async(task:(signal:AbortSignal)=>Promise<void>)=>{
  if(locked.current)return;locked.current=true;setBusy(true);setError(null);setNotice('');
  const controller=new AbortController(),current=epoch.current;controllers.current.add(controller);
  try{await task(controller.signal);}catch(e){if(!isAbort(e)&&!controller.signal.aborted&&current===epoch.current){setError(e);if(e instanceof ApiError&&[401,403,404].includes(e.status)){setPreview(null);setRows(null);setIssues(null);setHistory(null);setCatalog(null);key.current=null;}if(e instanceof ApiError&&e.status===409){setPreview(null);setRows(null);setIssues(null);key.current=null;setNotice('Os dados mudaram. Envie a planilha e gere um novo preview.');}}}
  finally{controllers.current.delete(controller);if(current===epoch.current){locked.current=false;setBusy(false);}}
 },[]);
 const reload=useCallback(()=>run(async signal=>{const [c,h]=await Promise.all([hub.catalog(signal),hub.history(1,signal)]);if(signal.aborted)return;setCatalog(c);setHistory(h);}),[hub,run]);
 const cancel=useCallback(()=>{epoch.current++;for(const c of controllers.current)c.abort();controllers.current.clear();locked.current=false;},[]);
 useEffect(()=>{let active=true;queueMicrotask(()=>{if(active)void reload();});return()=>{active=false;cancel();};},[reload,selected?.id,cancel]);
 useEffect(()=>{if(preview?.status!=='READY_FOR_CONFIRMATION')return;const expires=Date.parse(preview.preview_expires_at);const timer=setTimeout(()=>{setPreview(previous=>previous?.id===preview.id?{...previous,status:'EXPIRED'}:previous);key.current=null;},Math.min(Math.max(expires-Date.now(),0),2147483647));return()=>clearTimeout(timer);},[preview]);
 const view=async(id:string,signal:AbortSignal)=>{const [p,r,i]=await Promise.all([hub.detail(id,signal),hub.rows(id,1,signal),hub.issues(id,1,signal)]);if(signal.aborted)return;setPreview(p);setRows(r);setIssues(i);key.current=null;};
 return {catalog,history,preview,rows,issues,busy,error,notice,reload,
 upload:(file:File)=>run(async signal=>{setPreview(null);setRows(null);setIssues(null);key.current=null;const result=await hub.uploadExcel(file,signal);const [r,i]=await Promise.all([hub.rows(result.id,1,signal),hub.issues(result.id,1,signal)]);if(signal.aborted)return;setPreview(result);setRows(r);setIssues(i);key.current=crypto.randomUUID();const h=await hub.history(1,signal);if(!signal.aborted)setHistory(h);}),
 inspect:(id:string)=>run(signal=>view(id,signal)),
 confirm:()=>run(async signal=>{if(!preview||preview.status!=='READY_FOR_CONFIRMATION')return;if(Date.parse(preview.preview_expires_at)<=Date.now())throw new ApiError(409);key.current??=crypto.randomUUID();const result=await hub.confirmImport(preview.id,preview.version,key.current,signal);if(result.status!=='COMMITTED')throw new ApiError(503);if(signal.aborted)return;setPreview(result);setNotice('Importação concluída.');const h=await hub.history(1,signal);if(!signal.aborted)setHistory(h);}),
 historyPage:(page:number)=>run(async signal=>{const h=await hub.history(page,signal);if(!signal.aborted)setHistory(h);}),
 rowsPage:(page:number)=>run(async signal=>{if(!preview)return;const r=await hub.rows(preview.id,page,signal);if(!signal.aborted)setRows(r);}),
 issuesPage:(page:number)=>run(async signal=>{if(!preview)return;const i=await hub.issues(preview.id,page,signal);if(!signal.aborted)setIssues(i);}),
 download:(template:Template,nodes:string[])=>run(async signal=>{const blob=await hub.downloadTemplate(template.id,template.version,nodes,signal);if(!signal.aborted)saveWorkbook(blob,'HiAtlas-modelo.xlsx');}),
 exportWorkbook:(template:Template,nodes:string[])=>run(async signal=>{const blob=await hub.exportExcel(template.id,template.version,nodes,signal);if(!signal.aborted)saveWorkbook(blob,'HiAtlas-exportacao.xlsx');})};
}
