# Fase 3 — Contextos e permissões — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** Fase 3 implementada, revisada e validada (234 backend, 68 frontend; gate completo passou). Evidências em [phase-03.md](../../validation/hiatlas-platform/phase-03.md). Parada obrigatória antes da Fase 4.

**Goal:** Impedir acesso cruzado e implementar elegibilidade de perfis no servidor.
**Architecture:** Contexto por sessão/aba, catálogo fechado e negação por padrão.
**Depende de:** fase 2. **Não inclui:** UI, SMTP ou módulos operacionais.

## Review Focus

- Mesmo tenant, contrato diferente: negar assim como tenant diferente (3.1).
- Contexto de outra sessão ou revogado: negar, sem fallback (3.1).
- Usuário de cliente tentando listar todos os contratos: somente memberships (3.1).
- Perfil com nome inocente mas capacidade sensível: inelegível (3.2).
- Flag alterada antes de atribuição: consultar estado atual sob transação (3.2).

## Tarefa 3.1 — Seleção explícita de contrato e isolamento

**Arquivos**
- Criar: backend/app/tenancy/schemas.py, services.py, contexts.py,
  dependencies.py, routes.py.
- Criar: backend/alembic/versions/0003_contexts_roles_memberships.py.
- Criar: backend/tests/test_context_api.py, test_tenant_isolation.py,
  tests/__init__.py, tests/helpers.py.
- Modificar: tenancy/models.py, api/router.py, tests/conftest.py, db/models.py.

**Interfaces:** AccessScope e select_context definidos no índice.
GET /api/contracts?search=: internos veem metadados mínimos; clientes só vínculos
ativos. Busca limitada a 128 caracteres permite nome de empresa, código ou usuário
vinculado; retornar apenas metadados do contrato, sem expor identidade/vínculos globais.
POST /api/tenants e POST /api/tenants/{id}/contracts: somente PLATFORM_ADMIN,
auditoria global com alvo explícito; não precisam contexto de cliente preexistente.
POST/DELETE /api/contexts; GET /api/context para cabeçalho e estado atual.
GET /api/memberships/{id} será protegido por contexto já nesta fase.

- [x] **RED:**
```python
from tests.helpers import select_context

def test_same_tenant_other_contract_is_isolated(admin, ids):
    scope = select_context(admin, ids["contract_a2"])
    response = admin.get(f"/api/memberships/{ids['member_a']}", headers=scope)
    assert response.status_code == 404

def test_context_belongs_to_auth_session(admin, support, ids):
    scope = select_context(admin, ids["contract_a"])
    assert support.get("/api/context", headers=scope).status_code == 403
```
Testar ausência de contexto, contrato inativo, contexto expirado, cliente sem
membership e duas abas com seleção A/B sem mudar A.
- [x] Rodar `uv run pytest tests/test_context_api.py tests/test_tenant_isolation.py -v`.
- [x] **GREEN:** AccessContext com id UUID aleatório, session_id, actor_id,
tenant_id, contract_id, created_at, expires_at e revoked_at. Válido no máximo
até a sessão principal; negar qualquer contexto cujo proprietário mudou.
```python
statement = select(Membership).where(
    Membership.id == member_id,
    Membership.tenant_id == scope.tenant_id,
    Membership.contract_id == scope.contract_id,
)
```
Comparação da busca parametrizada, sem SQL interpolado; limitar paginação.
Aplicar escopo a cada repositório; nunca carregar por id e retornar antes de
verificar contexto. User pertence a identidade global, Membership à combinação.
Perfil/unidade associados por FKs compostas. Membership usa active e blocked
independentes; índices únicos user_id/tenant_id/contract_id.
Criar modelos TenantRole/Permission nesta migração porque membership referencia role;
comportamento e catálogo seguem na tarefa 3.2.
- [x] Revogar contexto ao encerrar; criar evento de seleção/encerramento. Global
admin não pode consultar operação por um tenant_id livre sem AccessContext.
- [x] Commit: `feat: require explicit contract context for tenant access`.

## Tarefa 3.2 — Catálogo e regras support_assignable

**Arquivos**
- Criar: backend/app/platform/types.py, capabilities.py, policy.py,
  role_schemas.py, roles.py, routes.py.
- Criar: backend/tests/test_role_policy.py, test_role_assignment_api.py.
- Modificar: tenancy/models.py, schemas.py, routes.py, services.py, api/router.py.

**Interfaces:** role_support_eligible(role, permissions) -> bool;
require_capability(db, principal, scope, capability) -> None.
GET/POST/PATCH /api/roles; GET /api/roles/assignable;
PUT /api/memberships/{id}/role com role_id e expected_version.
A lista assignable e a mutação compartilham a mesma política.
Somente admin cria/edita role, support_assignable, classificação e permissões.

- [x] **RED:**
```python
from tests.helpers import select_context

def test_support_cannot_assign_opted_out_role(support, ids):
    scope = select_context(support, ids["contract_a"])
    response = support.put(f"/api/memberships/{ids['member_a']}/role",
        headers=scope, json={"role_id": ids["role_opt_out"], "expected_version": 1})
    assert response.status_code == 403

def test_support_assignable_list_excludes_sensitive(support, ids):
    scope = select_context(support, ids["contract_a"])
    rows = support.get("/api/roles/assignable", headers=scope).json()["items"]
    assert ids["role_basic"] in {r["id"] for r in rows}
    assert ids["role_finance"] not in {r["id"] for r in rows}
    assert ids["role_admin"] not in {r["id"] for r in rows}
```
Testar atribuição permitida, role de outro contrato, códigos PLATFORM_*, perfil
renomeado com finance.read, edição concorrente da flag e tentativa de tornar
um perfil sensível support_assignable.
- [x] Rodar `uv run pytest tests/test_role_policy.py tests/test_role_assignment_api.py -v`.
- [x] **GREEN:** catálogo em código define capacidade, domínio e sensitivity;
não inferir sensibilidade pelo nome exibido. Role tem classification
STANDARD/ADMINISTRATIVE/FINANCIAL_FISCAL/SENSITIVE e flag default false:
```python
def role_support_eligible(role, permissions):
    return (
        role.support_assignable
        and role.classification == "STANDARD"
        and all(not permission.sensitive for permission in permissions)
    )
```
Capabilities desconhecidas são rejeitadas. Catálogo de tenant começa só com
capacidades necessárias aos fluxos existentes; finance.read/fiscal.read são
reservadas como sensíveis sem habilitar endpoints de domínio.
Na edição, rejeitar flag true com classificação/capacidade sensível (422).
Na atribuição, reler role e membership com controle de concorrência na transação;
não confiar na lista renderizada. Impedir alterar perfil de identidade interna
por endpoint de tenant, bem como transferir vínculos entre contextos.
Eventos de role.create/update/assign capturam diffs permitidos e revogam
autorizações afetadas. Nenhum papel interno aparece em GET /roles.
- [x] Catalogar capacidades de plataforma da matriz, mas endpoints ausentes
não se tornam disponíveis só por existir código de permissão.
- [x] Commit: `feat: enforce tenant role eligibility for platform support`.

## Quality gate e parada

- [x] Gate completo com matriz admin/suporte/cliente e dois tenants/três contratos.
- [x] Revisar todos os endpoints criados, incluindo listagens e criação global.
- [x] Provar transação/auditoria da atribuição e recusa de role desconhecida.
- [x] Registrar phase-03.md; parar antes da fase 4.
