import {useState} from 'react';
import {useScopedQuery} from '../platform/access/useScopedQuery';
import type {Page} from '../platform/access/types';
import {formatDate} from '../platform/access/types';
import ErrorNotice from '../api/ErrorNotice';
import type {SupportHistory} from './types';
const labels={ACTIVE:'Ativa',ENDED:'Encerrada',EXPIRED:'Expirada',REVOKED:'Revogada'};
function duration(item:SupportHistory){
 if(item.status==='ACTIVE')return 'Em andamento';
 if(!item.ended_at)return 'Não registrada';
 const milliseconds=Date.parse(item.ended_at)-Date.parse(item.started_at);
 if(!Number.isFinite(milliseconds)||milliseconds<0)return 'Não registrada';
 const seconds=Math.floor(milliseconds/1000);
 const hours=Math.floor(seconds/3600),minutes=Math.floor((seconds%3600)/60),remaining=seconds%60;
 return `${hours ? `${hours} h ` : ''}${minutes} min ${remaining} s`;
}
export default function SupportSessionHistory(){const [offset,setOffset]=useState(0);const {data,error,loading,retry}=useScopedQuery<Page<SupportHistory>>(`/support-sessions?limit=20&offset=${offset}`);return <section className="access-page"><h2>Sessões de suporte</h2><p>Histórico de atendimento deste contrato.</p><ErrorNotice error={error}/>{!!error&&<button onClick={retry}>Tentar novamente</button>}{loading&&<p role="status">Carregando sessões de suporte…</p>}{data&&<>{data.items.length===0?<p>Nenhuma sessão de suporte registrada neste contexto.</p>:data.items.map(item=><article className="support-module" key={item.id}><h3>{item.viewed.display_name}</h3><p>Operador: {item.operator.display_name} · {labels[item.status]}</p><p>Modo: {item.mode==='READ_ONLY'?'Somente leitura':'Indisponível'}</p><p>Duração: {duration(item)}</p><p>Início: {formatDate(item.started_at)} · Fim: {formatDate(item.ended_at)}</p><p>Motivo: {item.reason}</p>{item.reference&&<p>Referência: {item.reference}</p>}</article>)}<div className="pagination"><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Sessões anteriores</button><span>{data.total} sessões</span><button disabled={offset+data.limit>=data.total} onClick={()=>setOffset(offset+20)}>Próximas sessões</button></div></>}</section>;}
