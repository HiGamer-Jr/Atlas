# HiAtlas Obras & Projetos — Fase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao frontend atual do HiAtlas a fundação navegável do módulo **Obras & Projetos**, com acesso por perfis autorizados, dashboard inicial, portfólio de obras, detalhe de obra e dados demonstrativos coerentes, sem implementar ainda cronograma avançado, materiais, prontidão ou Horizon de Obras.

**Architecture:** Manter o `Workspace` como shell de navegação, mas delegar toda a experiência específica de Obras a um módulo React isolado em `frontend/src/workspace/projects/`. O catálogo global continuará responsável apenas por navegação/perfis; dados e componentes de Obras ficam encapsulados no novo módulo. A Fase 1 é frontend demonstrativa e não cria backend/persistência.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Vitest 4, Testing Library, CSS existente do Workspace.

**Spec:** `docs/superpowers/specs/2026-09-16-hiatlas-obras-projetos-v1-design.md`

## Global Constraints

- Produto oficial: **HiAtlas**.
- Slogan oficial: **Um novo horizonte para o seu negócio.**
- Manter o monólito modular; não introduzir microserviços.
- Não alterar CargoOps nem Atlas.CargoOps.
- Não implementar backend, banco, autenticação real ou persistência nesta fase.
- Não implementar Gantt, dependências, materiais, treinamentos, documentos, prontidão, diário, medições, aditivos ou Horizon de Obras nesta fase.
- Preservar tema Claro/Escuro, empresa/unidade, login demo, navegação e acessibilidade existentes.
- Dados desta fase são explicitamente demonstrativos.
- Acesso inicial ao módulo: `coordenacao`, `supervisao`, `diretoria` e `administrador`.
- Compradores, Financeiro, Loja e CD não recebem o módulo ainda; integrações específicas entram nas fases posteriores.
- O `Workspace.tsx` não deve receber lógica de negócio de Obras; apenas delegação para `ProjectsModule`.
- Toda alteração funcional deve seguir TDD: teste falhando → implementação mínima → teste passando → refatoração.
- Ao final, `npm test`, `npm run lint` e `npm run build` devem passar.

---

## File Structure

**Create**
- `frontend/src/workspace/projects/projectCatalog.ts` — tipos e dados demonstrativos da Fase 1.
- `frontend/src/workspace/projects/ProjectsModule.tsx` — shell visual do módulo Obras & Projetos.
- `frontend/src/workspace/projects/ProjectsModule.css` — estilos exclusivos do módulo.
- `frontend/src/workspace/projects/ProjectsModule.test.tsx` — testes unitários do módulo.

**Modify**
- `frontend/src/workspace/catalog.ts` — adicionar `obras` ao `ModuleKey`, menu e perfis autorizados.
- `frontend/src/workspace/Workspace.tsx` — delegar `active === 'obras'` para `ProjectsModule`.
- `frontend/src/Workspace.test.tsx` — testes de navegação/permissão integrados.

**Do not modify in Phase 1**
- backend;
- banco;
- Data Hub;
- Horizon/Copiloto de Compras;
- módulos legados.

---

### Task 1: Registrar Obras & Projetos no catálogo e proteger por perfil

**Files:**
- Modify: `frontend/src/workspace/catalog.ts`
- Test: `frontend/src/Workspace.test.tsx`

**Interfaces:**
- Produces: `ModuleKey` com valor `'obras'`.
- Produces: módulo `{ id: 'obras', label: 'Obras & Projetos', icon: '▣', children: ['Visão Geral', 'Portfólio de Obras'] }`.
- Access: Coordenação e Administrador recebem pelo `allModules`; Diretoria recebe pela regra atual; Supervisão deve receber explicitamente.
- No access: Comprador Nacional, Comprador Internacional, Financeiro, Loja e CD.

- [ ] **Step 1: Escrever teste integrado que exige o módulo para Coordenação**

Adicionar em `frontend/src/Workspace.test.tsx`:

```tsx
it("shows Obras & Projetos for coordination", () => {
  enter("coordenacao")
  expect(screen.getByRole("button", {name:"Obras & Projetos"})).toBeInTheDocument()
})
```

- [ ] **Step 2: Escrever teste integrado que protege o módulo do Comprador Nacional**

```tsx
it("does not show Obras & Projetos to national buyer during foundation phase", () => {
  enter("comprador-nacional")
  expect(screen.queryByRole("button", {name:"Obras & Projetos"})).not.toBeInTheDocument()
})
```

