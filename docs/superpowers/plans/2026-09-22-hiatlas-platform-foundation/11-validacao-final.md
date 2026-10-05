# Fase 11 — Validação integrada e operação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** executado e validado tecnicamente na Fase 11; encerrado para revisão, sem deploy. [Evidências finais](../../validation/hiatlas-platform/phase-11.md). Os exemplos originais abaixo permanecem como referência de planejamento; a execução real e equivalências estão registradas no fechamento.

**Goal:** Consolidar evidências e tornar a fundação instalável sem confundir infraestrutura com domínios ainda ausentes.
**Architecture:** Regressão por API/DB/UI, documentação reproduzível e configuração que falha fechada em produção.
**Depende de:** gates aprovados das fases 1–10. **Não inclui:** deployment automático.

## Review Focus

- Migração fresh versus banco da fase anterior: mesma estrutura e grants (11.1).
- Restart do backend perde revogação/token/outbox: teste deve detectar (11.1).
- Produção aceita chave padrão, demo ou cookie inseguro: recusar startup (11.2).
- Documento afirma envio SMTP real sem evidência: distinguir transporte falso (11.2).
- Health/schema público inclui rotas test-only ou senhas: reprovar (11.1).

## Tarefa 11.1 — Regressão de ponta a ponta e migrações

**Arquivos**
- Criar: backend/tests/test_platform_acceptance.py,
  test_migration_chain.py, test_production_surface.py.
- Criar: frontend/src/platform/PlatformAcceptance.test.tsx.
- Modificar: scripts/check-platform-foundation.ps1 apenas para incluir comandos
de integração necessários já introduzidos; não ignorar falhas do legado.

**Interfaces:** reutilizar create_app, fixtures reais e APIs das fases anteriores.
Não introduzir ferramenta E2E/dependência nova sem necessidade demonstrada.
Inspeção em navegador real complementa testes React e HTTP; não os substitui.

- [ ] **RED:** criar testes contra aplicação reiniciada e mesma persistência:
```python
from fastapi.testclient import TestClient
from app.main import create_app

def test_logout_remains_revoked_after_restart(admin, settings):
    old_cookies = dict(admin.cookies)
    assert admin.post("/api/auth/logout").status_code == 204
    with TestClient(create_app(settings), base_url="https://testserver") as restarted:
        restarted.cookies.update(old_cookies)
        assert restarted.get("/api/auth/me").status_code == 401
```
Fixtures settings/app são da fase 1. Acrescentar fluxo admin cria contrato,
perfil elegível, convite, aceite, suporte associa perfil, bloqueio só nesse
contrato, atendimento somente leitura e consulta redigida de auditoria.
Verificar também dois contratos do mesmo tenant.
Se o teste já passar por cobrir contratos entregues, registrar como regressão;
não inventar RED. Uma falha nova gera tarefa corretiva TDD própria na fase dona.
- [ ] Rodar `uv run pytest tests/test_platform_acceptance.py tests/test_migration_chain.py tests/test_production_surface.py -v`.
- [ ] **GREEN:** corrigir somente falhas comprovadas, com teste focado antes da
correção. Migration chain ensaia head, revisão anterior e retorno a head no
banco descartável com grants runtime; comparar constraints/índices/permissões.
Não fazer downgrade em banco com dados reais.
- [ ] Testar exposição de schema:
```python
def test_production_has_no_test_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert all("/test-" not in path for path in paths)
    assert "/api/maintenance/sql" not in paths
```
Testes de segredo verificam respostas contra sentinelas conhecidas, não imprimem
corpo com segredo ao falhar. Teste nenhum campo password_hash/session_token em /me.
- [ ] Commit: `test: verify platform foundation acceptance and migration chain`.

## Tarefa 11.2 — Configuração e manual reproduzível

**Arquivos**
- Criar: docs/operations/hiatlas-platform-foundation.md,
  docs/superpowers/validation/hiatlas-platform/phase-11.md.
- Modificar: backend/.env.example, frontend/.env.example, README.md,
  backend/app/core/config.py.
- Criar: backend/tests/test_production_config.py.

**Interfaces:** ambiente nomeado development/test/production; secrets via ambiente.
Configuração de produção usa runtime sem superuser/ownership, MIGRATION_DATABASE_URL
somente no processo de migração, HTTPS, origem pública exata, outbox key externa.
Não carregar credenciais de migração no runtime web nem devolvê-las em health.

- [ ] **RED:**
```python
import pytest
from pydantic import ValidationError
from app.core.config import Settings

@pytest.mark.parametrize("unsafe", [
    {"session_cookie_secure": False},
    {"demo_enabled": True},
    {"public_origin": "http://example.test"},
])
def test_production_refuses_unsafe_config(valid_production_config, unsafe):
    with pytest.raises(ValidationError):
        Settings(**(valid_production_config | unsafe))
```
valid_production_config é fixture com valores fictícios válidos apenas para
construção de Settings (não conecta/remete e-mail). Testar também chave inválida,
origem curinga, credenciais padrão e SMTP parcial; SMTP ausente pode desabilitar
entrega explicitamente, nunca entrar como enviado.
- [ ] Rodar `uv run pytest tests/test_production_config.py -v`.
- [ ] **GREEN:** validação de Settings com erros sem interpolar segredos.
Documentar comandos em ordem e ambientes separados:
```powershell
# Na pasta backend, com MIGRATION_DATABASE_URL de banco autorizado:
uv run alembic upgrade head
uv run python -m app.identity.bootstrap --email operador@example.test
uv run fastapi run app/main.py --port 8001
# Em processo separado, depois de SMTP/chave configurados:
uv run python -m app.identity.delivery --once --limit 20
```
Manual distingue teste/example de identidade real; senha via prompt protegido.
Descrever deployment same-origin HTTPS, reverse proxy, worker periódico externo,
backup/restore, rotação de chaves, limpeza de outbox expirada e retenção sem
exclusão de auditoria pela aplicação. Nenhum cron/automation será criado nesta tarefa.
- [ ] Manual lista cada endpoint/capacidade entregue e indisponibilidades:
MFA, Central de Operações completa, regras financeiras/fiscais, importadores,
conectores, handlers de negócio sem implementação e gerenciadores genéricos.
- [ ] Commit: `docs: document secure platform foundation operation`.

