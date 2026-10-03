# HiAtlas — Plano executável da fundação de plataforma

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar identidade, isolamento por contrato, administração e suporte reais, em onze fases pequenas e verificáveis.

**Architecture:** Evoluir o monólito modular FastAPI/PostgreSQL existente. Autorização e transações ficam no servidor; o React consome a API e nunca decide privilégios por um perfil escolhido no navegador. Auditoria nasce antes da primeira mutação administrativa.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, PostgreSQL; React/TypeScript, Vite, Vitest, Testing Library; pytest e Ruff. Manter os pisos de versão do projeto e atualizar lockfiles somente com dependências necessárias à fase.

**Spec:** [Especificação aprovada e ajustada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).

**Status:** Fases 1–8 revisadas/aprovadas. Fase 9 implementada, revisada independentemente e validada; parada para revisão do usuário. Fases 10–11 não iniciadas. [Evidências da Fase 9](../../validation/hiatlas-platform/phase-09.md).
**Raiz confirmada:** `D:\Atlas`. Caminhos de código abaixo são relativos a essa raiz ou ao worktree escolhido na execução.

## Global Constraints

- PLATFORM_ADMIN e PLATFORM_SUPPORT são internos, separados de TenantRole.
- Administrador do Cliente fica reservado, sem implementar esse perfil agora.
- support_assignable começa false. Apenas PLATFORM_ADMIN pode alterá-lo.
- Suporte só associa perfil elegível do contrato, não administrativo, Financeiro/Fiscal ou sensível.
- OrganizationNode usa WORKSITE/Canteiro; Project/Obra pertence a Obras & Projetos.
- Seleção explícita de tenant/contrato e contexto visível são obrigatórios.
- Financeiro/Fiscal: concessão temporária, explícita, justificada e auditada.
- Correções exclusivamente por handlers de domínio registrados e testados.
- Sem edição arbitrária de tabelas, colunas, SQL ou payloads genéricos.
- Flags, parâmetros e integrações: infraestrutura mínima; sem gerenciadores genéricos.
- Senhas, hashes, tokens e segredos nunca aparecem nas APIs, diagnósticos ou auditoria.
- Nenhum hard delete de negócio ou exclusão de auditoria pela aplicação; runtime
  não recebe DELETE/TRUNCATE de tabelas de negócio, nem ownership.
- Sem migração automática de identidades ou registros demonstrativos.
- Sem envio para destinatários reais, alteração de produção ou implantação durante testes.
- TDD por comportamento e quality gate por fase; não executar as onze fases como um bloco.

## Review Focus

1. Perfil renomeado ou alterado depois de marcado support_assignable: revalidar capacidades/sensibilidade e impedir escalada. Testes nas fases 3 e 6.
2. Mesmo tenant com dois contratos: ids válidos ainda devem ser isolados; acesso em outra aba não deve mudar o contexto original. Fases 3, 4 e 8.
3. Bloqueio, revogação ou expiração entre leitura e escrita: revalidar dentro da transação, sem depender de cache do navegador. Fases 2, 5, 8, 9 e 10.
4. Concorrência em token, último administrador, alteração de perfil e reprocessamento: somente um efeito autorizado e auditado. Fases 2, 5, 6 e 10.
5. Sucesso aparente sem infraestrutura: SMTP indisponível, banco ausente e handler inexistente devem falhar explicitamente; teste pulado não aprova gate. Fases 1, 5, 10 e 11.

## Fases, dependências e entregáveis

| Fase | Entrega verificável | Depende de | Plano |
|---|---|---|---|
| 1 | Banco, migração inicial e trilha de auditoria imutável | Nada | [Banco e auditoria](01-banco-auditoria.md) |
| 2 | Login, sessão, bootstrap e operadores internos | 1 | [Identidade](02-identidade.md) |
| 3 | Contextos e RBAC com perfis elegíveis ao suporte | 2 | [Contextos e permissões](03-contextos-permissoes.md) |
| 4 | Login real e seleção de contrato no React | 3 | [Interface autenticada](04-interface-autenticada.md) |
| 5 | Convite, recuperação e ciclo de vida de acesso | 3; integração visual depois de 4 | [Acessos seguros](05-acessos-seguros.md) |
| 6 | Telas de usuários, perfis e auditoria contextual | 4 e 5 | [Gestão de acesso](06-gestao-acesso.md) |
| 7 | Organização com WORKSITE e módulos contratados | 3 e 6 | [Organização e módulos](07-organizacao-modulos.md) |
| 8 | Sessão de suporte somente leitura | 6 e 7 | [Atendimento](08-atendimento.md) |
| 9 | Concessões Financeiro/Fiscal e manutenção autorizada | 8 | [Concessões temporárias](09-concessoes-temporarias.md) |
| 10 | Handlers de correção, reprocessamento e diagnóstico | 9 | [Manutenção controlada](10-manutencao-controlada.md) |
| 11 | Regressão integrada e manual operacional | Todas | [Validação final](11-validacao-final.md) |