- [ ] **Step 3: Rodar os dois testes e confirmar RED**

Run:

```powershell
cd D:\Atlas\frontend
npm test -- Workspace.test.tsx
```

Expected: o teste de Coordenação falha porque `Obras & Projetos` ainda não existe.

- [ ] **Step 4: Alterar `ModuleKey`**

Em `frontend/src/workspace/catalog.ts`, alterar:

```ts
export type ModuleKey =
  | 'dashboard'
  | 'compras'
  | 'comex'
  | 'estoque'
  | 'financeiro'
  | 'obras'
  | 'datahub'
  | 'agenda'
  | 'relatorios'
  | 'administracao'
```

- [ ] **Step 5: Registrar o módulo**

Inserir entre Financeiro e Data Hub:

```ts
{
  id: 'obras',
  label: 'Obras & Projetos',
  icon: '▣',
  children: ['Visão Geral', 'Portfólio de Obras']
},
```

- [ ] **Step 6: Dar acesso à Supervisão**

Alterar o perfil:

```ts
{
  id: 'supervisao',
  name: 'Supervisão',
  code: 'SU',
  modules: ['dashboard', 'compras', 'comex', 'estoque', 'obras', 'agenda', 'relatorios']
},
```

Não adicionar `'obras'` aos arrays de Compradores, Financeiro, Loja ou CD.

- [ ] **Step 7: Rodar teste e confirmar GREEN**

```powershell
npm test -- Workspace.test.tsx
```

Expected: todos os testes de `Workspace.test.tsx` passam.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/workspace/catalog.ts frontend/src/Workspace.test.tsx
git commit -m "feat: register Obras e Projetos module"
```

---

### Task 2: Criar o modelo demonstrativo de Obras

**Files:**
- Create: `frontend/src/workspace/projects/projectCatalog.ts`
- Create: `frontend/src/workspace/projects/ProjectsModule.test.tsx`

**Interfaces:**
- Produces type `ProjectStatus = 'Planejada' | 'Em andamento' | 'Em risco' | 'Atrasada' | 'Concluída'`.
- Produces type `ProjectRecord`.
- Produces constant `demoProjects: ProjectRecord[]`.
- Produces function `getProjectMetrics(projects: ProjectRecord[]): ProjectMetrics`.

- [ ] **Step 1: Criar teste do cálculo dos indicadores**

Criar `frontend/src/workspace/projects/ProjectsModule.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { demoProjects, getProjectMetrics } from "./projectCatalog"

describe("project catalog", () => {
  it("calculates portfolio metrics from project data", () => {
    const metrics = getProjectMetrics(demoProjects)

    expect(metrics.active).toBe(4)
    expect(metrics.atRisk).toBe(2)
    expect(metrics.delayed).toBe(1)
    expect(metrics.totalRevisedBudget).toBe(11390000)
    expect(metrics.totalProjectedCost).toBe(11650000)
  })
})
```

- [ ] **Step 2: Rodar e confirmar RED**

```powershell
npm test -- ProjectsModule.test.tsx
```

Expected: falha porque `projectCatalog` não existe.

- [ ] **Step 3: Criar `projectCatalog.ts`**

```ts
export type ProjectStatus =
  | 'Planejada'
  | 'Em andamento'
  | 'Em risco'
  | 'Atrasada'
  | 'Concluída'

export type ProjectRecord = {
  id: string
  name: string
  company: string
  unit: string
  manager: string
  status: ProjectStatus
  plannedStart: string
  actualStart?: string
  plannedEnd: string
  projectedEnd: string
  plannedProgress: number
  actualProgress: number
  approvedBudget: number
  revisedBudget: number
  committedCost: number
  realizedCost: number
  projectedFinalCost: number
  riskCount: number
  decisionCount: number
  summary: string
}

export type ProjectMetrics = {
  active: number
  atRisk: number
  delayed: number
  totalRevisedBudget: number
  totalProjectedCost: number
}

