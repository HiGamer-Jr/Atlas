# Fase 10 — Handlers e manutenção controlada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** não executado. Não marcar checkbox por existir apenas o código de exemplo neste plano.

**Goal:** Preparar correções e reprocessamentos sem abrir edição arbitrária de dados.
**Architecture:** Registro explícito em código; cada domínio fornece schema, validação e projeção de auditoria próprios.
**Depende de:** fase 9. **Não inclui:** handlers de COMEX, estoque, financeiro ou obras ainda inexistentes.

## Review Focus

- Handler desconhecido/desabilitado: falha fechada e sem alteração (10.1).
- Cliente envia antes/ator/tabela/SQL/payload extra: schema rejeita (10.1).
- Estado muda após prévia: conflito, sem sobrescrever mudança concorrente (10.1).
- Auditoria falha: rollback inclui dado de domínio (10.1).
- Retry/reprocessamento concorrente: uma execução idempotente por chave (10.2).

## Tarefa 10.1 — Contrato tipado de correção e execução transacional

**Arquivos**
- Criar: backend/app/maintenance/corrections.py, registry.py, schemas.py.
- Criar: backend/tests/test_correction_handlers.py,
  tests/fixtures/correction_domain.py.
- Criar: frontend/src/maintenance/CorrectionsPage.tsx,
  CorrectionsPage.test.tsx.
- Modificar: platform/ContractShell.tsx.

**Interfaces:** CorrectionCommand contém handler_key, entity_id, expected_version,
reason, reference opcional e comando de domínio tipado em Python, não dict livre.
apply_correction(db, principal, scope, command)->audit_event_id.
Registry é imutável após startup. Handler define capability, command_type,
load_scoped, apply e audit_snapshot. O schema concreto proíbe extras.

Não criar POST universal que aceite payload JSON e escolha tabela/coluna.
Cada domínio futuro registra sua rota concreta e seu formulário concreto.
Na fundação, catálogo de handlers de produção fica vazio; a UI não promete
correções operacionais inexistentes. Testes registram somente handler de teste.

- [ ] **RED:** fixture `correction_case` cria tabela de domínio apenas no banco
descartável via owner, com grants runtime limitados; registra handler tipado
que altera name nessa tabela, consulta por tenant/contract e permite simular
falha da fronteira de auditoria. Seus métodos test-only são:
apply(expected_version, reason)->id, read_name()->str, fail_audit()->context manager.
```python
import pytest
def test_audit_failure_rolls_back_domain_change(correction_case):
    before = correction_case.read_name()
    with correction_case.fail_audit():
        with pytest.raises(RuntimeError, match="audit unavailable"):
            correction_case.apply(expected_version=1, reason="Teste controlado")
    assert correction_case.read_name() == before
```
O fixture chama apply_correction real, não substitui política nem banco.
Acrescentar sucesso com before/after do servidor, conflito, handler inexistente,
suporte negado, scope externo e extras como sql/table/column/actor/before rejeitados.
- [ ] Rodar `uv run pytest tests/test_correction_handlers.py -v`.
- [ ] **GREEN:** registry[key] ou erro específico; validar grants/capability e
reconsultar entidade/version dentro da transação. A fronteira é:
```python
handler = registry.require(command.handler_key)
typed = handler.command_type.model_validate(command.domain_command)
entity = handler.load_scoped(db, scope, command.entity_id)
before = handler.audit_snapshot(entity)
handler.apply(entity, typed, expected_version=command.expected_version)
after = handler.audit_snapshot(entity)
# append_event usa before/after tipados, Principal e AccessScope do servidor.
# A unidade de trabalho faz commit somente depois do evento.
```
domain_command só existe internamente como modelo específico; sem endpoint para
submeter dict genérico. load_scoped não admite selecionar tabela/coluna.
Handler deve validar invariantes do domínio e não contornar regras fiscais.
Desconhecido -> indisponível; versão divergente -> 409; autorização -> 403.
- [ ] CorrectionsPage lista handlers disponíveis e seus formulários conhecidos;
catálogo vazio exibe “Nenhuma correção administrativa disponível neste contrato”.
Não gerar formulário a partir de schema arbitrário.
- [ ] Commit: `feat: add typed audited correction handler boundary`.

## Tarefa 10.2 — Registros de processamento e reprocessamento restrito

**Arquivos**
- Criar: backend/app/maintenance/models.py, processing.py, routes.py,
  projections.py.
- Criar: backend/alembic/versions/0008_processing_runs.py.
- Criar: backend/tests/test_reprocessing.py, test_processing_diagnostics.py.
- Criar: frontend/src/maintenance/ProcessingPage.tsx,
  ProcessingPage.test.tsx.
- Modificar: db/models.py, api/router.py e shell.

**Interfaces:** GET /api/processings (projeção sanitizada) e
POST /api/processings/{id}/reprocess com reason, reference e idempotency_key.
request_reprocess -> id de nova ProcessingRun; não aceita payload operacional.
Handler de processamento define validade da repetição e aplicação do domínio.
Produção sem handlers retorna catálogo vazio/indisponibilidade, sem job de mentirinha.

- [ ] **RED:** fixture `processing_case` registra handler só de teste e insere
execução FAILED no contrato A. Acrescenta ids["failed_run"] e possui query
persistida count_retries() para asserção:
```python
from tests.helpers import select_context
def test_reprocessing_is_idempotent(admin, ids, processing_case, maintenance_grant):
    scope = select_context(admin, ids["contract_a"])
    maintenance_grant(admin, scope, ids["failed_run"])
    payload = {"reason": "Repetir após correção", "reference": "SUP-TEST",
               "idempotency_key": "retry-test-0001"}
    path = f"/api/processings/{ids['failed_run']}/reprocess"
    first = admin.post(path, headers=scope, json=payload)
    second = admin.post(path, headers=scope, json=payload)
    assert first.status_code in (200, 202)
    assert second.json()["id"] == first.json()["id"]
    assert processing_case.count_retries() == 1
```
maintenance_grant usa POST /grants e reauth real da fase 9, não bypass.
Testar chaves simultâneas, mesma chave payload diferente -> 409, suporte,
handler ausente, execução de outro contexto e diagnóstico contendo sentinel-secret.
- [ ] Rodar `uv run pytest tests/test_reprocessing.py tests/test_processing_diagnostics.py -v`.
- [ ] **GREEN:** índice único (tenant_id,contract_id,source_run_id,idempotency_key),
lock da execução e fingerprint do comando; reservar execução e auditar na
mesma transação. Worker de domínio revalida autorização antes de despachar
ação adiada; grant expirado cancela, não executa sob privilégio antigo.
Não criar worker genérico que execute código ou payload arbitrário.
Status e erro são códigos allowlist, sem traceback/body/token.
- [ ] Tela: suporte consulta diagnóstico sanitizado, nunca vê botão executar;
admin só reprocessa tipo registrado com concessão vigente e confirmação.
- [ ] Commit: `feat: track scoped idempotent reprocessing and diagnostics`.

## Quality gate e parada

- [ ] Gate completo, rollback transacional e concorrência reais em PostgreSQL.
- [ ] Nenhum handler/rota/tabela de teste aparece no schema/app de produção.
- [ ] Declarar claramente: infraestrutura entregue, handlers de negócio ainda
não existentes indisponíveis. Nenhuma edição SQL/JSON genérica.
- [ ] Registrar phase-10.md e parar.
