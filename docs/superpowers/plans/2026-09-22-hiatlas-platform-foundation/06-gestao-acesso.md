# Fase 6 — Gestão de usuários, perfis e auditoria — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** não executado. Não marcar checkbox por existir apenas o código de exemplo neste plano.

**Goal:** Disponibilizar fluxos reais de atendimento de acesso e perfis com opções seguras.
**Architecture:** UI usa projeções e elegibilidade da API; auditoria paginada por contrato.
**Depende de:** fases 4 e 5. **Não inclui:** visualizar ambiente de usuário.

## Review Focus

- Lista fica desatualizada após revogar support_assignable: salvar falha (6.1).
- Suporte manipula payload, não só formulário: API continua negando (6.1).
- Usuário com perfil protegido: UI não oferece fluxo comum de reatribuição (6.1).
- Auditoria contém valores financeiros/segredos: suporte não recebe payload (6.2).
- Busca/paginação de outro contrato não revela existência (6.2).

## Tarefa 6.1 — Telas de acesso e perfis

**Arquivos**
- Criar: frontend/src/platform/access/UsersPage.tsx, UserActions.tsx,
  RoleAssignment.tsx, RolesPage.tsx, AccessPages.test.tsx, Access.css.
- Criar: backend/tests/test_role_assignment_races.py.
- Modificar: frontend/src/platform/ContractShell.tsx, api/client.ts,
  backend/app/platform/roles.py.

**Interfaces:** UsersPage usa GET /memberships, POST convite/reset e PATCH status.
RoleAssignment usa GET /roles/assignable e PUT membership/role.
RolesPage existe só no portal admin e edita classificação, flag e capacidades
do catálogo; recebe expected_version. UI mostra resultado queued, não enviado.

- [ ] **RED:** fixture `renderAccessPage` no platformHarness.tsx da fase 4
aceita actor: admin/support e respostas HTTP de roles:
```tsx
it('offers only server-approved roles to support', async () => {
  renderAccessPage({ actor: 'support' })
  expect(await screen.findByRole('option', { name: 'Comprador Nacional' })).toBeVisible()
  expect(screen.queryByRole('option', { name: 'Financeiro' })).not.toBeInTheDocument()
  expect(screen.queryByRole('option', { name: 'Administrador HiAtlas' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Criar perfil' })).not.toBeInTheDocument()
})
```
Acrescentar servidor retornando 403 após seleção elegível: UI mantém diálogo,
mostra motivo e atualiza opções; não confirma alteração.
API race test: duas conexões, uma altera role para inelegível, outra associa.
Quando a desabilitação confirma primeiro, atribuição pelo suporte falha. Se a
atribuição confirma antes, a alteração administrativa posterior é ação distinta,
autorizada e auditada; não desassociar usuários retroativamente em silêncio.
- [ ] Rodar `npm test -- src/platform/access/AccessPages.test.tsx` e
`uv run pytest tests/test_role_assignment_races.py -v` nos diretórios próprios.
- [ ] **GREEN:** só renderizar itens da resposta assignable; confirmação mostra
usuário, empresa, contrato e novo perfil antes de enviar:
```ts
await api.request('/memberships/' + member.id + '/role', {
  method: 'PUT',
  contextId: context.id,
  body: { role_id: selectedRole.id, expected_version: member.version },
})
```
API revalida regras e lock transacional da fase 3. Suporte não altera flag,
classificação ou permissões. Mostrar reset como envio de link, nunca campo senha.
Não incluir botão funcional de MFA. Rótulos distinguem ativo de bloqueado.
- [ ] Commit: `feat: add scoped user access management screens`.

## Tarefa 6.2 — Histórico e auditoria com projeção restrita

**Arquivos**
- Criar: backend/app/audit/queries.py, routes.py, projections.py.
- Criar: backend/tests/test_audit_queries.py.
- Criar: frontend/src/audit/AuditPage.tsx, AccessHistory.tsx, AuditPage.test.tsx.
- Modificar: api/router.py, platform/ContractShell.tsx.

**Interfaces:** GET /api/audit?cursor=&limit= (máximo 100, ordem created_at/id);
GET /api/memberships/{id}/access-history.
Suporte: timestamp, action, resultado, ator permitido, entidade/id, referência,
request_id; sem before/after ou motivo livre que possa conter dado sensível.
Admin: diffs somente quando sua capacidade permite o domínio. Financeiro permanece
redigido sem concessão da fase 9.

- [ ] **RED:**
```python
from tests.helpers import select_context
def test_support_audit_omits_operational_diffs(support, ids, audited_change):
    scope = select_context(support, ids["contract_a"])
    response = support.get("/api/audit", headers=scope)
    assert response.status_code == 200
    row = response.json()["items"][0]
    assert "before" not in row
    assert "after" not in row
    assert "reason" not in row
```
Fixture audited_change cria evento autorizado com snapshots por serviço da fase 1.
Testar paginação determinística, limite inválido, cursor de outro contrato,
redação financeira para admin sem concessão e nenhuma rota DELETE/PATCH de evento.
- [ ] Rodar `uv run pytest tests/test_audit_queries.py -v` e teste AuditPage.
- [ ] **GREEN:** schemas distintos de resposta; query aplica contexto antes de
paginar. Cursor não é autorização e não transporta snapshots. A projeção por
allowlist não tenta apenas remover palavras como password de um JSON arbitrário:
```python
class SupportAuditView(BaseModel):
    id: UUID
    occurred_at: datetime
    action: str
    outcome: str
    request_id: UUID
```
Completar campos mínimos explicitamente autorizados no contrato acima, sem extras.
Consultas de histórico de usuário retornam só eventos do vínculo selecionado;
login global não revela acessos ou contratos externos. UI mostra fuso horário
e filtros de data/ação/status, com paginação e estados vazios reais.
- [ ] Commit: `feat: expose scoped redacted audit and access history`.

## Quality gate e parada

- [ ] Gate completo; conferir atribuições por chamadas diretas, não só via UI.
- [ ] Inspecionar fluxo admin/suporte em claro/escuro, teclado, conflito e falha de rede.
- [ ] Registrar phase-06.md e parar.
