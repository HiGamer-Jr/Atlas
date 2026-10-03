# Fase 10 — Manutenção controlada, correções, reprocessamentos e diagnósticos

Data: 2026-10-03. Somente Fase 10; parada obrigatória antes da Fase 11.

- Branch: `feat/hiatlas-platform-phase-10`.
- Base aprovada: `1b01fa9ee3d0a826b5346ffc28745d590453aa67`.
- Commit de implementação: pendente do encerramento.
- Migração incremental: `0009_processing_runs`, após `0008`.
- Handlers reais de produção registrados: **zero**. Registro normal vazio, sem operações fictícias.
- Handler controlado: `FIXTURE_NODE_RENAME`, somente fixture/factory e entry frontend separados de teste.

## Implementação

Registry imutável, ações conhecidas, schemas concretos fechados e callback de domínio tipado. Sem SQL console, tabela/coluna escolhida pelo browser, JSON Patch, script runner, queue universal ou fallback genérico. A aplicação normal não importa fixture de domínio e seu build frontend não contém ação, formulário ou comprovante controlados.

CorrectionCommand valida action_code, entidade, expected_version, input específico, motivo e referência. Estado/Before/ator/contexto vêm do servidor. Preview sanitizado obrigatório com Antes/Depois/efeitos e comprovante HMAC vinculado ao comando, identidade real, contexto, grant, versão e prazo. Callback de preview roda em SAVEPOINT sempre revertido. Confirmar consulta/lock/revalida novamente, exige a mesma revisão e versão, aplica integridade do handler e grava auditoria na mesma transação. 409 exige nova revisão; falha da auditoria desfaz domínio e execução.

ProcessingRun persistente possui catálogo fechado de status/códigos, origem conhecida, idempotência/fingerprint, operador real, contexto/grant, request_id, timestamps e versão. Reprocessamento síncrono transacional e explicitamente registrado, sem efeito externo arbitrário. Mesma chave autorizada retorna a execução existente antes do bloqueio de linhagem; chaves novas não repetem linhagem com efeito concluído ou resultado pendente/desconhecido. FAILED exige decisão explícita/elegibilidade do domínio; UNKNOWN não tem retry automático. Falha do handler desfaz seu SAVEPOINT e persiste FAILED sanitizado com auditoria; falha da auditoria desfaz também a reserva.

Diagnósticos usam projeção/códigos permitidos, sem motivos completos, fingerprint, payload bruto, SQL, stack trace, segredo ou configuração interna. Suporte só recebe ações conhecidas explicitamente seguras e classificação não sensível, com entidade/origem reduzidas; Financeiro/Fiscal e ações desconhecidas são excluídos server-side. Suporte não recebe menu Manutenção nem autorização de execução.

UI Admin real com operações, diagnóstico paginado e ausência verdadeira de handlers; adapter específico no caminho controlado. Confirmações mostram empresa/contrato/ambiente, ação/entidade, motivo/referência e Antes/Depois. Banner MAINTENANCE permanente. Intenção/chave de reprocessamento ficam apenas em memória, sobrevivem à revalidação do mesmo grant e desaparecem no término/revogação. Projeção retornada precisa corresponder à ação, entidade, origem, id/request_id, versão e status/códigos antes de sucesso. Reload não persiste dados de negócio; somente contexto opaco em sessionStorage.

## RED / correção / GREEN

| Verificação | RED observado / origem | Correção e GREEN |
| --- | --- | --- |
| Registry/API/preview tipados | Implementador: registry aberto/API ausente e 23 falhas de correção | Schemas fechados e fronteira transacional; coordenador executou suíte focada completa 92/92 |
| Preview com flush e revisão alterada | Implementador/revisão: callback podia persistir escrita e comprovante omitia After/efeitos | SAVEPOINT revertido e HMAC completo; incluído no GREEN 92 do coordenador |
| Schema Any e CHECK NULL | Implementador/revisão: schema aberto e retry nulo aceitável no PostgreSQL | Tipo concreto e CHECK nonnull; incluído no GREEN 92 |
| Diagnóstico sensível e handler após lock | Implementador/revisão: classificação isolada e callback selecionado antes do refresh | Allowlist segura e nova resolução pós-lock; incluído no GREEN 92 |
| Nova chave após sucesso/UNKNOWN | Implementador: quatro RED de nova intenção na mesma linhagem | Guard persistente e replay autorizado primeiro; testes reais incluídos no GREEN 92 |
| Restauração perde chave / sucesso incoerente | Frontend: log RED 12/26, revisão independente FE01/FE02 | Provider estável em memória e validação integral; GREEN 26/26 e gate fresco 282/282 |
| Mensagem contextual de conflito | E2E controlado encontrou texto genérico de 409; teste exact-text RED | Mensagem exigida e nova revisão explícita; GREEN manutenção 32/32, gate FE 282/282 |
| Fixtures extras de concorrência | Coordenador: dados residuais e revogação sem ended_at falharam setup/CHECK; problemas do teste | Reset atestado e estado terminal coerente; 7/7 testes adicionais aprovados |

