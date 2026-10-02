# Fase 8 — Sessão de Suporte somente leitura

Implementada e validada para revisão. Somente Fase 8; Fase 9 não iniciada.

## Proveniência

- Branch: `feat/hiatlas-platform-phase-8`.
- Base aprovada: `62d55088ac6ca4aa0b20ed1babc4432d1fc7da5e` (Fase 7).
- Commit da implementação: `7b68f8652f0bb1501a166e0a59c2d2276ddd8546`; commit final de evidências identificado no histórico Git desta branch.
- Worktree existente e isolada; sem deploy, push ou merge.

## Entrega e schema

SupportSession persistente aceita somente READ_ONLY. Operador autenticado continua sendo o Principal e o ator real; o alvo é o membership exato do contrato selecionado. Não há autenticação, cookie, token ou credencial emitida para o usuário visualizado. Contexto derivado está vinculado à mesma sessão HTTP, operador, tenant e contrato.

Migração incremental `0007_support_sessions`, após `0006_organization_modules`. Colunas técnicas `operator_id`, `operator_role` e `parent_context_id` representam operator_user_id, support_platform_role e created_from_access_context_id; não há aliases duplicados. FKs compostas vinculam membership/usuário e ambos os contextos ao mesmo escopo e sessão HTTP. Checks limitam modo, papel, status, datas, alvo e texto. Contexto derivado é único; índice único parcial permite um atendimento ACTIVE por contexto pai.

Runtime recebe apenas SELECT/INSERT/UPDATE em support_sessions, sem DELETE/TRUNCATE. Auditoria permanece imutável. Owner e runtime são separados; runtime não é owner, superuser nem membro de papel privilegiado. Não houve migração de produção.

## Autorização e lifecycle

A política transversal falha fechada cobre rotas futuras não declaradas seguras, inclusive GET sem dependência de banco, contexto pai/derivado e chamada sem contexto. Validação antecede a rota e se repete na transação do endpoint. Verbo GET sozinho não concede autorização. POST/PATCH/PUT/DELETE de negócio e gestão de acesso são negados; controles estreitos preservam identidade e CSRF do operador.

EffectiveAccess intercepta o contexto derivado antes dos grants internos e aplica interseção entre permissões atuais do alvo, limite fechado de leitura do operador, módulos contratados/ativos e restrições de suporte. Financeiro/Fiscal, gestão, auditoria completa, credenciais e configurações sensíveis são excluídos no servidor, inclusive para Admin. Não existe backend operacional entregue nesta fase: o workspace mostra metadados reais permitidos e indisponibilidade; não usa demo.

Validade inicial configurável de 30 minutos, limitada pela sessão principal, idle inicial e contexto pai. Leituras não renovam o idle. Sessão, papel vigente, identidade, alvo, tenant/contrato, contexto, perfil e módulos são revalidados após locks. Mudança do papel interno também revoga o atendimento; a trilha conserva o papel original da sessão.

Início, encerramento, logout/revogação e observação de expiração persistem estado, revogação do filho e audit tipado atomicamente. Observer persiste transição terminal antes de rejeitar; falha no endpoint fecha/rollback sua transação antes de observar novamente. Falha de auditoria impede mutação. Negação de negócio conserva operador e escopo comprovados pelo servidor em AccessEvent sanitizado; header estrangeiro não atribui ator alheio.

Frontend separa Provider, banner, diálogo, histórico e Workspace. Faixa permanente distingue operador/usuário visualizado, contrato, perfil, prazo e modo. Gestão/switch não são montados enquanto atendimento restaura ou está ativo. Só id opaco permanece em sessionStorage por aba. Reload revalida autenticação, contexto e atendimento. AbortSignal e gerações descartam respostas tardias. Encerramento depende do commit, limpa dados e devolve foco ao portal normal. Histórico contextual inclui modo e duração comprovável por datas do servidor.

## RED / GREEN executados

