# Fase 5 — Convites, recuperação e ciclo de vida — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Status:** Implementada e validada em 2026-09-28; parada para revisão. Commit consolidado das tarefas 5.1/5.2: `ef6b7c5`. [Evidências e ajustes de execução](../../validation/hiatlas-platform/phase-05.md). Frontend consolidado em AccessLifecycle.tsx; entrega incerta usa UNKNOWN sem reenvio automático; ausência global de transporte retorna 503 uniforme também na recuperação pública.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** não executado. Não marcar checkbox por existir apenas o código de exemplo neste plano.

**Goal:** Gerenciar acesso sem expor senha/token ou afetar outros contratos.
**Architecture:** Tokens de uso único, outbox transacional cifrada e memberships independentes.
**Depende de:** fase 3; páginas React usam fase 4. **Não inclui:** MFA.

## Review Focus

- Duas requisições consomem o mesmo token: apenas uma vence (5.1).
- Reenvio deixa mensagem velha na fila: worker cancela token revogado (5.1).
- SMTP ausente/falhou: mostrar solicitação/erro, nunca entregue (5.1).
- Identidade já existe em outro cliente: convite não enumera vínculos (5.2).
- Inativação e bloqueio independentes, com revogação imediata só no vínculo (5.2).

## Tarefa 5.1 — Tokens e e-mail seguro

**Arquivos**
- Criar: backend/app/identity/tokens.py, email_schemas.py, outbox.py,
  delivery.py, email_transport.py, access_routes.py.
- Criar: backend/alembic/versions/0004_access_tokens_outbox.py.
- Criar: backend/tests/test_access_tokens.py, test_email_outbox.py.
- Criar: frontend/src/auth/AcceptInvite.tsx, ResetPassword.tsx,
  PasswordRecovery.test.tsx.
- Modificar: identity/models.py, config.py, db/models.py, api/router.py,
  pyproject.toml, uv.lock, frontend/src/App.tsx.

**Interfaces:** AccessEmailRequest: purpose INVITE/RESET, recipient_user_id,
membership_id opcional, request_id; queue_access_email -> id, sem token.
EmailTransport.send(message: EmailMessage) -> None; exceção significa falha.
EmailMessage: to, subject, text. SMTP configurado pelo ambiente.
deliver_batch(limit) -> DeliverySummary(sent, failed, cancelled).
CLI worker: `uv run python -m app.identity.delivery --once --limit 20`.
Rotas POST /api/auth/recovery (resposta genérica), /reset-password e /accept-invite.

- [x] **RED:** fixture `mailbox` é lista de EmailMessage recebidas por adaptador
falso no limite SMTP; token só é extraído desse e-mail no código de teste:
```python
from urllib.parse import urlparse, parse_qs
def test_reset_token_is_single_use(client, mailbox, reset_delivery):
    reset_delivery()  # fixture chama recovery + deliver_batch para usuário fictício
    link = next(word for word in mailbox[0].text.split() if word.startswith("https://"))
    token = parse_qs(urlparse(link).fragment)["token"][0]
    payload = {"token": token, "new_password": "a-new-test-password-123"}
    assert client.post("/api/auth/reset-password", json=payload).status_code == 204
    assert client.post("/api/auth/reset-password", json=payload).status_code == 400
```
Fixtures client e reset_delivery preparam CSRF pré-auth válido e origem de teste.
Adicionar expiração, token de finalidade errada, reenvio, concorrência real
com dois clientes e rollback se fila não for gravada.
- [x] Rodar `uv run pytest tests/test_access_tokens.py tests/test_email_outbox.py -v`.
- [x] **GREEN:** token aleatório 32 bytes, hash persistido, expiração 24h convite/
30min reset; consumo com UPDATE condicionado a consumed_at/revoked_at/expiry:
```python
stmt = update(SecurityToken).where(
    SecurityToken.token_hash == token_hash,
    SecurityToken.consumed_at.is_(None),
    SecurityToken.revoked_at.is_(None),
    SecurityToken.expires_at > now,
).values(consumed_at=now).returning(SecurityToken.id)
```
Finalidade também faz parte do WHERE. Atualizar senha, consumir token e revogar
sessões na mesma transação. Novo convite revoga anteriores por destinatário e
finalidade, preservando a validade de finalidades distintas.
Outbox usa cifra autenticada da biblioteca cryptography (chave fora do banco)
e nunca serialize segredo/token para diagnóstico. Worker tem claim transacional
com SKIP LOCKED, prazo de lease e máximo de 5 tentativas com atraso limitado.
SMTP não garante exatamente uma entrega após crash: documentar possível
duplicata, mas token permanece único e invalida mensagens obsoletas.
- [x] Registrar queued/sent/failed/cancelled, apagar ciphertext após entrega/
expiração, revalidar token imediatamente antes do envio. Testar erro do SMTP e
ausência de configuração (503 para operação interna; recovery pública genérica).
- [x] Páginas capturam token do fragment, removem URL visível após captura,
enviam no body protegido por CSRF e usam Referrer-Policy: no-referrer.
Teste de frontend: token ausente, expirado, consumido e sucesso sem auto-login.
- [x] Commit: `feat: deliver single-use access invitations and password resets`.