Relatos RED do backend são atribuídos ao implementador; o coordenador observou execuções GREEN novas. Revisores executaram leitura estática, não testes ou banco. Os relatórios independentes preservam o histórico dos achados.

## Quality gate

| Gate | Resultado |
| --- | --- |
| pytest backend completo, PostgreSQL real | PASS — 700/700, 614.20s, zero skips |
| Backend focado da Fase 10 | PASS — 92/92, 102.38s, zero skips |
| Concorrência e negação direta adicionais | PASS — 12/12, 13.78s |
| Ruff (configuração backend) | PASS — app/tests/alembic + fixture E2E |
| Vitest completo | PASS — 282/282, 16 arquivos, 19.16s, zero skips |
| oxlint | PASS — exit 0 |
| TypeScript/Vite | PASS — 75 módulos; build normal sem fixture controlada |
| git diff --check | PASS — conteúdo staged e worktree |
| E2E configuração normal Admin/Suporte | PASS — Chrome/FastAPI/React/PostgreSQL reais |
| E2E controlado completo | PASS — correção/conflito/reprocess/replay/auditoria/A/A2/B/teclado/mobile reais |

## PostgreSQL, migração e grants

PostgreSQL descartável 18.6 em loopback, atestado pelo harness. Owner/runtime separados, não-superusers; runtime não owner, sem CREATE/DDL/TRUNCATE/DELETE nas novas tabelas. Migração apenas owner, sem produção. Auditoria continua imutável.

0009 cria ProcessingRun e chaves compostas de contrato/entidade/operador/AuthSession/AccessContext/grant/action scope/source run, unicidade persistente de idempotência, CHECKs de status/códigos/timestamps/versão/chave/fingerprint. Adiciona unicidades de referência nas tabelas da Fase 9. Downgrade remove somente a extensão incremental. Testes reais exercitam upgrade/downgrade/upgrade, permissões SELECT/INSERT/UPDATE e negação DELETE/TRUNCATE; validação incluída no pytest completo 700/700; ciclo/grants repetidos após remover whitespace sem alterar SQL: 4/4 em 1.12s.

## Concorrência e isolamento

Fixtures Tenant A/Contract A, Tenant A/Contract A2 e Tenant B/Contract B. Testes reais cobrem entidade/run/contexto/scope externos ocultos, action/input não registrados, Financeiro/READ_ONLY/Suporte negados, nova AuthSession e grant expirado. Same-key concorrente gera uma execução/efeito/audit; chaves distintas para mesma origem produzem um efeito e conflito. Reprocess resolve handler vigente após lock da origem. Correção revalida expiry/versão/domínio após lock da entidade.

Adendo do coordenador usa dois administradores distintos, sessões/contextos/grants/receipts próprios: uma correção 200, outra 409, domínio versão 2 e um evento de sucesso. Seis causas durante lock da fronteira de autorização — sessão, contexto pai, contrato, tenant, role e grant — negam a mutação, preservam domínio/versão e não criam auditoria de sucesso. Esses casos complementam locks de entidade/origem; não afirmam que uma revogação sem lock possa vencer uma transação já autorizada/serializada.

## E2E e inspeção

Roteiros versionados: frontend/e2e/phase10.mjs, phase10-controlled.html e scripts/phase10_browser_fixture.py. Chrome headless real, FastAPI real, React/Vite HTTPS real, PostgreSQL descartável real. FakeEmailTransport controlado, nenhum SMTP real, identidades/textos sintéticos, nenhum mock HTTP ou demo autenticado.

Configuração normal: Admin login/contrato A → Manutenção → registry vazio/mensagem verdadeira; request MAINTENANCE desconhecido negado. Suporte sem menu e endpoints diretos 403. Desktop claro/escuro e 390×844 sem overflow externo; storage e recursos externos verificados.

Controlado: login Admin → contrato A → solicitação MAINTENANCE com entidade, motivo, referência e reauth → revisão → banner → preview Antes/Depois sem mutação → confirmação → entidade alterada e auditada. Segunda conexão altera versão; confirmação recebe 409, preserva a alteração concorrente e exige novo preview. Reprocess de run FAILED conhecido → novo run SUCCEEDED; replay da mesma chave retorna o mesmo id, um único efeito e uma única execução. Nova chave conflita, reload mantém grant válido e não oferece novo reprocess da linhagem concluída. Contextos A2/B, entidade/run/scope externos, ação desconhecida e write de gestão de usuário são negados. Encerramento via Enter/Escape/confirmação restaura contexto normal e invalida o derivado; audit event real e Before/After consultados no contrato, ocultos em B. Suporte sem menu e endpoints de manutenção negados.