| Achado/comportamento | RED confirmado | GREEN confirmado |
| --- | --- | --- |
| API de início ausente | Esperado 201, recebido 404; matriz inicial 32 falhas/6 passes | API, bindings e gate implementados; matriz incluída nos 487 finais |
| Contexto independente com contrato inativo | POST administrativo retornou 201 | Estado vigente exige contrato/tenant/ator/sessão/contexto válidos |
| Papel interno alterado / fronteira CSRF | Leitura e CSRF retornaram 200 indevidamente | Revogação por papel; CSRF de suporte rejeita sem cair em preauth ou apagar cookie |
| Negação antecipada sem proveniência | Três casos sem evento scoped esperado | Parent/child/sem contexto registram ator real e escopo; caso estrangeiro neutro |
| Histórico ENDED vence empate com ACTIVE | Mesmo started_at e UUID histórico maior fizeram pai expor 15 capabilities | Consulta ACTIVE explícita suspende pai; regressão determinística passa |
| Descoberta tardia / deadline compartilhado / workspace obsoleto | Gestão visível enquanto verify pendia; notice perdida; metadata mantida após foco | Fail closed imediato, timer pai preserva notice e observação, revision refaz workspace |
| Revogação pai primeiro / storage indisponível / erro de end | Notice perdida e erro fora do modal | Referência opaca em memória, cancelamento e notice preservados, erro dentro do diálogo |
| Histórico sem modo/duração | Duas regressões falharam | READ_ONLY traduzido e duração calculada; ACTIVE mostra Em andamento |

Os achados da revisão independente receberam correção e releitura. A preparação inicial do E2E tentou criar contexto sem vínculo durante atendimento e recebeu negação prevista; foi corrigida para abrir os fluxos independentes antes de suspender o pai. Isso foi correção do harness, não falha de autorização do produto.

## Quality gate executado

Comando integrado: `scripts/check-platform-foundation.ps1`, com configuração temporária do banco descartável. Exit 0 na árvore final da lógica; após simplificar apenas o texto explicativo do Workspace, frontend completo/lint/build novamente executados antes do commit.

| Verificação | Resultado |
| --- | --- |
| Backend pytest completo | PASS — 487 testes, 388,62 s; zero skips |
| Ruff app/tests/alembic | PASS — zero achados |
| Ruff fixture controlada | PASS |
| Frontend Vitest completo | PASS — 216 testes / 13 arquivos; zero skips |
| oxlint | PASS — zero achados |
| TypeScript / Vite build | PASS |
| git diff --check | PASS — working e staged diff conferidos antes dos commits |
| Migrações upgrade/downgrade/upgrade | PASS — lifecycle completo e 0006→0007→0006→0007 em PostgreSQL real |
| Grants / constraints reais | PASS — 15 testes específicos de schema/grants, além do gate anterior |
| Concorrência suporte | PASS — 13 casos com conexões independentes e espera por locks observada |
| Isolamento A/A2/B | PASS — backend e E2E reais |
| E2E Suporte/Admin | PASS — FastAPI, React/Vite e Chrome reais |
| Light/dark / desktop / mobile 390×844 | PASS — execução e inspeção das capturas |
| Teclado/foco / banner sticky | PASS — browser real, Enter/Escape e foco início/fim; banner visível após scroll |
| Revisão independente backend/frontend | Concluída, sem achados pendentes no escopo revisado |
| Cleanup e worktree limpa | PASS — API/Vite/PostgreSQL encerrados, portas fechadas, diretórios e segredos temporários removidos; árvore final conferida após commit |

Há um aviso herdado de depreciação Starlette/httpx. Não há testes ignorados ou falha encoberta pelo aviso.

## PostgreSQL e concorrência

PostgreSQL 18.6 real descartável, restrito ao loopback e atestado pelo harness. Owner/runtime seguros e separados; grants e recusa física de DELETE/TRUNCATE foram executados (42501). Constraints de modo/lifecycle, escopo, target/user, AuthSession/operator, parent/child e unicidade foram testadas no banco (23514/23503/23505). Credenciais e configuração ficam somente no diretório temporário e não são reproduzidas aqui.

Races cobrem dois encerramentos idempotentes com um evento terminal; leitura aguardando locks de membership, identidade global, contexto, contrato, perfil e AuthSession; expiração após espera; logout/leitura concorrentes; gestão de operadores com locks exclusivos em fluxos independentes; início aguardando alvo/contexto e perda de validade. Não houve ressurreição ou efeito não autorizado. Rollback de início/fim/observação quando auditoria falha está na suíte.

