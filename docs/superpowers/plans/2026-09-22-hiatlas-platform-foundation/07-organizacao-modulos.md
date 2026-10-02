# Fase 7 — Organização e módulos contratados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** implementado, revisado independentemente e validado; parada para revisão do usuário antes da Fase 8. O addendum de execução abaixo prevalece sobre os exemplos originais.

**Goal:** Configurar estrutura organizacional real sem confundir canteiro com obra.
**Architecture:** Nós tipados no contrato e módulos de catálogo fechado; sem gerenciador universal.
**Depende de:** fase 6. **Não inclui:** cronograma, portfólio persistente ou integrações executáveis.

## Review Focus

- PROJECT/Obra enviado como nó: rejeitar (7.1).
- Pai/unidade de outro contrato: rejeitar inclusive no mesmo tenant (7.1).
- Ciclo criado por duas reparentagens concorrentes: impedir (7.1).
- Desabilitar módulo durante sessão: efeito imediato na API (7.2).
- Nome livre de flag/parâmetro/conector: não vira configuração executável (7.2).

## Tarefa 7.1 — Estrutura com WORKSITE

**Arquivos**
- Criar: backend/app/organization/models.py, schemas.py, services.py, routes.py.
- Criar: backend/alembic/versions/0006_organization_modules.py.
- Criar: backend/tests/test_organization_api.py.
- Criar: frontend/src/platform/organization/OrganizationPage.tsx,
  OrganizationPage.test.tsx.
- Modificar: db/models.py, api/router.py, platform/ContractShell.tsx.

**Interfaces:** GET/POST /api/organization/nodes;
PATCH /api/organization/nodes/{id}, com expected_version.
Tipos: COMPANY, BRANCH, OFFICE, STORE, DISTRIBUTION_CENTER, WAREHOUSE, WORKSITE.
Campos: id, tenant_id, contract_id, parent_id nullable, kind, name, active, version.
MembershipUnitScope associa nós existentes por FK composta e define acessos
por unidade; ausência de escopo não significa acesso global implícito.

- [x] **RED:**
```python
from tests.helpers import select_context
def test_organization_rejects_business_project(admin, ids):
    scope = select_context(admin, ids["contract_a"])
    result = admin.post("/api/organization/nodes", headers=scope,
        json={"kind": "PROJECT", "name": "Obra comercial", "parent_id": None})
    assert result.status_code == 422

def test_organization_accepts_worksite(admin, ids):
    scope = select_context(admin, ids["contract_a"])
    result = admin.post("/api/organization/nodes", headers=scope,
        json={"kind": "WORKSITE", "name": "Canteiro Norte", "parent_id": None})
    assert result.status_code == 201
    assert result.json()["kind"] == "WORKSITE"
```
Acrescentar suporte negado, pai externo, ciclo próprio/indireto/concorrente,
nome vazio, conflito de versão e escopo de unidade externo.
- [x] Testes focados reais executados: `.venv/Scripts/python.exe -m pytest` com organization/modules/schema/policy/races/audit; 63 passaram.
- [x] **GREEN:** enum explícito e FK (tenant_id,contract_id,parent_id).
Antes de mover nó, lock na linha Contract para serializar alterações de árvore,
buscar ancestrais no contexto e rejeitar self/descendente:
```python
if node_id == parent_id or node_id in ancestor_ids:
    raise DomainConflict("ORGANIZATION_CYCLE")
```
DomainConflict definida em core/errors.py na fase 2 mapeia para 409.
Criação de nó não cria Project, cronograma ou dado de negócio. Não modificar
frontend/src/workspace/projects/, preservado como demo.
Tela mostra tipo Canteiro (WORKSITE), edição administrativa e inativação,
sem botão excluir definitivamente. Mudanças de escopo de unidade são auditadas.
- [x] Commit conjunto de estrutura/módulos: `d7dc2e1` (`feat: implement contextual organization and contracted modules`).

## Tarefa 7.2 — Módulos e extensões mínimas

**Arquivos**
- Criar: backend/app/organization/modules.py.
- Criar: backend/tests/test_contract_modules.py, test_extension_boundaries.py.
- Criar: frontend/src/platform/organization/ModulesPage.tsx,
  ModulesPage.test.tsx.
- Modificar: organization/models.py, schemas.py, routes.py, policy.py e shell.

**Interfaces:** GET /api/contract/modules e PATCH /api/contract/modules/{code}
com enabled/expected_version, apenas admin.
Catálogo fechado: PROCUREMENT, COMEX, INVENTORY, FINANCE, PROJECTS, DATAHUB.
Module habilitado indica contratado; não prova domínio já implementado.
Flags/parâmetros/integrações reutilizarão contexto, catálogo de capacidades e
auditoria ao ganhar seu primeiro caso real. Nesta fase não criar classes,
funções vazias ou tabelas dedicadas sem consumidor. Ausência de capacidade ou
módulo reconhecido é negada pela política central já existente.