export const demoProjects: ProjectRecord[] = [
  {
    id: 'OBR-2026-014',
    name: 'Ampliação CD Bauru',
    company: 'Aurora Distribuição',
    unit: 'CD Sul',
    manager: 'Marcos Almeida',
    status: 'Em risco',
    plannedStart: '2026-08-03',
    actualStart: '2026-08-05',
    plannedEnd: '2027-01-20',
    projectedEnd: '2027-01-28',
    plannedProgress: 48,
    actualProgress: 42,
    approvedBudget: 2500000,
    revisedBudget: 2640000,
    committedCost: 1720000,
    realizedCost: 1340000,
    projectedFinalCost: 2780000,
    riskCount: 5,
    decisionCount: 3,
    summary: 'Estrutura metálica e abastecimento de aço exigem acompanhamento de prazo e custo.'
  },
  {
    id: 'OBR-2026-009',
    name: 'Retrofit Loja Centro',
    company: 'Aurora Distribuição',
    unit: 'Loja Centro',
    manager: 'Fernanda Costa',
    status: 'Em andamento',
    plannedStart: '2026-07-15',
    actualStart: '2026-07-15',
    plannedEnd: '2026-10-30',
    projectedEnd: '2026-10-30',
    plannedProgress: 71,
    actualProgress: 73,
    approvedBudget: 1320000,
    revisedBudget: 1370000,
    committedCost: 1040000,
    realizedCost: 910000,
    projectedFinalCost: 1350000,
    riskCount: 1,
    decisionCount: 0,
    summary: 'Execução acima do progresso planejado e projeção financeira dentro do orçamento revisado.'
  },
  {
    id: 'OBR-2026-018',
    name: 'Implantação Centro Logístico',
    company: 'Horizonte Industrial',
    unit: 'Matriz',
    manager: 'Ricardo Nunes',
    status: 'Atrasada',
    plannedStart: '2026-06-01',
    actualStart: '2026-06-06',
    plannedEnd: '2026-12-18',
    projectedEnd: '2027-01-09',
    plannedProgress: 61,
    actualProgress: 49,
    approvedBudget: 4100000,
    revisedBudget: 4280000,
    committedCost: 3310000,
    realizedCost: 2890000,
    projectedFinalCost: 4520000,
    riskCount: 7,
    decisionCount: 4,
    summary: 'Atraso acumulado em infraestrutura pressiona a data final e a projeção de custos.'
  },
  {
    id: 'OBR-2026-021',
    name: 'Adequação Área de Expedição',
    company: 'Aurora Distribuição',
    unit: 'CD Sul',
    manager: 'Juliana Prado',
    status: 'Em risco',
    plannedStart: '2026-09-01',
    actualStart: '2026-09-02',
    plannedEnd: '2026-11-28',
    projectedEnd: '2026-12-04',
    plannedProgress: 22,
    actualProgress: 18,
    approvedBudget: 2950000,
    revisedBudget: 3100000,
    committedCost: 1610000,
    realizedCost: 880000,
    projectedFinalCost: 3000000,
    riskCount: 4,
    decisionCount: 2,
    summary: 'Dependências de fornecedores e liberações internas podem deslocar próximas etapas.'
  },
  {
    id: 'OBR-2026-024',
    name: 'Nova Área de Treinamento',
    company: 'Horizonte Industrial',
    unit: 'Matriz',
    manager: 'Paulo Lima',
    status: 'Planejada',
    plannedStart: '2026-10-05',
    plannedEnd: '2027-02-12',
    projectedEnd: '2027-02-12',
    plannedProgress: 0,
    actualProgress: 0,
    approvedBudget: 980000,
    revisedBudget: 980000,
    committedCost: 180000,
    realizedCost: 0,
    projectedFinalCost: 960000,
    riskCount: 0,
    decisionCount: 1,
    summary: 'Obra em planejamento, com orçamento-base aprovado e mobilização ainda não iniciada.'
  }
]