## Tarefa 5.2 — Gestão de vínculos e status

**Arquivos**
- Criar: backend/app/tenancy/memberships.py.
- Criar: backend/tests/test_membership_lifecycle.py,
  test_membership_invitations.py.
- Modificar: tenancy/routes.py, schemas.py, identity/access_routes.py,
  tests/conftest.py.

**Interfaces:** GET/POST /api/memberships; filtros nome/e-mail/status dentro do
contexto. POST /{id}/invite e /{id}/reset-password.
PATCH /{id}/status com active e/ou blocked, expected_version.
POST /memberships recebe email, display_name e role_id; nunca password ou platform_role.
POST /api/platform/operators/invite é exclusivo de admin, com reautenticação/
confirmação da fase 2; usa a mesma entrega segura, sem identidade de tenant.

- [x] **RED:**
```python
from tests.helpers import select_context
def test_support_invitation_respects_role_eligibility(support, ids):
    scope = select_context(support, ids["contract_a"])
    response = support.post("/api/memberships", headers=scope, json={
        "email": "new@example.test", "display_name": "Usuário de teste",
        "role_id": ids["role_finance"]})
    assert response.status_code == 403

def test_activate_does_not_unblock(support, ids):
    scope = select_context(support, ids["contract_a"])
    response = support.patch(f"/api/memberships/{ids['blocked_member']}/status",
        headers=scope, json={"active": True, "expected_version": 1})
    assert response.status_code == 200
    assert response.json()["blocked"] is True
```
Acrescentar blocked_member às fixtures. Testar bloqueio A preservando B,
invalidar contexto de usuário ativo ao bloquear, convite de usuário existente,
tentativa de gerenciar operador interno e convite com papel não elegível.
- [x] Rodar `uv run pytest tests/test_membership_lifecycle.py tests/test_membership_invitations.py -v`.
- [x] **GREEN:** vínculo novo fica pendente até aceite; conta existente mantém
senha e demais contratos. Identidade interna não é alvo desses endpoints.
Convite de usuário existente não revela existência ou vínculos externos;
destinatário confirma posse por sessão autenticada/reauth antes de aceitar.
Primeiro convite permite definir senha; convite não é reset implícito.
```python
# Dentro da transação, depois de conferir contexto e autorização:
membership.active = command.active if command.active is not None else membership.active
membership.blocked = command.blocked if command.blocked is not None else membership.blocked
membership.version += 1
```
Usar expected_version e rollback em auditoria; status global só por fluxo
interno autorizado. Suporte não edita e-mail global nem cria papel interno
por campos extras. Revalidar elegibilidade do role no aceite também; se mudou
para sensível, cancelar atribuição pendente e exigir reemissão por admin.
- [x] Commit: `feat: manage contract memberships without cross-client effects`.

## Quality gate e parada

- [x] Gate completo, consumo concorrente, revogação após reinício e outbox
persistida. Não afirmar entrega real por usar adaptador falso.
- [x] Garantir testes sem e-mails reais e sem dumps de tokens em relatórios.
- [x] Registrar phase-05.md e parar.
