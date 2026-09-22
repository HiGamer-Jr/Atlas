# Fase 2 — Identidade e sessão — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** concluída e validada em 22/09/2026, com revisão independente e correção verificada. [Evidências](../../validation/hiatlas-platform/phase-02.md). Parada para revisão antes da Fase 3.

**Goal:** Autenticar identidades reais com revogação e controlar operadores internos.
**Architecture:** Sessão opaca persistida, Argon2id, CSRF e bootstrap local auditado.
**Depende de:** fase 1 aprovada. **Não inclui:** contexto de cliente ou convites.

## Review Focus

- E-mail inexistente e senha incorreta têm mesma resposta pública (2.1).
- Revogação/expiração observadas na requisição seguinte (2.1).
- CSRF pré-login e origem inválida não criam sessão (2.1).
- Bootstrap concorrente ou segundo bootstrap não cria novo administrador (2.2).
- Último administrador protegido inclusive em concorrência (2.2).

## Tarefa 2.1 — Autenticação HTTP real

**Arquivos**
- Criar: backend/app/identity/passwords.py, schemas.py, sessions.py, routes.py,
  dependencies.py, rate_limits.py.
- Criar: backend/app/core/security.py (origem/CSRF) e errors.py.
- Criar: backend/alembic/versions/0002_sessions.py.
- Criar: backend/tests/test_auth_api.py, test_session_security.py.
- Modificar: identity/models.py, core/config.py, api/router.py, main.py,
  backend/pyproject.toml, uv.lock e tests/conftest.py.

**Interfaces:** Principal, require_principal, GET /auth/csrf, POST /auth/login,
POST /auth/logout, GET /auth/me, POST /auth/reauthenticate.
Sessão: token_hash, CSRF hash, user_id, created_at, last_seen_at, expires_at,
revoked_at e reauthenticated_at. Registrar tentativas/limites no PostgreSQL.

- [x] **RED:** os clientes fixture fazem login via HTTP, sem bypass da dependência:
```python
def test_logout_revokes_session(admin):
    assert admin.get("/api/auth/me").status_code == 200
    assert admin.post("/api/auth/logout").status_code == 204
    assert admin.get("/api/auth/me").status_code == 401

def test_client_cannot_choose_platform_role(client):
    csrf = client.get("/api/auth/csrf").json()["token"]
    response = client.post("/api/auth/login",
        headers={"X-CSRF-Token": csrf, "Origin": "https://testserver"},
        json={"email": "member@example.test", "password": "test-only-password",
              "platform_role": "PLATFORM_ADMIN"})
    assert response.status_code == 422
```
Testar cookies, CSRF ausente/incorreto, origem externa, resposta 401 genérica,
expiração idle/absoluta e bloqueio de conta após login.
- [x] Rodar `uv run pytest tests/test_auth_api.py tests/test_session_security.py -v`.
- [x] **GREEN:** adicionar argon2-cffi com lockfile pelo uv; hash e verify
encapsulados, hash fictício para a verificação de usuário inexistente.
```python
from argon2 import PasswordHasher
from secrets import token_urlsafe
from hashlib import sha256

hasher = PasswordHasher()
def hash_session_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()

def new_session_token() -> tuple[str, str]:
    token = token_urlsafe(32)
    return token, hash_session_token(token)
```
Invalidar cookie antigo no login; CSRF por sessão e preauth com expiração.
Sessão: 30 minutos idle, 8 horas absoluta. Limite inicial: 10 falhas por
identificador/15 minutos e 100 por origem/15 minutos, configurável; guardar
identificador limitado/hasheado, não body ou senha. Falhas distribuídas entre
processos usam o mesmo contador transacional. Origem atrás de proxy só é
confiada quando proxy está explicitamente configurado.
- [x] Fixture admin/support insere atores fictícios usando hash real; obtém CSRF,
posta login e atualiza CSRF após rotação. Nenhuma rota secreta para testes.
- [x] Usar relógio injetável para teste de expiração; runtime usa datetime UTC real.
Registrar sucessos/falhas sanitizados sem evento que bloqueie para sempre a conta.
- [x] Commit: `feat: authenticate persistent sessions with csrf and revocation`.

## Tarefa 2.2 — Bootstrap e operadores internos

**Arquivos**
- Criar: backend/app/identity/bootstrap.py, operators.py.
- Criar: backend/tests/test_bootstrap.py, test_platform_operators.py.
- Modificar: identity/routes.py, schemas.py, sessions.py e audit/schemas.py.
- Documentar: docs/operations/hiatlas-identity.md.

**Interfaces:** CLI `uv run python -m app.identity.bootstrap --email EMAIL`,
senha via getpass; sem senha em argumentos ou output.
POST /api/platform/operators/{user_id}/role com role, confirmation e password;
POST /api/platform/operators/{user_id}/status para active/blocked explícitos.
A confirmação contém target_user_id e target_role, ambos conferidos.

- [x] **RED:** fixture `last_admin` é cliente HTTP cujo usuário é o único admin
ativo no banco do teste; ids retorna seu id em `last_admin_user`.
```python
def test_cannot_disable_last_admin(last_admin, ids):
    response = last_admin.post(
        f"/api/platform/operators/{ids['last_admin_user']}/status",
        json={"active": False})
    assert response.status_code == 409

def test_support_cannot_promote_itself(support, ids):
    response = support.post(
        f"/api/platform/operators/{ids['support_user']}/role",
        json={"role": "PLATFORM_ADMIN",
              "confirmation": {"target_user_id": ids["support_user"],
                               "target_role": "PLATFORM_ADMIN"},
              "password": "test-only-password"})
    assert response.status_code == 403
```
Nesta fase ids fixture contém admin_user, support_user, last_admin_user; fase 3
amplia o mesmo dict. Testar confirmação errada, senha errada, bootstrap duplo
e dois admins tentando se desativar ao mesmo tempo, com conexões separadas.
- [x] Rodar `uv run pytest tests/test_bootstrap.py tests/test_platform_operators.py -v`.
- [x] **GREEN:** transação com lock PostgreSQL único para bootstrap e alterações
da população de administradores; recontar ativos antes de gravar:
```python
db.execute(text("SELECT pg_advisory_xact_lock(720260922)"))
# Reconsultar os administradores ativos sob o lock antes de cada alteração.
```
Conferir role existente no servidor e confirmação ligada ao alvo; senha nunca
integra AuditInput. Reautenticação recente: até 5 minutos, limites de tentativa
do login também aplicáveis. CLI só primeiro admin; contas posteriores por convite
quando a fase 5 existir. Rotas atuais promovem somente identidade já existente.
Proibir autopromoção, preservar último admin e revogar sessões do alvo.
- [x] Testar bootstrap por stdin protegido/subprocesso isolado ou função que recebe
segredo em memória; capturar stdout/stderr e garantir ausência de senha/hash.
- [x] Commit: `feat: bootstrap and manage internal operators safely`.

## Quality gate e parada

- [x] Gate completo do índice; PostgreSQL obrigatório, fixtures sem auth mocks.
- [x] Provar revogação após reiniciar app com mesmo banco e efeito concorrente único.
- [x] Documentar que frontend antigo ainda é demo e não se tornou seguro nesta fase.
- [x] Registrar phase-02.md na pasta de validação; parar antes da fase 3.
