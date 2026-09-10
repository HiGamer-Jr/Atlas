import { useEffect, useRef, useState } from 'react'
import { modules, records, type DemoRecord, type ModuleKey } from './catalog'
import lightLogo from '../assets/hiatlas-light.png'
import darkLogo from '../assets/hiatlas-dark.png'
import './Workspace.css'

type Profile = { id:string; name:string; code:string; modules:ModuleKey[] }
export default function Workspace({profile,onLogout}:{profile:Profile;onLogout:()=>void}) {
 const [theme,setTheme] = useState(() => {try{return localStorage.getItem('hiatlas-theme') === 'light' ? 'light':'dark'}catch{return 'dark'}})
 const [active,setActive] = useState<ModuleKey>('dashboard')
 const [section,setSection] = useState('')
 const [company,setCompany] = useState('Aurora Distribuição')
 const profileUnits = profile.id === 'loja' ? ['Loja Centro'] : profile.id === 'cd' ? ['CD Sul'] : ['Todas as unidades','Matriz','Loja Centro','CD Sul']
 const [unit,setUnit] = useState(profileUnits[0])
 const [search,setSearch] = useState('')
 const [status,setStatus] = useState('Todos')
 const [detail,setDetail] = useState<DemoRecord|null>(null)
 const [menu,setMenu] = useState(false)
 const dialog = useRef<HTMLDialogElement>(null)
 const trigger = useRef<HTMLElement|null>(null)
 useEffect(()=>{try{localStorage.setItem('hiatlas-theme',theme)}catch{/* storage optional */}},[theme])
 useEffect(()=>{if(detail) dialog.current?.showModal(); else dialog.current?.close()},[detail])
 const canSeeSection = (child:string) => !(profile.id==='comprador-nacional'&&child==='Internacional') && !(profile.id==='comprador-internacional'&&child==='Nacional')
 const allowed = modules.filter(m=>m.id==='dashboard'||profile.modules.includes(m.id)).map(m=>({...m,children:m.children.filter(canSeeSection)}))
 const context = records.filter(r=>r.module!=='dashboard'&&profile.modules.includes(r.module)&&canSeeSection(r.section)&&r.company===company&&(unit==='Todas as unidades'||r.unit===unit))
 const current = allowed.find(m=>m.id===active)!
 const rows = context.filter(r=>r.module===active&&(!section||r.section===section)&&(status==='Todos'||r.status===status)&&(`${r.title} ${r.id} ${r.owner} ${r.detail}`).toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR')))
 const priorities = context.filter(r=>r.status!=='Em dia').sort((a,b)=>Number(b.status==='Crítico')-Number(a.status==='Crítico')).slice(0,5)
 const next = context.filter(r=>r.due!=='Hoje').sort((a,b)=>Number(b.due==='Amanhã')-Number(a.due==='Amanhã')).slice(0,3)
 function navigate(id:ModuleKey,child='') {setActive(id);setSection(child);setSearch('');setStatus('Todos');setDetail(null);setMenu(false)}
 function show(r:DemoRecord) {trigger.current=document.activeElement as HTMLElement;setDetail(r)}
 function close(){setDetail(null);trigger.current?.focus()}
 const badges = (s:string) => <span className={`ws-badge ${s==='Crítico'?'critical':s==='Atenção'?'warning':'normal'}`}>{s}</span>
 return <main className="ws" data-theme={theme}>
  <aside className={`ws-sidebar ${menu?'is-open':''}`}>
   <div className="ws-brand"><img src={theme==='light'?lightLogo:darkLogo} alt="HiAtlas — Supply Chain Intelligence"/><span>WORKSPACE</span></div>
   <nav aria-label="Módulos HiAtlas"><button className={active==='dashboard'?'selected':''} onClick={()=>navigate('dashboard')}><i aria-hidden="true">◫</i>Dashboard</button>
    <div className="ws-nav-caption">OPERAÇÃO</div>
    {allowed.filter(m=>m.id!=='dashboard').map(m=><div key={m.id}><button aria-expanded={m.children.length?active===m.id:undefined} className={active===m.id?'selected':''} onClick={()=>navigate(m.id)}><i aria-hidden="true">{m.icon}</i>{m.label}<span className="ws-chevron" aria-hidden="true">{m.children.length?'⌄':''}</span></button>{active===m.id&&m.children.length>0&&<div className="ws-subnav">{m.children.map(c=><button key={c} aria-current={section===c?'page':undefined} onClick={()=>navigate(m.id,c)}>{c}</button>)}</div>}</div>)}
   </nav>
   <div className="ws-profile"><span className="ws-avatar">{profile.name.slice(0,2).toUpperCase()}</span><div><strong>{profile.name}</strong><small>{profile.code} · Demonstração</small></div><button onClick={onLogout} aria-label="Sair" title="Sair">↪</button></div>
  </aside>
  <div className="ws-main">
   <header className="ws-header"><img className="ws-mobile-logo" src={theme==='light'?lightLogo:darkLogo} alt="HiAtlas"/><button className="ws-menu" aria-label="Alternar menu" aria-expanded={menu} onClick={()=>setMenu(!menu)}>☰</button><div className="ws-context"><label>Empresa<select aria-label="Empresa" value={company} onChange={e=>{setCompany(e.target.value);setUnit(profileUnits[0]);setDetail(null)}}><option>Aurora Distribuição</option><option>Horizonte Industrial</option></select></label><label>Unidade<select aria-label="Unidade" value={unit} onChange={e=>{setUnit(e.target.value);setDetail(null)}}>{profileUnits.map(u=><option key={u}>{u}</option>)}</select></label></div>
    <div className="ws-rates" aria-label="Câmbio demonstrativo"><div><small>USD/BRL</small><strong>R$ 5,45</strong></div><div><small>EUR/BRL</small><strong>R$ 5,91</strong></div><span>Valores de exemplo<br/>Sem cotação ao vivo</span></div>
    <div className="ws-themes" role="group" aria-label="Aparência"><button aria-label="Tema claro" aria-pressed={theme==='light'} onClick={()=>setTheme('light')}>☼</button><button aria-label="Tema escuro" aria-pressed={theme==='dark'} onClick={()=>setTheme('dark')}>☾</button></div>
   </header>
   <div className="ws-content"><div className="ws-breadcrumb">Workspace <span>/</span> {current.label} {section&&<> <span>/</span> {section}</>}<span className="ws-demo">DADOS DEMONSTRATIVOS</span></div>
    <div className="ws-title"><div><p className="ws-eyebrow">{active==='dashboard'?'SUA OPERAÇÃO, EM PERSPECTIVA':current.label}</p><h1>{active==='dashboard'?'O que precisa da sua atenção hoje?':section||current.label}</h1><p>{active==='dashboard'?`Painel ${profile.name} · Prioridades e próximos passos da sua operação.`:`Acompanhe ${section?section.toLocaleLowerCase('pt-BR'):current.label.toLocaleLowerCase('pt-BR')} no contexto de ${company}.`}</p></div><span className="ws-date">{new Date().toLocaleDateString('pt-BR',{day:'2-digit',month:'long',year:'numeric'})}</span></div>
    <div className="ws-metrics">{[{label:'Exigem atenção',value:context.filter(r=>r.status==='Crítico').length,caption:'Prioridade alta',tone:'red'},{label:'Para acompanhar',value:context.filter(r=>r.status==='Atenção').length,caption:'Pendências operacionais',tone:'amber'},{label:'Em dia',value:context.filter(r=>r.status==='Em dia').length,caption:'Fluxos sob controle',tone:'green'},{label:'Áreas disponíveis',value:allowed.length-1,caption:`Visão ${profile.name}`,tone:'blue'}].map(m=><article key={m.label} className={`ws-metric ${m.tone}`}><span>{m.label}<b>↗</b></span><strong>{m.value.toString().padStart(2,'0')}</strong><small>{m.caption}</small></article>)}</div>
    {active==='dashboard'?<>
      <div className="ws-dashboard-grid"><section className="ws-panel"><div className="ws-panel-title"><div><h2>Central de atenção</h2><p>Comece pelo que pode impactar sua operação.</p></div><span className="ws-count">{priorities.length} prioridades</span></div><div className="ws-attention">{priorities.length?priorities.map(r=><button key={r.id} onClick={()=>show(r)}><span className={`ws-dot ${r.status==='Crítico'?'red':'amber'}`}/><div><strong>{r.title}</strong><small>{modules.find(m=>m.id===r.module)?.label} · {r.unit} · {r.owner}</small></div><div className="ws-alert-end">{badges(r.status)}<small>{r.due} →</small></div></button>):<p className="ws-empty">Nenhuma pendência neste contexto.</p>}</div></section>
      <section className="ws-panel ws-next"><div className="ws-panel-title"><div><span className="ws-eyebrow">PLANEJAMENTO</span><h2>Próximos dias</h2><p>Eventos previstos, sem surpresas.</p></div></div>{next.length?next.map(r=><button key={r.id} onClick={()=>show(r)}><span>{r.due}</span><strong>{r.title}</strong><small>{r.owner} · {r.unit}</small></button>):<p className="ws-empty">Sem eventos neste contexto.</p>}<p className="ws-footnote">Agenda demonstrativa. Recomendações preditivas serão uma evolução futura.</p></section></div>
      <section className="ws-panel ws-operation"><div className="ws-panel-title"><div><h2>Visão da operação</h2><p>Do planejamento à disponibilidade em estoque.</p></div></div><div className="ws-area-grid">{allowed.filter(m=>m.id!=='dashboard').map(m=><button key={m.id} onClick={()=>navigate(m.id)}><span className="ws-area-icon">{m.icon}</span><strong>{m.label}</strong><small>{context.filter(r=>r.module===m.id).length} registros no contexto</small><span className="ws-area-link">Explorar módulo ↗</span></button>)}</div></section>
    </>:<section className="ws-panel"><div className="ws-panel-title"><div><h2>{section?`Registros de ${section.toLocaleLowerCase('pt-BR')}`:'Visão geral'}</h2><p>{rows.length} registros · {unit}</p></div></div>{current.children.length>0&&<div className="ws-tabs">{current.children.map(c=><button className={section===c?'active':''} key={c} onClick={()=>navigate(active,c)}>{c}</button>)}</div>}<div className="ws-filters"><label><span>Buscar registros</span><input aria-label="Buscar registros" placeholder="Buscar por descrição, código ou responsável…" value={search} onChange={e=>setSearch(e.target.value)}/></label><label><span>Status</span><select aria-label="Filtrar por status" value={status} onChange={e=>setStatus(e.target.value)}><option>Todos</option><option>Crítico</option><option>Atenção</option><option>Em dia</option></select></label></div><div className="ws-table-scroll"><table><thead><tr><th>Registro / descrição</th><th>Unidade</th><th>Responsável</th><th>Prazo</th><th>Referência</th><th>Status</th><th><span className="ws-sr">Detalhes</span></th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td><strong>{r.title}</strong><small>{r.id} · {r.section}</small></td><td>{r.unit}</td><td>{r.owner}</td><td>{r.due}</td><td>{r.value}</td><td>{badges(r.status)}</td><td><button onClick={()=>show(r)} aria-label={`Ver detalhes de ${r.title}`}>↗</button></td></tr>)}</tbody></table>{rows.length===0&&<p className="ws-empty">Nenhum registro encontrado.</p>}</div></section>}
    <footer className="ws-bottom"><span>HiAtlas — Supply Chain Intelligence</span><span>Informação → Atenção → Decisão</span></footer>
   </div>
  </div>
  <dialog ref={dialog} className="ws-dialog" onCancel={close} onClose={()=>{if(detail)close()}} aria-labelledby="detail-title">{detail&&<><button className="ws-close" onClick={close} aria-label="Fechar detalhes">×</button><span className="ws-eyebrow">{detail.id} · DEMONSTRAÇÃO</span><h2 id="detail-title">{detail.title}</h2>{badges(detail.status)}<p>{detail.detail}</p><dl><dt>Empresa</dt><dd>{detail.company}</dd><dt>Unidade</dt><dd>{detail.unit}</dd><dt>Responsável</dt><dd>{detail.owner}</dd><dt>Prazo</dt><dd>{detail.due}</dd><dt>Referência</dt><dd>{detail.value}</dd></dl><p className="ws-footnote">Registro ilustrativo para validar o fluxo. Nenhuma alteração operacional será enviada.</p><button className="ws-primary" onClick={()=>{navigate(detail.module,detail.section);close()}}>Abrir página relacionada →</button></>}</dialog>
 </main>
}