Executar na ordem numérica. Dependências adicionais esclarecem interfaces;
não são autorização para paralelizar ou pular fases. Cada fase produz commit
revisável e relatório próprio, e encerra sua execução no gate. Uma nova rodada
inicia somente a próxima fase prevista, sem continuar automaticamente o pacote.

Fases 1–3 são entregas de infraestrutura/API, sem afirmar que o frontend legado
já está protegido. Após a fase 4, o caminho autenticado real estará isolado do
demo. A liberação a usuários reais exige o gate final, não apenas o primeiro login.

## Fronteiras e arquivos

Não criar toda a estrutura vazia na fase 1. Cada plano cria os arquivos de que precisa.

| Caminho | Responsabilidade | Primeira fase |
|---|---|---|
| backend/app/db/session.py, models.py | unidade de trabalho e registro dos modelos | 1 |
| backend/app/identity/ | User, hash, sessão, bootstrap, operadores, tokens e outbox | 1–2; tokens em 5 |
| backend/app/tenancy/ | tenants, contratos, contexto e memberships | 1; contexto em 3 |
| backend/app/platform/ | papéis, catálogo, autorização e perfis | 3 |
| backend/app/audit/ | eventos tipados, persistência e projeções | 1; consulta em 6 |
| backend/app/organization/ | nós, unidades e módulos do contrato | 7 |
| backend/app/support/ | atendimento e concessões temporárias | 8–9 |
| backend/app/maintenance/ | registros de handlers e reprocessamento | 10 |
| backend/alembic/versions/ | uma revisão incremental por fase que altera schema | 1 em diante |
| backend/tests/conftest.py, helpers.py | fixtures PostgreSQL e clientes autenticados reais | 1–3 |
| frontend/src/auth/, api/, platform/ | identidade real, HTTP e portal interno | 4 |
| frontend/src/platform/access/, audit/ | gestão contextual | 6 |
| frontend/src/platform/organization/ | estrutura e módulos | 7 |
| frontend/src/support/, maintenance/ | atendimento e operações autorizadas | 8–10 |
| frontend/src/demo/ | entrada isolada para o protótipo existente | 4 |
| scripts/check-platform-foundation.ps1 | gate da fundação sem mexer no preview legado | 1 |
| docs/superpowers/validation/hiatlas-platform/ | evidências por fase | 1 em diante |

## Contratos compartilhados

A implementação de cada contrato está atribuída à fase indicada. Não criar
abstrações adicionais para casos ainda inexistentes.

### HTTP e transações

- Prefixo `/api`; sessão por cookie. `GET /api/auth/csrf` prepara token/cookie
  pré-login; mutações usam `X-CSRF-Token` e origem permitida.
- Sessão autenticada rotaciona token e CSRF. `GET /api/auth/me` retorna id,
  nome, papel interno opcional e capacidades mínimas, sem segredos.
- `X-HiAtlas-Context` contém id opaco de AccessContext pertencente à sessão.
  Não é tenant_id, não é credencial autossuficiente.
- `POST /api/contexts` com `contract_id` seleciona explicitamente o contrato.
  `DELETE /api/contexts/{id}` encerra somente contexto da própria sessão.
- Sucesso usa schema explícito. Erros: `{"code": "...", "message": "...",
  "request_id": "..."}`, com 401/403/404/409/422/429/503 conforme especificação.
- Cada mutação tem transação única: revalidação, alteração, auditoria e commit.
  Serviço não chama commit interno; rota/unidade de trabalho controla o commit.
- Tenant/contract vêm do contexto; payload de negócio não os redefine.
- Datas UTC timezone-aware; versões inteiras para concorrência otimista.

### Tipos e serviços