- [x] **RED:**
```python
from tests.helpers import select_context
def test_support_cannot_enable_module(support, ids):
    scope = select_context(support, ids["contract_a"])
    response = support.patch("/api/contract/modules/FINANCE", headers=scope,
        json={"enabled": True, "expected_version": 1})
    assert response.status_code == 403
```
Testar código desconhecido, acesso depois de desabilitar, versão divergente e
ausência de rotas de edição genérica. Escopo administrativo pode ler metadados
dos módulos para reabilitar; isso não libera conteúdo financeiro.
- [x] Rodar testes focados backend e ModulesPage no frontend.
- [x] **GREEN:** ContractModule único por tenant/contract/code, enabled e version.
Política usa essa informação antes de autorizar conteúdo de domínio.
```python
if code not in CONTRACT_MODULE_CATALOG:
    raise InvalidInput("UNKNOWN_CONTRACT_MODULE")
require_capability(db, principal, scope, "contract.modules.update")
```
CONTRACT_MODULE_CATALOG é constante imutável em modules.py; InvalidInput,
definido em core/errors.py na fase 2, mapeia para 422.
Infraestrutura reutilizável é contexto + catálogo fechado + auditoria, sem
funções que simulem feature flags ou conectores. Não criar tabela JSON, editor
de parâmetros, builder de integração, CRUD de feature flags, agendador genérico
ou campos URL/token. Qualquer extensão exige caso real e teste que falhe.
A UI exibe módulos contratados e informa módulos ainda indisponíveis; recursos
sem caso de uso não recebem formulários.
- [x] Entregue no mesmo commit conjunto `d7dc2e1`, sem infraestrutura fictícia.

## Quality gate e parada

- [x] Gate completo, teste de ciclo com conexões concorrentes, ausência de PROJECT.
- [x] Revisar diff: nenhuma alteração no domínio Obras & Projetos; nenhuma tabela/
endpoint genérico de parâmetros, flags ou integração.
- [x] Registrar phase-07.md e parar.

## Decisões de execução — 2026-10-01

Base Fase 6 aprovada por autorização de início da Fase 7: `ef9d080`.
Branch: `feat/hiatlas-platform-phase-7`; worktree isolada existente reutilizada.
A solicitação detalhada do usuário complementa o plano; somente a Fase 7 está autorizada.

- [x] Backend OrganizationNode: oito kinds incluindo UNIT, code estável normalizado/imutável,
  unicidade por tenant/contract, timestamps e versão; migração incremental `0006` após `0005`.
  FK composta para contrato/parent, self-parent check, enum/check sem PROJECT.
- [x] Matriz central: COMPANY recebe todos os tipos físicos não COMPANY; BRANCH recebe
  UNIT/STORE/DISTRIBUTION_CENTER/WAREHOUSE/OFFICE/WORKSITE; UNIT recebe UNIT e estes tipos;
  STORE e DISTRIBUTION_CENTER recebem WAREHOUSE/OFFICE; WAREHOUSE/WORKSITE recebem OFFICE;
  OFFICE é folha. Raízes sem parent são permitidas, como no fluxo WORKSITE do plano.
  COMPANY nunca é child. Pai/ancestrais ativos são exigidos para unidade ativa.
- [x] Contrato é bloqueado para serializar alterações de árvore; revalidação de sessão,
  contexto, contrato e versão após locks. Ciclos simples/concorrentes são rejeitados.
  Inativação preserva histórico e nega enquanto houver filhos ou escopos ativos dependentes;
  API informa contagens provadas para confirmação. Nenhum hard delete.
- [x] MembershipUnitScope com FKs compostas para vínculo/nó e lifecycle sem delete;
  API mínima administrativa, expected_version do membership, no máximo 100 unidades por
  alteração. Sem gestão visual completa nesta fase. Ausência de escopo não concede
  acesso global quando uma operação exigir unidade. Nó estrangeiro/inativo é rejeitado.
- [x] Módulos: catálogo original PROCUREMENT/COMEX/INVENTORY/FINANCE/PROJECTS/DATAHUB.
  ContractModule contratado e ativo independentes, defaults false; ativo exige contratado.
  Catálogo ausente no banco é projetado como não contratado, version 0, sem escrita no GET.
  PATCH usa expected_version; primeira alteração persiste version 1. Catálogo informa
  indisponibilidade dos domínios operacionais ainda não implementados.
- [x] Política central require_capability integra disponibilidade de módulo e escopo de
  unidade quando a operação os exige; capabilities existentes modules.read/manage e
  organization.manage, sem duplicar nomes do exemplo antigo do plano. Admin configura;
  Suporte lê metadados mínimos de módulos e não altera estrutura/módulos/escopos.
  Ativar FINANCE não libera finance/fiscal.read nem concessões da Fase 9.
- [x] Auditoria atômica com schemas fechados para nó/módulo/escopo, dados obtidos do
  servidor. Projeção Admin permite metadados seguros desta fase; suporte não recebe
  diffs estruturais/sensíveis. Sem relaxar grants/imutabilidade.
- [x] React: menus Estrutura/Módulos; lista hierárquica acessível e paginada com parent
  explícito, labels portugueses, criação/revisão/edição/inativação, impacto, 409,
  loading/empty/error/retry e remoção de dados após sessão/contexto inválidos.
  Módulos admin contextual; Suporte somente leitura. Sem persistência de negócio no storage.
- [x] Extensões: sem tabelas/rotas genéricas de FeatureFlag/ContractParameter/
  IntegrationConfiguration, conforme tarefa 7.2 aprovada: não há catálogo/consumidor concreto.
  Não construir conectores nem simular flags; documentar dependência futura.
- [x] Testes RED/GREEN PostgreSQL constraints/grants reais, A/A2/B, auditoria rollback,
  ciclo/reparent concorrente, mesma versão, contrato inativado/contexto expirado em locks.
- [x] Revisões independentes backend/frontend e correções RED/GREEN de todos os achados.
- [x] Quality gate completo zero skips; migrations upgrade/downgrade/upgrade; E2E real
  Admin/Suporte, A/A2/B, light/dark, desktop/mobile390×844, teclado/foco/contexto visível.
- [x] Evidências phase-07.md, capturas sanitizadas, commits; worktree limpa; serviços,
  banco e segredos temporários removidos; parar para revisão antes da Fase 8.