## Revisão independente

- Backend: phase-10-review-backend.md — seis achados tratados, sem bloqueador remanescente na versão congelada; adendo dos sete testes extras revisado.
- Frontend: phase-10-review-frontend.md — FE01/P1 e FE02/P2 fechados, sem novo bloqueador; gates atribuídos corretamente ao implementador/coordenador.

## Riscos e limitações

- Não há handler real operacional nesta fase; registro de produção vazio é comportamento correto.
- Escopo físico inicial acompanha organization_node da fundação/Fase 9. Um domínio operacional futuro exige schema/referências, política, projeção e formulário próprios; registrar uma string não fornece acesso.
- Comprovante usa chave efêmera por processo. Reinício ou outro processo sem a mesma chave exige novo preview, falhando fechado; não é autorização persistente nem dado de sessão.
- Execução transacional síncrona; efeitos externos não transacionais e processamento distribuído não fazem parte desta entrega.
- Reload descarta intenção/chave em memória; servidor impede repetição da linhagem. Não há persistência de comando no browser.
- UNKNOWN exige decisão/prova explícita do domínio; não há retry automático. Lifecycle de grants herdado da Fase 9 nega imediatamente e persiste transições na observação segura.
- Warning herdado Starlette/httpx, sem skip obrigatório ou falso PASS.
- Sem módulos operacionais, MFA, dupla aprovação, impersonação, deploy, merge ou Fase 11.

## Encerramento

API/Vite próprios encerrados e listeners ausentes. PostgreSQL próprio parado e cluster descartável removido. Diretório temporário da Fase 10, senhas/chaves de teste, TLS, logs brutos e scratch removidos após validação dos caminhos e ausência de reparse points; workspace SDD antigo preservado. Portas próprias 55490/8010/5180 sem listeners. E2E normal/controlado completo executados e capturas inspecionadas. Commits são registrados ao concluir; sem deploy, merge ou Fase 11.
### Adendo de conferência final

A primeira execução completa do backend passou com 695/695 em 624.20s, zero skips. Após incluir cinco casos diretos obrigatórios, a repetição completa passou com 700/700 em 614.20s, zero skips. Casos novos: Admin em SupportSession READ_ONLY, FINANCIAL_FISCAL, Suporte usando contexto de Admin, nova AuthSession do mesmo Admin e segunda ação conhecida fora do grant. Cada caso chama preview/correção/reprocess, exige negação, Original/versão 1, nenhum run derivado e nenhuma auditoria de sucesso. A suíte adicional completa passou 12/12; revisão independente do adendo sem achados.

Capturas inspecionadas: [configuração normal clara](phase-10-visual/normal-empty-light.png), [escura](phase-10-visual/normal-empty-dark.png), [mobile](phase-10-visual/normal-empty-mobile.png), [review da concessão](phase-10-visual/maintenance-grant-review.png), [preview](phase-10-visual/correction-preview-light.png), [Antes/Depois na confirmação](phase-10-visual/correction-confirmation.png), [409 visível](phase-10-visual/correction-conflict.png), [confirmação de reprocess](phase-10-visual/reprocess-confirmation.png), [banner escuro](phase-10-visual/maintenance-dark.png), [mobile](phase-10-visual/maintenance-mobile.png), [foco mobile abaixo do banner](phase-10-visual/maintenance-mobile-focus.png), [encerramento mobile](phase-10-visual/maintenance-end-confirmation.png), [Suporte negado](phase-10-visual/support-controlled-denied.png).

Roteiro ajustado ao 404 neutro já existente para scope estrangeiro (aceita 403/404, sem relaxar autorização). A captura 409 foi posicionada no topo para expor mensagem e contexto. Sem alteração de produto nesses ajustes. Os E2E completos foram repetidos e passaram. Nenhum pageerror, recurso externo ou storage de negócio foi encontrado; tema em localStorage e somente ids opacos contextuais em sessionStorage.

Verificação física final separada: server_version 18.6, revisão 0009 consultada por owner; runtime não owner/não-superuser, CREATE em public negado, SELECT em alembic_version negado. ProcessingRun: SELECT/INSERT/UPDATE concedidos individualmente, DELETE/TRUNCATE negados. AuditEvent: UPDATE/DELETE/TRUNCATE negados. Nenhum grant foi ampliado para concluir a verificação. Diff staged detectou whitespace final no SQL da migração nova; removido, diff check e ciclo físico repetidos GREEN.

104 casos novos de backend e 32 de frontend nesta fase. Logs temporários citados pelos revisores foram removidos; resultados sanitizados, fontes dos testes, capturas e relatórios permanecem versionados.