export function getProjectMetrics(projects: ProjectRecord[]): ProjectMetrics {
  const activeProjects = projects.filter(project =>
    ['Em andamento', 'Em risco', 'Atrasada'].includes(project.status)
  )

  return {
    active: activeProjects.length,
    atRisk: projects.filter(project => project.status === 'Em risco').length,
    delayed: projects.filter(project => project.status === 'Atrasada').length,
    totalRevisedBudget: projects.reduce((sum, project) => sum + project.revisedBudget, 0),
    totalProjectedCost: projects.reduce((sum, project) => sum + project.projectedFinalCost, 0)
  }
}
```

- [ ] **Step 4: Corrigir a expectativa de `active` para refletir a regra definida**

Com os dados acima, ativos são `Em andamento`, `Em risco` e `Atrasada`: quatro registros. Mantenha:

```ts
expect(metrics.active).toBe(4)
```

- [ ] **Step 5: Rodar teste e confirmar GREEN**

```powershell
npm test -- ProjectsModule.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/workspace/projects/projectCatalog.ts frontend/src/workspace/projects/ProjectsModule.test.tsx
git commit -m "feat: add Obras demo portfolio model"
```

---

### Task 3: Implementar dashboard inicial e portfólio do módulo

**Files:**
- Create: `frontend/src/workspace/projects/ProjectsModule.tsx`
- Create: `frontend/src/workspace/projects/ProjectsModule.css`
- Modify: `frontend/src/workspace/projects/ProjectsModule.test.tsx`

**Interfaces:**
- `ProjectsModule` props:

```ts
type ProjectsModuleProps = {
  company: string
  unit: string
  section: string
}
```

- Usa `demoProjects`.
- Filtra por empresa e unidade.
- `section === 'Portfólio de Obras'` prioriza tabela/lista; `Visão Geral` ou seção vazia exibe dashboard.

- [ ] **Step 1: Escrever teste de renderização da visão geral**

Adicionar ao teste:

```tsx
import { render, screen } from "@testing-library/react"
import ProjectsModule from "./ProjectsModule"

