# Fase 8 — Atendimento somente leitura — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** implementado, revisado independentemente e validado; parado para revisão do usuário. [Evidências](../../validation/hiatlas-platform/phase-08.md).

**Goal:** Permitir visualização contextual sem senha do usuário e sem operações de escrita.
**Architecture:** SupportSession e contexto derivado, mantendo operador real e interseção de permissões.
**Depende de:** fase 7. **Não inclui:** manutenção ou concessão financeira.

## Review Focus

- Request de escrita direto, mesmo sem botão: 403 (8.1).
- Reutilizar contexto pai para escrever durante atendimento: 403 (8.1).
- Usuário simulado interno/de outro contrato: recusar (8.1).
- Permissão, membership ou módulo revogado depois de iniciar: efeito imediato (8.1).
- Faixa some ao navegar/recarregar: sessão não pode continuar silenciosa (8.2).

## Tarefa 8.1 — Sessão de suporte no servidor

**Arquivos**
- Criar: backend/app/support/models.py, schemas.py, services.py, routes.py.
- Criar: backend/alembic/versions/0007_support_sessions.py.
- Criar: backend/tests/test_support_sessions.py.
- Modificar: platform/policy.py, tenancy/dependencies.py, db/models.py, api/router.py.

**Interfaces:** start_support(db, principal, scope, member_id).
POST /api/support-sessions com membership_id, reason obrigatório e reference opcional devolve id/context_id/expires_at/mode.
POST /api/support-sessions/{id}/end encerra sessão própria; idempotente.
Mode inicialmente READ_ONLY; validade 30 minutos limitada à sessão principal.
Contexto pai fica suspenso para mutações até encerramento, inclusive chamadas diretas.
Outros contextos independentes não adquirem permissão da sessão de suporte.

- [x] **RED:**
```python
from tests.helpers import select_context
def test_read_only_blocks_direct_and_parent_writes(support, ids):
    parent = select_context(support, ids["contract_a"])
    started = support.post("/api/support-sessions", headers=parent,
        json={"membership_id": str(ids["member_a"]), "reason": "Investigação de acesso"})
    assert started.status_code == 201
    child = {"X-HiAtlas-Context": started.json()["context_id"]}
    for context in (child, parent):
        response = support.patch(
            f"/api/memberships/{ids['member_a']}/status", headers=context,
            json={"active": False, "expected_version": 1})
        assert response.status_code == 403
```
Testar término por outro operador, expiração, alvo bloqueado, mudança de perfil,
módulo desativado e suporte incapaz de consultar Financeiro mesmo se alvo puder.
- [x] Suíte backend específica executada nos ciclos RED/GREEN e incluída no gate completo `uv run --frozen pytest`: 487 testes, zero skips.
- [x] **GREEN:** actor_id nunca substituído por target_user_id:
```python
if scope.support_mode == "READ_ONLY" and capability.mutates_business_state:
    raise Forbidden("SUPPORT_READ_ONLY")
effective = target_permissions & support_read_capabilities & enabled_capabilities
```
Metadados da capacidade incluem mutation/sensitivity; não depender somente de
verbo HTTP. Encerramento é comando de controle com autorização específica.
Auditar início, fim, expiração observada e negações. Política reconsulta sessão,
alvo, role e módulos para cada chamada; sem token que imite login do cliente.
Respostas do usuário visualizado permanecem redigidas por limites do suporte.
- [x] Commit integrado backend/frontend: `7b68f86` — `feat: implement contextual read-only support sessions`.

## Tarefa 8.2 — Faixa permanente e retorno seguro

**Arquivos**
- Criar: frontend/src/support/SupportBanner.tsx, SupportView.tsx,
  SupportSession.test.tsx.
- Modificar: platform/access/UsersPage.tsx, platform/ContextProvider.tsx,
  platform/ContractShell.tsx.

**Interfaces:** SupportView recebe session com id, contextId, userName, company,
contractCode, expiresAt e mode; callbacks onEnd/onExpired.
POST início troca contexto explicitamente e limpa conteúdo; não usa login do alvo.

- [x] **RED:**
```tsx
it('keeps the operator and read-only mode visible', async () => {
  renderSupportSession() // fixture adicionada a platformHarness.tsx
  expect(await screen.findByRole('status')).toHaveTextContent('SESSÃO DE SUPORTE — SOMENTE LEITURA')
  expect(screen.getByTestId('contract-context')).toHaveTextContent('Contrato A')
  expect(screen.getByText('Usuário visualizado: Pessoa de teste')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Encerrar sessão de suporte' })).toBeVisible()
})
```
Fixture usa /me do suporte e POST /support-sessions. Testar que expiração ou
401 limpa os detalhes e volta à seleção, sem restaurar automaticamente acesso.
- [x] Suíte frontend específica executada nos ciclos RED/GREEN e incluída em `npm test -- --maxWorkers=2`: 216 testes, zero skips.
- [x] **GREEN:** banner fora da área rolável com nome do operador e alvo distintos:
```tsx
<div role="status" className="support-banner">
  <strong>SESSÃO DE SUPORTE — SOMENTE LEITURA</strong>
  <span>Usuário visualizado: {session.userName}</span>
  <button onClick={onEnd}>Encerrar sessão de suporte</button>
</div>
```
Sessão só visualiza capacidades e dados que a API já entrega; módulos ainda
demonstrativos não se tornam ambientes reais. Recarregar restaura somente após revalidação de autenticação, contexto e SupportSession no servidor; antes de iniciar outra sessão, encerrar ou expirar a anterior.
- [x] Commit integrado backend/frontend: `7b68f86` — `feat: implement contextual read-only support sessions`.

## Quality gate e parada

- [x] Gate completo; verificar escrita em todos os endpoints já existentes,
inclusive convites, roles, módulos e organização.
- [x] Inspeção de banner em desktop/mobile, navegação, erro e expiração.
- [x] Registrar phase-08.md e parar.

## Execução — 2026-10-02

Base aprovada: 62d5508; branch feat/hiatlas-platform-phase-8. A solicitação detalhada do usuário complementa os exemplos: migração 0007, motivo obrigatório, vínculo à sessão HTTP e ao membership, restauração somente após revalidação, política central fail-closed, histórico contextual. O contrato de execução temporário fixou interfaces/responsabilidades; decisões, RED/GREEN, gate, E2E, revisões e cleanup estão consolidados em phase-08.md. O scratch temporário foi removido após consolidação. Somente Fase 8.