## Quality gate final e encerramento

- [ ] Rodar gate completo uma vez após últimas correções, sem falhas ou skips
de infraestrutura. Executar check legado separadamente quando aplicável;
se falhar, informar a falha por nome e resolver impacto antes da liberação.
- [ ] Inspecionar login, seleção, gestão, auditoria, atendimento e grants em
navegador real nos dois temas; confirmar contexto permanente.
- [ ] Relacionar os 21 critérios da especificação a testes/evidências concretos.
- [ ] Verificar diff/commits por escopo, nenhum segredo e nenhum dado demo no app real.
- [ ] Registrar resultados reais, limitações de SMTP e ausência de handlers,
sem chamar indisponibilidade de sucesso.
- [ ] Entregar revisão final antes de integração/deploy; não publicar automaticamente.

## Tarefa 11.3 — Recuperação administrativa break-glass

**Arquivos:** criar backend/app/identity/recover_admin.py e
backend/tests/test_admin_recovery.py; ampliar docs/operations/hiatlas-platform-foundation.md.
**Interfaces:** CLI local `uv run python -m app.identity.recover_admin --user-id UUID`;
sem rota HTTP. Uso restrito ao operador de infraestrutura autorizado, com acesso
protegido ao host/credencial de manutenção, e validação externa da identidade alvo.

- [ ] RED: recuperar último PLATFORM_ADMIN existente com senha perdida; exigir
  motivo, chamado/referência e confirmação do id/e-mail verificados. Rejeitar alvo
  externo/inexistente, papel inesperado e execução sem credencial autorizada.
- [ ] Testar que falha ao inserir auditoria aborta a recuperação e preserva senha,
  status e sessões anteriores. Testar revogação de todas as sessões após sucesso.
- [ ] GREEN: CLI separado do bootstrap; não criar usuário nem administrador extra.
  Bloquear concorrência pelo mesmo lock dos operadores e registrar ator de
  recuperação, alvo, horário, motivo, referência e resultado, sem senha/hash/token.
  Senha nova pelo próprio operador autorizado via entrada protegida ou fluxo
  seguro ao titular; sem argumento de senha, senha padrão ou segredo em stdout.
- [ ] A identidade de banco de recuperação tem somente SELECT/UPDATE necessários
  de identidade/sessões e INSERT em auditoria; não recebe DELETE/UPDATE/TRUNCATE
  da trilha. Nenhum caminho desliga ou ignora auditoria.
- [ ] Rodar `uv run pytest tests/test_admin_recovery.py -v`, depois gate completo.
- [ ] Documentar pré-requisitos de infraestrutura, verificação fora de banda,
  aprovação da organização responsável, execução, validação do login restaurado
  e revisão posterior do evento. Ensaio apenas com identidade fictícia em _test.
- [ ] Provar em OpenAPI que não há endpoint de recuperação administrativa.
- [ ] Commit: `feat: add audited offline administrator recovery procedure`.

Este é um requisito da Fase 11 aprovada, não trabalho autorizado para a Fase 1.

## Fechamento executado — 2026-10-05

- [x] Regressão integrada:767 testes backend e282 frontend, zero skips obrigatórios.
- [x] Migrações full-chain/incremental/down-up, comparação real de schema/ACLs e grants PostgreSQL.
- [x] Backup/restore em banco novo, invalidação técnica auditada e login posterior.
- [x] Configuração production fail-safe, health/schema/headers/logging sanitizado e recuperação offline com33 testes focados.
- [x] Browser real:8 rodadas Admin/Support/READ_ONLY/grants/manutenção controlada/reprocess/build,78 capturas, A/A2/B, temas/mobile/teclado.
- [x] Reviews independentes backend/frontend, achados corrigidos e confirmados; Ruff/oxlint/TypeScript/Vite/diff gates.
- [x] Runbook, sanity, demo readiness apenas documental, release Foundation v1 e21 critérios rastreados nas evidências.
- [x] Serviços/banco/dumps/segredos temporários removidos; branch/worktree preservadas para revisão; sem push/merge/tag/release/deploy.

A cadeia de migrações foi comprovada pelo script operacional com PostgreSQL, em vez de duplicar um test_migration_chain.py. A cobertura frontend existente permaneceu funcional: nenhuma alteração de comportamento React exigiu novo PlatformAcceptance.test.tsx. O wrapper de checks existente foi preservado; seus comandos foram executados com os scripts adicionais de operação/browser. RED só foi registrado para falhas/lacunas efetivamente reproduzidas. As extensões do escopo vieram dos requisitos aprovados da Fase11, sem novo domínio operacional.
