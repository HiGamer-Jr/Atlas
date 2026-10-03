# Fase 9 — Concessões temporárias administrativas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** Fase 9 implementada, validada e revisada independentemente em 2026-10-03; parada para revisão do usuário. Fase 10 não iniciada. O adendo abaixo prevalece sobre nomes e exemplos legados deste plano.

**Goal:** Exigir autorização explícita para Financeiro/Fiscal e manutenção.
**Architecture:** Grants ligados à sessão, contexto, finalidade e expiração, sem promover papel.
**Depende de:** fase 8. **Não inclui:** endpoints financeiros de negócio ou handlers novos.

Os checkboxes legados abaixo não representam pendências: nomes, arquivos e exemplos foram substituídos pelo adendo executável e pela especificação autorizada do usuário. As provas atuais constam em phase-09.md.

## Review Focus

- Ser admin e selecionar contrato não concede finance.read (9.1).
- Grant de A usado em B ou em outra sessão: negar (9.1).
- Grant expirado/revogado durante operação: revalidar no servidor (9.1).
- Manutenção em entidade/capacidade diferente da autorizada: negar (9.1).
- UI mantém modo após expiração ou troca de contexto: encerrar (9.2).

## Referência histórica superada — Tarefa 9.1

**Arquivos**
- Criar: backend/app/support/grants.py, grant_schemas.py.
- Criar: backend/alembic/versions/0007_authorized_grants.py.
- Criar: backend/tests/test_financial_grants.py, test_maintenance_grants.py.
- Modificar: support/models.py, routes.py, platform/policy.py, audit/projections.py.

**Interfaces:** GrantRequest: kind FINANCIAL_READ/MAINTENANCE, reason não vazio,
reference obrigatório para MAINTENANCE, capability_ids e entity_ids fechados,
expected_context_id; senha de reauth passa somente ao serviço de identidade.
POST /api/grants e POST /api/grants/{id}/revoke, apenas admin.
Grant: actor_id/session_id/context_id/tenant_id/contract_id, created_at,
expires_at, revoked_at, kind, escopo, reason/reference.
Teto 30 minutos e reautenticação válida por 5 minutos.

- [ ] **RED:** fixture `financial_probe` registra somente no app de teste uma rota
GET /api/test-financial-probe que chama require_capability com finance.read
e devolve {"authorized":true}. Não lê dado fictício de negócio nem existe em produção.
```python
from tests.helpers import select_context
def test_admin_contract_selection_does_not_grant_finance(admin, ids, financial_probe):
    scope = select_context(admin, ids["contract_a"])
    assert admin.get("/api/test-financial-probe", headers=scope).status_code == 403
```
Adicionar grant válido -> 200, expirado/revogado -> 403, grant A em A2/B -> 403,
suporte -> 403 e auditoria com ator/motivo/validade.
Testar manutenção sem chamado, escopo desconhecido, reauth vencida e entidade fora
do escopo. Fixture de capability de manutenção é conhecida só no app de teste
até existir handler da fase 10; não criar permissão coringa.
- [ ] Rodar `uv run pytest tests/test_financial_grants.py tests/test_maintenance_grants.py -v`.
- [ ] **GREEN:** require_capability exige as duas condições:
```python
if capability.financial and principal.platform_role == "PLATFORM_ADMIN":
    if not valid_financial_grant(db, principal, scope, capability, now):
        raise Forbidden("FINANCIAL_GRANT_REQUIRED")
```
valid_financial_grant e valid_maintenance_grant são funções privadas de grants.py;
consultam todos os vínculos/expiração e nunca aceitam só um grant_id do cliente.
FINANCIAL_READ não concede escrita; MAINTENANCE não concede leitura financeira
automaticamente. Operação financeira de escrita exige capacidade de domínio,
grant financeiro apropriado à leitura necessária e grant de manutenção específico.
Proibir capabilities coringa/strings arbitrárias. Trilha registra criar/revogar/
expirar e uso em ação, sem persistir senha de reauth.
Uma sessão READ_ONLY deve ser encerrada/transicionada explicitamente; grant
não desativa o bloqueio de leitura de forma implícita.
- [ ] Atualizar projeção de auditoria financeira para usar o mesmo grant; suporte
permanece sem snapshots financeiros. Impedir concessão a outro usuário.
- [ ] Commit: `feat: require explicit expiring administrative grants`.

## Referência histórica superada — Tarefa 9.2

**Arquivos**
- Criar: frontend/src/support/GrantDialog.tsx, GrantStatus.tsx,
  GrantFlow.test.tsx.
- Modificar: SupportBanner.tsx, platform/ContractShell.tsx.

**Interfaces:** GrantDialog recebe kind, ações/entidades da API e contexto;
campos motivo, chamado quando obrigatório e confirmação explícita do escopo.
Nenhum campo escolhe tabela, coluna, SQL ou JSON livre.