it("shows Obras portfolio overview for the selected company", () => {
  render(
    <ProjectsModule
      company="Aurora Distribuição"
      unit="Todas as unidades"
      section="Visão Geral"
    />
  )

  expect(screen.getByRole("heading", {name:"Obras & Projetos"})).toBeInTheDocument()
  expect(screen.getByText("Ampliação CD Bauru")).toBeInTheDocument()
  expect(screen.queryByText("Implantação Centro Logístico")).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Escrever teste de indicadores**

```tsx
it("shows portfolio health indicators", () => {
  render(
    <ProjectsModule
      company="Aurora Distribuição"
      unit="Todas as unidades"
      section="Visão Geral"
    />
  )

  expect(screen.getByText("Obras ativas")).toBeInTheDocument()
  expect(screen.getByText("Em risco")).toBeInTheDocument()
  expect(screen.getByText("Atrasadas")).toBeInTheDocument()
  expect(screen.getByText("Projeção financeira")).toBeInTheDocument()
})
```

- [ ] **Step 3: Rodar e confirmar RED**

```powershell
npm test -- ProjectsModule.test.tsx
```

Expected: falha porque `ProjectsModule.tsx` ainda não existe.

- [ ] **Step 4: Criar `ProjectsModule.tsx`**

Implementar com esta estrutura mínima:

```tsx
import { useMemo, useState } from 'react'
import { demoProjects, getProjectMetrics, type ProjectRecord } from './projectCatalog'
import './ProjectsModule.css'

type ProjectsModuleProps = {
  company: string
  unit: string
  section: string
}

const currency = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  maximumFractionDigits: 0
})

function formatDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('pt-BR')
}

export default function ProjectsModule({ company, unit, section }: ProjectsModuleProps) {
  const [selected, setSelected] = useState<ProjectRecord | null>(null)

  const projects = useMemo(
    () => demoProjects.filter(project =>
      project.company === company &&
      (unit === 'Todas as unidades' || project.unit === unit)
    ),
    [company, unit]
  )

  const metrics = getProjectMetrics(projects)
  const variance = metrics.totalProjectedCost - metrics.totalRevisedBudget
  const portfolioMode = section === 'Portfólio de Obras'

  if (selected) {
    const delayDays = Math.round(
      (new Date(selected.projectedEnd).getTime() - new Date(selected.plannedEnd).getTime()) /
      86400000
    )
    const costVariance = selected.projectedFinalCost - selected.revisedBudget

    return (
      <section className="projects-module">
        <button className="projects-back" onClick={() => setSelected(null)}>
          ← Voltar ao portfólio
        </button>

        <div className="projects-detail-head">
          <div>
            <span>{selected.id}</span>
            <h2>{selected.name}</h2>
            <p>{selected.summary}</p>
          </div>
          <strong className={`projects-status status-${selected.status.toLowerCase().replaceAll(' ', '-')}`}>
            {selected.status}
          </strong>
        </div>

        <div className="projects-detail-grid">
          <article>
            <small>Progresso</small>
            <strong>{selected.actualProgress}%</strong>
            <span>Planejado {selected.plannedProgress}%</span>
          </article>
          <article>
            <small>Entrega prevista</small>
            <strong>{formatDate(selected.plannedEnd)}</strong>
            <span>Projeção {formatDate(selected.projectedEnd)}</span>
          </article>
          <article>
            <small>Desvio de prazo</small>
            <strong>{delayDays > 0 ? `+${delayDays} dias` : 'No prazo'}</strong>
            <span>Baseado na projeção atual</span>
          </article>
          <article>
            <small>Projeção de custo</small>
            <strong>{currency.format(selected.projectedFinalCost)}</strong>
            <span>{costVariance > 0 ? `+${currency.format(costVariance)}` : `${currency.format(Math.abs(costVariance))} abaixo`}</span>
          </article>
        </div>

        <div className="projects-detail-panels">
          <article>
            <h3>Cronograma</h3>
            <dl>
              <dt>Início previsto</dt><dd>{formatDate(selected.plannedStart)}</dd>
              <dt>Início real</dt><dd>{selected.actualStart ? formatDate(selected.actualStart) : 'Não iniciado'}</dd>
              <dt>Entrega prevista</dt><dd>{formatDate(selected.plannedEnd)}</dd>
              <dt>Entrega projetada</dt><dd>{formatDate(selected.projectedEnd)}</dd>
            </dl>
          </article>
          <article>
            <h3>Orçamento</h3>
            <dl>
              <dt>Aprovado</dt><dd>{currency.format(selected.approvedBudget)}</dd>
              <dt>Revisado</dt><dd>{currency.format(selected.revisedBudget)}</dd>
              <dt>Comprometido</dt><dd>{currency.format(selected.committedCost)}</dd>
              <dt>Realizado</dt><dd>{currency.format(selected.realizedCost)}</dd>
              <dt>Projeção final</dt><dd>{currency.format(selected.projectedFinalCost)}</dd>
            </dl>
          </article>
          <article>
            <h3>Gestão</h3>
            <dl>
              <dt>Responsável</dt><dd>{selected.manager}</dd>
              <dt>Unidade</dt><dd>{selected.unit}</dd>
              <dt>Riscos abertos</dt><dd>{selected.riskCount}</dd>
              <dt>Decisões pendentes</dt><dd>{selected.decisionCount}</dd>
            </dl>
          </article>
        </div>
      </section>
    )
  }

  return (
    <section className="projects-module">
      <div className="projects-heading">
        <div>
          <span className="projects-eyebrow">OBRAS & PROJETOS</span>
          <h2>Obras & Projetos</h2>
          <p>Prazo, custo e execução no mesmo horizonte operacional.</p>
        </div>
        <span className="projects-context">{projects.length} obras no contexto</span>
      </div>

      {!portfolioMode && (
        <div className="projects-metrics">
          <article><span>Obras ativas</span><strong>{metrics.active}</strong><small>Em execução neste contexto</small></article>
          <article><span>Em risco</span><strong>{metrics.atRisk}</strong><small>Exigem acompanhamento</small></article>
          <article><span>Atrasadas</span><strong>{metrics.delayed}</strong><small>Prazo projetado comprometido</small></article>
          <article>
            <span>Projeção financeira</span>
            <strong>{currency.format(metrics.totalProjectedCost)}</strong>
            <small>{variance > 0 ? `${currency.format(variance)} acima do revisado` : 'Dentro do orçamento revisado'}</small>
          </article>
        </div>
      )}

      <div className="projects-panel">
        <div className="projects-panel-head">
          <div>
            <h3>{portfolioMode ? 'Portfólio de Obras' : 'Obras em foco'}</h3>
            <p>Acompanhe progresso, prazo, custo e riscos.</p>
          </div>
        </div>

        <div className="projects-list">
          {projects.map(project => (
            <button key={project.id} onClick={() => setSelected(project)}>
              <div>
                <span className="projects-id">{project.id}</span>
                <strong>{project.name}</strong>
                <small>{project.manager} · {project.unit}</small>
              </div>
              <div className="projects-progress">
                <span>{project.actualProgress}%</span>
                <small>planejado {project.plannedProgress}%</small>
              </div>
              <div>
                <span>{formatDate(project.projectedEnd)}</span>
                <small>entrega projetada</small>
              </div>
              <div>
                <span>{currency.format(project.projectedFinalCost)}</span>
                <small>custo final projetado</small>
              </div>
              <span className={`projects-status status-${project.status.toLowerCase().replaceAll(' ', '-')}`}>
                {project.status}
              </span>
              <span aria-hidden="true">→</span>
            </button>
          ))}
          {projects.length === 0 && <p className="projects-empty">Nenhuma obra encontrada neste contexto.</p>}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 5: Criar CSS focado, usando as variáveis do Workspace**

Criar `ProjectsModule.css`:

```css
.projects-module{display:grid;gap:22px}
.projects-heading{display:flex;justify-content:space-between;gap:24px;align-items:end}
.projects-heading h2{font-size:24px;margin:6px 0}
.projects-heading p,.projects-context{color:var(--muted);font-size:10px}
.projects-eyebrow{font-size:9px;letter-spacing:1.6px;color:var(--accent)}
.projects-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.projects-metrics article,.projects-panel,.projects-detail-grid article,.projects-detail-panels article{background:var(--panel);border:1px solid var(--line);border-radius:10px}
.projects-metrics article{padding:18px}
.projects-metrics span,.projects-metrics small{display:block;color:var(--muted);font-size:9px}
.projects-metrics strong{display:block;font-size:25px;margin:11px 0}
.projects-panel-head{padding:20px 22px;border-bottom:1px solid var(--line)}
.projects-panel-head h3{margin:0 0 6px;font-size:16px}
.projects-panel-head p{margin:0;color:var(--muted);font-size:10px}
.projects-list>button{width:100%;display:grid;grid-template-columns:minmax(220px,1.8fr) .7fr .8fr 1fr auto 20px;gap:18px;align-items:center;text-align:left;padding:17px 22px;border:0;border-bottom:1px solid var(--line);background:transparent;color:var(--text)}
.projects-list>button:hover{background:var(--hover)}
.projects-list strong,.projects-list span{display:block}
.projects-list strong{font-size:11px;margin:5px 0}
.projects-list small{display:block;color:var(--muted);font-size:8px;margin-top:5px}
.projects-id{font-size:8px;color:var(--accent)}
.projects-status{font-size:8px;border-radius:5px;padding:6px 8px;white-space:nowrap}
.status-em-risco{color:#d8af68;background:#b6812020}
.status-atrasada{color:#ed9a9d;background:#bd45451c}
.status-em-andamento{color:#55bea0;background:#23856a20}
.status-planejada{color:var(--accent);background:var(--hover)}
.status-concluída{color:#55bea0;background:#23856a20}
.projects-back{width:max-content;border:0;background:transparent;color:var(--accent);padding:0}
.projects-detail-head{display:flex;justify-content:space-between;gap:20px;align-items:start}
.projects-detail-head>div>span{color:var(--accent);font-size:9px}
.projects-detail-head h2{font-size:25px;margin:7px 0}
.projects-detail-head p{color:var(--muted);font-size:10px;max-width:680px}
.projects-detail-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.projects-detail-grid article{padding:18px}
.projects-detail-grid small,.projects-detail-grid span{display:block;color:var(--muted);font-size:9px}
.projects-detail-grid strong{display:block;font-size:20px;margin:9px 0}
.projects-detail-panels{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.projects-detail-panels article{padding:20px}
.projects-detail-panels h3{font-size:14px;margin:0 0 18px}
.projects-detail-panels dl{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0;font-size:10px}
.projects-detail-panels dt{color:var(--muted)}
.projects-detail-panels dd{text-align:right;margin:0}
.projects-empty{padding:35px;text-align:center;color:var(--muted)}
@media(max-width:1100px){
 .projects-metrics,.projects-detail-grid{grid-template-columns:repeat(2,1fr)}
 .projects-detail-panels{grid-template-columns:1fr}
 .projects-list>button{grid-template-columns:1.5fr .7fr .8fr auto}
 .projects-list>button>:nth-child(4),.projects-list>button>:last-child{display:none}
}
@media(max-width:700px){
 .projects-heading{align-items:start;flex-direction:column}
 .projects-metrics,.projects-detail-grid{grid-template-columns:1fr}
 .projects-list>button{grid-template-columns:1fr auto}
 .projects-list>button>:nth-child(2),.projects-list>button>:nth-child(3),.projects-list>button>:nth-child(4),.projects-list>button>:last-child{display:none}
}
```

- [ ] **Step 6: Rodar testes**

```powershell
npm test -- ProjectsModule.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/workspace/projects
git commit -m "feat: add Obras portfolio dashboard"
```

---

### Task 4: Integrar o módulo ao Workspace sem colocar lógica de Obras nele

**Files:**
- Modify: `frontend/src/workspace/Workspace.tsx`
- Modify: `frontend/src/Workspace.test.tsx`

**Interfaces:**
- Consumes: `ProjectsModule`.
- Passa `company`, `unit`, `section`.
- O módulo genérico continua atendendo os demais `ModuleKey`.

- [ ] **Step 1: Escrever teste integrado de navegação**

Adicionar:

```tsx
it("opens Obras & Projetos and shows the project portfolio", () => {
  enter("coordenacao")

  fireEvent.click(screen.getByRole("button", {name:"Obras & Projetos"}))

  expect(screen.getByRole("heading", {name:"Obras & Projetos"})).toBeInTheDocument()
  expect(screen.getByText("Ampliação CD Bauru")).toBeInTheDocument()
})
```

- [ ] **Step 2: Escrever teste da subnavegação**

```tsx
it("opens Portfólio de Obras from the Obras submenu", () => {
  enter("coordenacao")

  fireEvent.click(screen.getByRole("button", {name:"Obras & Projetos"}))
  fireEvent.click(
    within(screen.getByRole("navigation")).getByRole("button", {name:"Portfólio de Obras"})
  )

  expect(screen.getByText("Portfólio de Obras")).toBeInTheDocument()
})
```

- [ ] **Step 3: Rodar e confirmar RED**

```powershell
npm test -- Workspace.test.tsx
```

Expected: falha porque o Workspace ainda tenta usar a tabela genérica.

- [ ] **Step 4: Importar o módulo**

No topo de `Workspace.tsx`:

```tsx
import ProjectsModule from './projects/ProjectsModule'
```

- [ ] **Step 5: Delegar o conteúdo quando `active === 'obras'`**

Na área em que hoje existe:

```tsx
{active==='dashboard' ? <>...</> : <section className="ws-panel">...</section>}
```

alterar conceitualmente para:

```tsx
{active === 'dashboard' ? (
  <>
    {/* dashboard atual sem alterações */}
  </>
) : active === 'obras' ? (
  <ProjectsModule
    company={company}
    unit={unit}
    section={section || 'Visão Geral'}
  />
) : (
  <section className="ws-panel">
    {/* visão genérica atual dos demais módulos */}
  </section>
)}
```

Não mover nem reescrever Dashboard, Compras, COMEX, Estoque ou demais módulos nesta tarefa.

- [ ] **Step 6: Garantir que a primeira entrada em Obras abra Visão Geral**

Alterar `navigate` apenas para o caso de Obras:

```tsx
function navigate(id:ModuleKey,child='') {
  setActive(id)
  setSection(id === 'obras' && !child ? 'Visão Geral' : child)
  setSearch('')
  setStatus('Todos')
  setDetail(null)
  setMenu(false)
}
```

- [ ] **Step 7: Rodar testes e confirmar GREEN**

```powershell
npm test -- Workspace.test.tsx
npm test -- ProjectsModule.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/workspace/Workspace.tsx frontend/src/Workspace.test.tsx
git commit -m "feat: integrate Obras module into workspace"
```

---

### Task 5: Validar detalhe de obra e contexto Empresa/Unidade

**Files:**
- Modify: `frontend/src/workspace/projects/ProjectsModule.test.tsx`

**Interfaces:**
- Usa interação real do `ProjectsModule`.
- Não cria nova API.

- [ ] **Step 1: Adicionar teste de detalhe**

```tsx
import { fireEvent } from "@testing-library/react"

it("opens project detail with schedule and budget information", () => {
  render(
    <ProjectsModule
      company="Aurora Distribuição"
      unit="Todas as unidades"
      section="Visão Geral"
    />
  )

  fireEvent.click(screen.getByRole("button", {name:/Ampliação CD Bauru/i}))

  expect(screen.getByRole("heading", {name:"Ampliação CD Bauru"})).toBeInTheDocument()
  expect(screen.getByText("Cronograma")).toBeInTheDocument()
  expect(screen.getByText("Orçamento")).toBeInTheDocument()
  expect(screen.getByText("Gestão")).toBeInTheDocument()
  expect(screen.getByText("R$ 2.780.000")).toBeInTheDocument()
})
```

- [ ] **Step 2: Adicionar nome acessível aos botões de obra**

No botão do `projects.map`, adicionar:

```tsx
aria-label={`Abrir ${project.name}`}
```

- [ ] **Step 3: Atualizar o teste para buscar pelo nome acessível**

```tsx
fireEvent.click(screen.getByRole("button", {name:"Abrir Ampliação CD Bauru"}))
```

- [ ] **Step 4: Adicionar teste de Unidade**

```tsx
it("filters projects by selected organizational unit", () => {
  render(
    <ProjectsModule
      company="Aurora Distribuição"
      unit="Loja Centro"
      section="Visão Geral"
    />
  )

  expect(screen.getByText("Retrofit Loja Centro")).toBeInTheDocument()
  expect(screen.queryByText("Ampliação CD Bauru")).not.toBeInTheDocument()
})
```

- [ ] **Step 5: Rodar testes**

```powershell
npm test -- ProjectsModule.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/workspace/projects
git commit -m "test: cover Obras detail and context filtering"
```

---

### Task 6: Quality Gate e validação visual local

**Files:**
- No production changes unless a verification exposes a real defect.

**Interfaces:**
- Validates the complete Phase 1 slice.

- [ ] **Step 1: Rodar todos os testes do frontend**

```powershell
cd D:\Atlas\frontend
npm test
```

Expected: exit code 0.

- [ ] **Step 2: Rodar lint**

```powershell
npm run lint
```

Expected: exit code 0.

- [ ] **Step 3: Rodar build**

```powershell
npm run build
```

Expected: exit code 0.

- [ ] **Step 4: Rodar o preview de desenvolvimento**

```powershell
npm run dev -- --port 5174
```

Abrir:

```text
http://localhost:5174
```

- [ ] **Step 5: Checklist manual — Coordenação**

Entrar como `Coordenação` e verificar:

```text
[ ] Obras & Projetos aparece no menu
[ ] Visão Geral abre sem erro
[ ] Cards mostram indicadores
[ ] Ampliação CD Bauru aparece
[ ] Clique abre detalhe
[ ] Cronograma/Orçamento/Gestão aparecem
[ ] Tema claro funciona
[ ] Tema escuro funciona
[ ] Empresa filtra as obras
[ ] Unidade filtra as obras
```

- [ ] **Step 6: Checklist manual — permissões**

```text
[ ] Supervisão vê Obras & Projetos
[ ] Diretoria vê Obras & Projetos
[ ] Administrador vê Obras & Projetos
[ ] Comprador Nacional NÃO vê na Fase 1
[ ] Comprador Internacional NÃO vê na Fase 1
[ ] Financeiro NÃO vê na Fase 1
[ ] Loja NÃO vê na Fase 1
[ ] CD NÃO vê na Fase 1
```

- [ ] **Step 7: Revisão com Dayana**

Mostrar no localhost apenas como **Foundation / dados demonstrativos** e coletar:

```text
1. O portfólio permite entender quais obras estão em risco?
2. A informação de prazo é suficiente para uma primeira visão?
3. Orçamento revisado x projeção final é compreensível?
4. Que informação ela procuraria imediatamente e ainda não aparece?
5. O detalhe está excessivo ou insuficiente?
```

Não implementar sugestões durante a reunião. Registrar feedback para a Fase 2/3.

- [ ] **Step 8: Commit de correções de verificação, somente se houver**

Se nenhum defeito for encontrado, não criar commit vazio.

Se houver correção real:

```powershell
git add <arquivos-corrigidos>
git commit -m "fix: polish Obras foundation validation"
```

---

## Definition of Done — Fase 1

A Fase 1 está concluída somente quando:

```text
[ ] Obras & Projetos existe como ModuleKey oficial
[ ] acesso inicial está correto por perfil
[ ] dashboard inicial renderiza por empresa/unidade
[ ] portfólio de obras está navegável
[ ] detalhe de obra mostra prazo, progresso, orçamento e gestão
[ ] dados são claramente demonstrativos
[ ] nenhuma lógica de Obras foi despejada dentro do Workspace
[ ] temas claro/escuro continuam funcionando
[ ] testes existentes continuam verdes
[ ] novos testes estão verdes
[ ] lint passa
[ ] build passa
[ ] validação local foi realizada
```

## Explicitly Deferred to Later Phases

Não transformar sugestões da validação em scope creep. Estes itens permanecem fora da Fase 1:

```text
Fase 2: EAP, atividades, marcos, dependências, calendário e Gantt
Fase 3: orçamento detalhado, comprometido/realizado, categorias e margem
Fase 4: materiais, pedidos, estoque, inbound e transferências
Fase 5: prontidão, equipes, terceiros, treinamentos, documentos e equipamentos
Fase 6: Horizon Obras — Hoje / 1–7 / 7–30 e recomendações explicáveis
Fase 7: diário, medições, mudanças e aditivos
Fase 8: portfólio executivo e Modo Reunião completo
```
