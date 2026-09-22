# Fase 7 — Organização e módulos contratados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** não executado. Não marcar checkbox por existir apenas o código de exemplo neste plano.

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
- Criar: backend/alembic/versions/0005_organization_modules.py.
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

- [ ] **RED:**
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
- [ ] Rodar `uv run pytest tests/test_organization_api.py -v`.
- [ ] **GREEN:** enum explícito e FK (tenant_id,contract_id,parent_id).
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
- [ ] Commit: `feat: model contract organization with worksite nodes`.

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

- [ ] **RED:**
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
- [ ] Rodar testes focados backend e ModulesPage no frontend.
- [ ] **GREEN:** ContractModule único por tenant/contract/code, enabled e version.
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
- [ ] Commit: `feat: configure contracted modules with minimal extension boundaries`.

## Quality gate e parada

- [ ] Gate completo, teste de ciclo com conexões concorrentes, ausência de PROJECT.
- [ ] Revisar diff: nenhuma alteração no domínio Obras & Projetos; nenhuma tabela/
endpoint genérico de parâmetros, flags ou integração.
- [ ] Registrar phase-07.md e parar.