- [ ] **RED:**
```tsx
it('requires a reference for authorized maintenance', async () => {
  renderGrantFlow({ kind: 'MAINTENANCE' }) // fixture HTTP no platformHarness.tsx
  fireEvent.change(screen.getByLabelText('Motivo'), {target:{value:'Correção solicitada'}})
  expect(screen.getByRole('button', {name:'Confirmar manutenção'})).toBeDisabled()
  expect(screen.getByLabelText('Chamado ou referência')).toBeRequired()
})
```
Testar FINANCIAL_READ com justificativa obrigatória, sem ativar na seleção do
contrato; grant negado/expirado remove acesso e alerta o operador.
- [ ] Rodar `npm test -- src/support/GrantFlow.test.tsx`.
- [ ] **GREEN:** distinção de modo permanente: Somente leitura, Manutenção
autorizada e Acesso Financeiro/Fiscal temporário. Mostrar escopo e prazo real
retornado pelo servidor, botão encerrar e limpar estado quando contexto mudar.
Tempo do navegador apenas informa; servidor decide validade.
Sem handlers/capacidades de manutenção disponíveis, botão explica indisponibilidade.
- [ ] Commit: `feat: show temporary administrative authorization scope`.

## Referência histórica superada — gate

- [ ] Gate completo; GET protegido e mutação de teste devem falhar sem grant,
mesmo com PLATFORM_ADMIN, contrato selecionado e frontend manipulado.
- [ ] Confirmar ausência de probe/handlers de teste no app/OpenAPI de produção.
- [ ] Registrar phase-09.md e parar.

## Adendo executável — especificação da Fase 9 autorizada em 2026-10-03

**Base:** d360d30f51d76a5256a19095f0f00a401979b792.
**Branch:** feat/hiatlas-platform-phase-9.
**Autoridade:** requisitos detalhados da Fase 9 fornecidos pelo usuário; não executar Fase 10.

O catálogo desta entrega utiliza FINANCIAL_FISCAL e MAINTENANCE. A migração será 0008, posterior a 0007_support_sessions. Os exemplos FINANCIAL_READ e 0007_authorized_grants acima foram superados. A concessão financeira prepara somente leitura excepcional; não altera disponibilidade operacional, não cria dados financeiros nem libera escrita.

### Interfaces compartilhadas

- POST /api/grants: grant_type fechado, reason, reference, scopes tipados (action_code, entity_type, entity_id opcional); somente admin e reautenticação recente.
- GET /api/grants: histórico paginado do contrato, contexto administrativo normal.
- GET /api/grants/context: concessão vinculada ao contexto derivado informado em X-HiAtlas-Context.
- GET /api/grants/maintenance-actions: catálogo fechado registrado no servidor; vazio em produção.
- POST /api/grants/{id}/end: expected_version e encerramento auditado.
- GrantView: id, context_id, parent_context_id, grant_type, status, version, operator (user_id/display_name/platform_role), tenant_id/contract_id/tenant_name/contract_code/environment, reason/reference, started_at/expires_at/ended_at/revoked_at e scopes.
- Settings.grant_seconds: 1800 inicialmente; Settings.reauthentication_seconds existente: 300 inicialmente. Expiração limitada pela sessão e contexto pai; sem extensão por atividade ou reload.
- Apenas o id opaco do contexto derivado pode persistir em sessionStorage. Contexto pai conserva seu ciclo por aba; requests privilegiados usam explicitamente o contexto derivado.
- Contextos comuns não herdam privilégios. SupportSession READ_ONLY não pode ser elevada. Contexto derivado não autoriza gestão normal de acesso ou mutações genéricas.
- Registry de manutenção com injeção em testes; sem handlers, probes ou rotas de teste em produção.

### Tarefas e provas

- [x] Backend: modelos e FKs compostas, tipos/status fechados, lifecycle/versionamento, reauth, vínculo exato de sessão/contexto/contrato, registry/escopo tipado, policy central fail closed, auditoria atômica.
- [x] RED/GREEN de financeiro e manutenção: reauth antiga, Support, parent/sibling, nova sessão HTTP, module/capability ausentes, operational_available=false, ausência de handler, rollback de auditoria.
- [x] PostgreSQL real: constraints/grants, upgrade/downgrade/upgrade, A/A2/B, locks e corridas exigidas, sem privilégios owner/superuser em runtime.
- [x] Frontend: área exclusiva Admin, formulário/reauth/revisão, banner sticky, countdown informativo, encerramento/restauração, reload, expiração/revogação/logout, respostas tardias e isolamento entre abas.
- [x] E2E real Admin e Support: FastAPI/React/Chrome e PostgreSQL descartável; fake SMTP, sem dados demonstrativos operacionais; manutenção realmente indisponível.
- [x] Inspeção visual: desktop claro/escuro, mobile 390×844, contexto visível, teclado/foco e diálogos.
- [x] Revisões independentes backend/frontend; achados relevantes reproduzidos RED, corrigidos e confirmados GREEN.
- [x] Gate integral: pytest/Ruff/Vitest/oxlint/TypeScript/Vite/diff; nenhum PASS sem execução, zero skips obrigatórios.
- [x] Evidência phase-09.md sem segredos; commit, worktree limpa, serviços/banco/segredos temporários removidos; parar antes da Fase 10.

### Foco adicional de revisão

1. Reautenticação ou role removida enquanto criação aguarda lock: revalidar após a espera.
2. Encerramento concorrente/expiração/revogação: somente um estado terminal auditado, sem ressuscitar.
3. Contexto derivado usado por outra sessão ou outro contrato: negar sem revelar registros externos.
4. Contexto normal e aba independente: nenhuma elevação implícita ou persistência de capacidades.
5. Manutenção autorizada sem handler/action/domínio/versão: continuar negando escrita.
