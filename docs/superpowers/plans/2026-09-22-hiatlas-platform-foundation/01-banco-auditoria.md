# Fase 1 — Banco e auditoria — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** implementada e validada em 22/09/2026; parada para revisão antes da Fase 2. Ver [evidências e desvios de execução](../../validation/hiatlas-platform/phase-01.md).

**Goal:** Ter schema mínimo real e eventos imutáveis antes de qualquer mutação administrativa.
**Architecture:** PostgreSQL dedicado a testes, owner de migração separado do runtime, modelos por domínio e auditoria na mesma transação.
**Depende de:** nenhuma fase. **Não inclui:** login, API administrativa ou telas.

## Review Focus

- Banco errado: fixture recusa nomes sem sufixo _test (1.1).
- Vínculo tenant/contrato divergente: FK composta falha (1.1).
- Runtime proprietário/superusuário: teste e configuração recusam (1.1).
- Auditoria pode ser alterada com SQL direto: UPDATE/DELETE/TRUNCATE falham (1.2).
- Falha ao auditar: a mutação não persiste (1.2).

## Tarefa 1.1 — Migração mínima e ambiente testável

**Arquivos**
- Criar: backend/app/identity/models.py (User, PlatformRoleAssignment).
- Criar: backend/app/tenancy/models.py (Tenant, Contract).
- Criar: backend/app/audit/models.py (AuditEvent, AccessEvent).
- Criar: backend/app/db/models.py (imports de registro de modelos).
- Criar: backend/alembic/versions/0001_identity_tenancy_audit.py.
- Criar: backend/tests/conftest.py, backend/tests/test_foundation_schema.py.
- Criar: database/test-bootstrap.sql, scripts/check-platform-foundation.ps1.
- Modificar: backend/app/main.py, db/session.py, core/config.py,
  backend/alembic/env.py, backend/pyproject.toml, backend/.env.example.
- Documentar: database/README.md.

**Interfaces:** create_app(settings), get_db() e fixtures descritas no índice.
Configuração: DATABASE_URL do runtime e MIGRATION_DATABASE_URL do owner.
Testes recebem TEST_DATABASE_OWNER_URL e TEST_DATABASE_RUNTIME_URL por ambiente.
Não adicionar segredos a exemplos; não usar DATABASE_URL como fallback dos testes.

- [x] **RED:** criar caso com SQL real, sem SQLite:
```python
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import pytest

def test_contract_cannot_reference_missing_tenant(db):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("""
          INSERT INTO contracts (id, tenant_id, code, environment, active)
          VALUES ('00000000-0000-0000-0000-000000000001',
                  '00000000-0000-0000-0000-000000000099',
                  'TEST-001', 'TEST', true)
        """))
```
A primeira RED significativa deve detectar ausência de FK em schema mínimo;
tabela inexistente não valida o comportamento. Acrescentar teste de unicidade
de e-mail normalizado e de papel interno fora do enum.
- [x] Executar em backend: `uv run pytest tests/test_foundation_schema.py -v`.
- [x] **GREEN:** criar schema com UUID, datas UTC e constraints explícitas:
```python
# Contract.__table_args__
(
    UniqueConstraint("tenant_id", "id"),
    UniqueConstraint("code"),
    CheckConstraint("environment IN ('TEST','STAGING','PRODUCTION')"),
)
# PlatformRoleAssignment.role
CheckConstraint("role IN ('PLATFORM_ADMIN','PLATFORM_SUPPORT')")
```
User: id, email_normalized unique, display_name, password_hash nullable,
active, blocked, created_at, updated_at. Um papel interno por user_id.
Tenant: id, name, active. Contract: campos do teste, name, version e timestamps.
Modelo de auditoria inclui todos os campos da especificação, com par tenant/contract
ambos nulos para evento global ou ambos preenchidos com FK composta.
Não conceder cascata de exclusão a User/Tenant/Contract ou eventos.
- [x] Fixtures criam schema por Alembic no banco dedicado, usam runtime nos
requests e executam cleanup via owner somente nesse banco descartável.
Teste de concorrência pode usar conexões próprias e cleanup dedicado.
- [x] O gate novo verifica cada exit code do protocolo principal e falha cedo.
Não alterar scripts/check.ps1, web/ ou o preview legado nesta fase.
- [x] Rodar suíte backend e ensaiar upgrade/downgrade/upgrade no banco descartável.
Documentar owner/runtime e sufixo obrigatório; não executar downgrade fora dos testes.
- [x] Commit: incluído no commit único da Fase 1, conforme registro de execução.

## Tarefa 1.2 — Auditoria atômica e protegida no banco

**Arquivos**
- Criar: backend/app/audit/schemas.py, service.py.
- Criar: backend/tests/test_audit_integrity.py.
- Modificar: migração 0001 e database/test-bootstrap.sql, ainda não liberada.

**Interfaces:** AuditInput e append_event(db, event) -> UUID.
AuditInput é interno; API não aceita evento pronto enviado pelo usuário.

- [x] **RED:** provar proteção com conexão runtime, cada comando em uma transação:
```python
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

@pytest.mark.parametrize("statement", [
    "UPDATE audit_events SET action = 'changed'",
    "DELETE FROM audit_events",
    "TRUNCATE audit_events",
])
def test_runtime_cannot_destroy_audit(db_runtime, statement):
    with pytest.raises(DBAPIError):
        with db_runtime.begin() as connection:
            connection.execute(text(statement))
```
Acrescentar teste que insere Tenant e tenta evento inválido no mesmo db.begin();
após a exceção, outra sessão não encontra o tenant. Também testar AccessEvent.
- [x] Rodar `uv run pytest tests/test_audit_integrity.py -v`; registrar RED.
- [x] **GREEN:** owner cria tabelas; runtime recebe SELECT/INSERT em eventos,
sem ownership, superuser, CREATE no schema ou associação ao owner.
Não conceder UPDATE/DELETE/TRUNCATE aos eventos nem aos schemas futuros por
privilégio padrão. Grants específicos por tabela; função não usa SECURITY DEFINER.
```python
def append_event(db, event):
    values = event.model_dump()
    record = AuditEvent(**values)
    db.add(record)
    db.flush()
    return record.id
```
AuditInput rejeita extras e ações desconhecidas; snapshots vêm de schema do
evento. Criar primeiro evento tipado de bootstrap/identidade, sem senha/hash.
Campos request_id/ator são gerados pelo servidor; não logar raw request.
- [x] Testar INSERT válido, SELECT, negação de alteração e rollback transacional;
não basta examinar permissões concedidas em strings SQL.
- [x] Commit: incluído no commit único da Fase 1, conforme registro de execução.

## Quality gate e parada

- [x] Executar `./scripts/check-platform-foundation.ps1` na raiz com PostgreSQL disponível.
- [x] Confirmar testes reais de grants/constraints, health preservado e zero skips
por ausência de banco. Gate bloqueado se owner/runtime não forem distintos.
- [x] Revisar migração, ausência de secrets e escopo dos grants.
- [x] Registrar `docs/superpowers/validation/hiatlas-platform/phase-01.md`.
- [x] Parar. A fase 2 é uma rodada separada.

## Ajustes de execução aprovados

uv já é o gerenciador canônico; usar lockfile congelado. Não introduzir novos
pacotes para esta fase. Classificar grants: negócio sem DELETE/TRUNCATE;
auditoria/access_events append-only; alembic_version sem acesso do runtime.
Nenhuma tabela técnica de sessão/fila será criada antes de sua fase. Seus grants
futuros serão explícitos e limitados ao ciclo de vida, sem proibição indiscriminada.