| Interface | Definição/responsabilidade | Fase |
|---|---|---|
| `create_app(settings: Settings) -> FastAPI` | app configurável para fixture; manter export `app` e health | 1 |
| `get_db() -> Iterator[Session]` | sessão SQLAlchemy por request com rollback em exceção | 1 |
| `append_event(db: Session, event: AuditInput) -> UUID` | evento tipado, sem commit próprio | 1 |
| `Principal` | dataclass imutável: user_id, session_id, platform_role | 2 |
| `require_principal(...) -> Principal` | dependência FastAPI que consulta sessão persistida | 2 |
| `require_context(...) -> AccessScope` | id, tenant_id, contract_id, session_id, actor_id | 3 |
| `require_capability(db, principal, scope, capability) -> None` | nega por padrão, relê estado vigente | 3 |
| `role_support_eligible(role, permissions) -> bool` | flag + classificação + catálogo sensível | 3 |
| `ApiClient.request<T>(path, options) -> Promise<T>` | credenciais, CSRF, contexto e AbortSignal | 4 |
| `queue_access_email(db, request: AccessEmailRequest) -> UUID` | grava token/outbox; não revela token | 5 |
| `deliver_batch(limit: int) -> DeliverySummary` | worker SMTP; resultado de entrega persistido | 5 |
| `start_support(db, principal, scope, member_id) -> SupportSession` | contexto derivado de leitura | 8 |
| `authorize_grant(db, principal, scope, request: GrantRequest) -> Grant` | concessão temporária explícita | 9 |
| `apply_correction(db, principal, scope, command: CorrectionCommand) -> UUID` | handler tipado e auditoria atômica | 10 |
| `request_reprocess(db, principal, scope, run_id, key, reason) -> UUID` | execução idempotente por handler | 10 |

`AuditInput` usa ator, tipo de evento, tenant/contrato opcionais para eventos
globais, entity_type/id, before/after sanitizados, reason/reference e request_id.
Não aceitar esse objeto diretamente do navegador. Campos before/after derivam
de schemas permitidos no serviço dono do evento.

`AccessScope` não congela permissões: mudanças são consultadas a cada operação.
`Principal` é criado no servidor e não permite autenticação por cabeçalho de papel.

### Fixtures e exemplos de teste

Fase 1 cria `settings`, `db_owner`, `db_runtime`, `db` (sessão SQLAlchemy transacional),
`app` e `client` (TestClient). Banco dedicado termina em `_test`; teste
recusa URL para banco de aplicação. Owner/runtime distintos por configuração.
Sem URLs de teste, falhar com mensagem operacional; não pular silenciosamente.

Fase 2 acrescenta `admin` e `support`: TestClient com identidades fictícias
persistidas e login HTTP real; configuração de teste usa origem
`https://testserver`. Cada cliente possui cookies/CSRF próprios.
Senhas de teste só existem em fixtures; nunca em seeds de produção.

Fase 3 acrescenta `ids: dict[str, str]`:
`tenant_a`, `tenant_b`, `contract_a`, `contract_a2` (mesmo tenant),
`contract_b`, `member_a`, `member_b`, `role_basic` (elegível),
`role_opt_out` (não elegível), `role_finance`, `role_admin`.
Memberships das fixtures têm usuários sem papel interno. Inserção por ORM serve
somente para preparar cenários; as ações verificadas passam pela API real.

Fase 3 cria `backend/tests/__init__.py` e `backend/tests/helpers.py`:
```python
def select_context(client, contract_id: str) -> dict[str, str]:
    response = client.post("/api/contexts", json={"contract_id": contract_id})
    assert response.status_code == 201, response.text
    return {"X-HiAtlas-Context": response.json()["id"]}
```
Headers CSRF já estão no cliente das fixtures após login. Retornar contexto
separado permite testar duas abas com a mesma sessão sem trocar estado global.

Fixtures posteriores estão definidas no plano que as introduz. Testes de
integração não substituem autorização, persistência ou transações por mocks.
Transporte SMTP falso e relógio controlado são fronteiras de teste permitidas.

## Protocolo TDD por tarefa

1. Escrever o teste de comportamento indicado no plano.
2. Executar o teste focado e registrar RED pelo comportamento ausente. Erro
   de import, ambiente ou banco não é evidência suficiente: fornecer somente
   o esqueleto necessário para coletar o teste e obter falha de asserção.
3. Implementar o mínimo para GREEN; nenhuma funcionalidade antecipada.
4. Rodar teste focado e suíte do componente, refatorar mantendo GREEN.
5. Revisar diff e escopo, executar gate da fase e registrar evidências.
6. Commit com arquivos explícitos da tarefa/fase; não incluir alterações alheias.

## Quality gate de cada fase