## E2E e inspeção visual

Harness: `scripts/phase08_browser_fixture.py` e `frontend/e2e/phase08.mjs`. Transporte FakeEmailTransport controlado; nenhum SMTP externo/destinatário real. HTTP não foi mockado. Fixture sintética fica apenas no banco descartável.

Suporte e Admin: login real, contexto A, alvo contextual, motivo/referência, READ_ONLY, identidade e cookie do operador preservados, workspace real sem operações fictícias, escritas diretas negadas para todos os verbos protegidos via pai/filho/sem contexto, gestão ausente, reload, encerramento/manual idempotente e histórico. Expiração controlada e revogação do pai descartam dados e retornam ao fluxo seguro.

Abas A2/B com contextos normais previamente abertos permanecem independentes da aba em atendimento A; reload não sobrescreve ids locais. IDs estrangeiros de membership e suporte são negados; A não aparece em B. Novo login HTTP do mesmo operador não restaura o atendimento anterior. Storage contém somente tema e ids opacos permitidos. Zero erros de página e zero requisições externas monitoradas.

Capturas inspecionadas:

- [Início contextual e foco](phase-08-visual/support-start.png).
- [Desktop claro](phase-08-visual/support-readonly-light.png) e [escuro](phase-08-visual/support-readonly-dark.png).
- [Mobile 390×844](phase-08-visual/support-readonly-mobile.png).
- [Confirmação contextual de encerramento](phase-08-visual/support-end-confirmation.png).
- [Histórico com modo/duração](phase-08-visual/support-history-dark.png).
- [Expiração](phase-08-visual/support-expired.png) e [acesso revogado](phase-08-visual/support-access-denied.png).
- [Admin sob as mesmas restrições](phase-08-visual/admin-readonly-light.png).

## Revisão independente

- [Backend: revisão, achados, correções e releituras](phase-08-review-backend.md).
- [Frontend: revisão, achados, correções e releituras](phase-08-review-frontend.md).

Revisores não implementaram os componentes revisados. A disposição é leitura estática independente; execução de gates e browser foi feita separadamente pelos implementadores/root. Leitura estática não foi marcada como teste executado.

## Riscos e limites

- Nenhum módulo operacional está entregue; somente metadados reais e indisponibilidade são exibidos. FINANCE/Fiscal não são liberados.
- Contextos independentes válidos já existentes continuam isolados. Criar/selecionar contexto sem vínculo durante atendimento é bloqueado; encerrar para trocar o fluxo atual. Não há troca silenciosa de usuário ou contrato.
- Não há polling para renovar sessão nem worker de expiração em background. Estado terminal persiste nos hooks/primeira observação autorizada; servidor nega imediatamente quando invalidação é observada.
- Locks de lifecycle serializam conservadoramente requests; esta fase não declara capacidade de throughput ou infraestrutura distribuída.
- Motivo/referência são dados textuais limitados, não linguagem executável. Não inserir credenciais/dados sensíveis nesses campos.
- Sem manutenção, WRITE, impersonação, concessões financeiras, correções, reprocessamento, help desk, MFA, deploy, merge ou Fase 9.

## Encerramento

Implementação em 7b68f86. A última execução frontend após ajuste apenas da mensagem do Workspace confirmou 216 testes/13 arquivos em 36,72 s, oxlint zero e build TypeScript/Vite. O E2E consumiu as fontes finais e passou; capturas foram inspecionadas.

API, Vite e PostgreSQL descartável foram encerrados; os três listeners temporários não existem mais. Diretório atestado contendo banco, binários, credenciais de owner/runtime, chave outbox, TLS, logs e captura de falha foi removido. Scratch desta Fase 8 e workspace auxiliar do plano foram removidos após consolidar as evidências. Processos verificados não permanecem ativos. Dependências/caches regulares e worktree foram preservados.

Commit final de documentação registra estas evidências e a parada para revisão. O hash desse próprio commit deve ser consultado no histórico Git (não há autorreferência circular). Sem deploy, push, merge ou início da Fase 9.