O script da fase 1 executará a partir da raiz:
```powershell
Push-Location backend
uv run pytest
uv run ruff check app tests
Pop-Location
Push-Location frontend
npm test
npm run lint
npm run build
Pop-Location
git diff --check
```
Cada chamada é verificada individualmente; qualquer exit code diferente de zero
interrompe o script. Repetir o gate completo no encerramento de cada fase;
durante RED/GREEN usar comandos focados. Não repetir suíte sem mudança ou causa.

Além da suíte: testes reais de PostgreSQL do escopo, revisão de autorização,
migração upgrade e rollback apenas em banco descartável, e inspeção de UI
quando a fase altera telas. Nenhuma migração de teste aponta para banco real.
Rollback aqui significa ensaio técnico, não autorização para apagar produção.

Evidência em `docs/superpowers/validation/hiatlas-platform/phase-NN.md`:
commit, tarefa, comando RED e asserção, comando GREEN e resultado, comandos do
gate e exit codes, migrações testadas, riscos/bloqueios, escopo entregue.
Não registrar URLs com senhas, tokens, e-mails reais ou conteúdo de cookies.

**PASS:** todos os critérios verificáveis executados, zero falhas/pendências críticas.
**BLOCKED:** dependência operacional ausente ou verificação obrigatória não executada.
**FAIL:** comportamento incorreto. Não passar à próxima fase em BLOCKED ou FAIL.

## Ambiente observado, sem inferir disponibilidade

uv, node e npm foram encontrados no PATH. Docker não foi encontrado no PATH
durante a inspeção; isso não demonstra ausência de PostgreSQL instalado ou remoto.
Antes da fase 1, localizar um PostgreSQL de teste autorizado ou configurar instância
isolada. Não mexer no volume atlas_pgdata nem revelar arquivos .env.

A tarefa foi aberta originalmente em D:\Cargo.Ops; D:\Atlas foi confirmado pelo
usuário. Escrita pode exigir a permissão de filesystem da ferramenta. Criar
worktree de implementação apenas ao iniciar execução e após verificar instruções
locais e alterações existentes; não copiar segredos para contornar permissões.

## Cobertura dos seis ajustes

| Ajuste | Aplicação na especificação | Prova no plano |
|---|---|---|
| support_assignable + exclusão de sensíveis | §§5, 9 e 15 | F3 política, F5 convites, F6 lista/atribuição |
| WORKSITE separado de Project | §§5 e 15 | F7 rejeita PROJECT e não toca o domínio de obras |
| Fases pequenas verificáveis | cabeçalho e §§15–16 | 11 planos; gate e parada em cada fase |
| Financeiro temporário e auditado | §§9–10 | F9 testa ausência, expiração e contexto errado |
| Infraestrutura mínima de flags/parâmetros/integrações | §§4–5, 12–13 | F7 sem CRUD/modelos antecipados |
| Handlers tipados e testados | §§11–12 | F10 falha fechado e rollback transacional |

## Handoff

Revisar este índice e a fase 1 antes da execução. Escolher:
- **Inline:** mesmo agente implementa uma fase por rodada; revisão independente
  conforme skill de execução, após gate e antes de integração.
- **Com subagentes:** tarefas implementadas e revisadas separadamente; maior custo
  de coordenação e contexto.

Recomendação: inline, uma fase por rodada, porque contratos de identidade e
isolamento são sequenciais e o usuário pediu entregas pequenas. Nenhuma delegação
foi realizada para escrever estes planos. Não iniciar implementação nesta tarefa
de planejamento. A autorização de execução deve identificar a fase inicial;
não interpretar aprovação do plano como ordem para executar todas de uma vez.

## Ajustes finais aprovados antes da Fase 1

- Plano APROVADO; executar somente a Fase 1 e parar para revisão antes da Fase 2.
- Cabeçalho único: `X-HiAtlas-Context` em implementação, testes e documentação.
- AccessContext por aba, em memória e/ou sessionStorage. localStorage é proibido
  para sessão autenticada e contexto. Preferência de tema não é sessão.
- uv já é canônico neste repositório (uv.lock, README e scripts/check.ps1).
  Preservar gerenciador e lockfile; não migrar gerenciador nesta fundação.
- Privilégios por categoria: negócio SELECT/INSERT/UPDATE, sem DELETE/TRUNCATE;
  auditoria/acessos SELECT/INSERT, sem UPDATE/DELETE/TRUNCATE; técnicas somente
  operações necessárias por tabela. alembic_version é exclusivo da migração.
  Nada de grants em todas as tabelas presentes/futuras.
- Fase 11 incluirá recuperação administrativa break-glass documentada e testada,
  sem endpoint público, senha padrão ou bypass da auditoria.
