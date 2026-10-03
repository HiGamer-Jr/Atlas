# Fase 9 — Concessões temporárias Financeiro/Fiscal e manutenção autorizada

## Proveniência e escopo

- Branch: `feat/hiatlas-platform-phase-9`.
- Base aprovada: `d360d30f51d76a5256a19095f0f00a401979b792` (Fase 8).
- Commit de implementação: 9750a0813fd8c281465b5dec9f162f40f7a73686.
- Commit complementar de evidências: este relatório, identificado no histórico por `docs: record phase 9 validation and cleanup`.
- Data da validação: 2026-10-03. Somente Fase 9; sem deploy, merge ou início da Fase 10.

## Implementação e schema

Migração incremental `0008_temporary_privileged_grants`, posterior a `0007_support_sessions`.
As tabelas `temporary_privileged_grants` e `maintenance_grant_scopes` persistem lifecycle, versão, operador real, sessão exata, tenant/contrato, contexto pai/derivado, motivo, referência e escopo tipado.

Tipos fechados: FINANCIAL_FISCAL e MAINTENANCE. Apenas PLATFORM_ADMIN; Support não solicita, usa ou encerra concessões. FKs compostas garantem operador/AuthSession e contextos do mesmo operador/sessão/tenant/contrato. Checks protegem papel, status, prazo, versão e transições terminais. O escopo inicial aceita somente organization_node, com FK composta para a entidade; uma action_code por concessão. Ampliações dependem de fase futura explícita.

GRANT_SECONDS inicia em 1800; REAUTHENTICATION_SECONDS existente inicia em 300. Validade é limitada pela sessão absoluta/idle e contexto pai. Não há sliding expiration, renovação por polling ou extensão por reload.

O Principal permanece o administrador real. O contexto privilegiado é opaco e utiliza X-HiAtlas-Context. Capabilities específicas grants.request/read/end e maintenance.authorize são reavaliadas pelo backend. Contextos administrativos comuns e abas independentes não herdam elevação.

FINANCIAL_FISCAL prepara apenas finance.read/fiscal.read, exigindo concessão vigente, contexto, módulo contratado/ativo/operacional, capability e entidade contextual. O gate central nega rotas não declaradas e revalida após locks/resolvers. Nenhuma API financeira operacional ou dado financeiro fictício foi criado. Todos os módulos operacionais continuam indisponíveis.

MAINTENANCE exige motivo, referência, ação registrada e escopo válido. O registry de produção está vazio; a UI informa ausência real de operações. Testes injetam ação/resolver controlados, sem rota de teste ou handler em produção. Nenhum write genérico, SQL, edição operacional, correção ou reprocessamento foi liberado. SupportSession READ_ONLY permanece separada e não pode ser elevada.

Criação e transições terminais compartilham transação com auditoria tipada. Eventos privileged_grant.started/ended/expired/revoked/denied identificam operador real e grant_type; manutenção é classificada no mesmo evento para evitar duplicação. Senhas, cookies, segredos e conteúdo financeiro não integram concessão/auditoria.

## RED → correção → GREEN

| Achado observado | RED | Correção / GREEN |
| --- | --- | --- |
| Contrato/API da concessão ausente | Dois testes comportamentais falharam | Settings e endpoints implementados; contrato atual com três testes passou |
| Capability específica ausente | history, registry e end retornavam 200 | Checks grants.read, maintenance.authorize e grants.end; negação confirmada |
| Concessão anterior expirada impedia nova solicitação | Parent retornava 409 | Terminalização auditada do anterior; nova concessão após reauth retorna 201 |
| Leitura declarada expirava durante resolver | GET retornava 200 após avanço controlado de 61s com TTL60 | Nova revalidação após resolver; 403 e auditoria terminal |
| Leitura declarada sem dependency Database | Contexto normal recebia 200 | Gate exige concessão/contexto também sem dependency e sem header/autenticação |
| Scopes duplicados por action_code | Cópia isolada do schema anterior aceitava duas entidades; DID NOT RAISE ValidationError | Schema atual rejeita, API422; antigo 500 potencial não foi executado |
| Projeção temporal terminal inconsistente | Mesmo instante com offsets diferentes quebrava idempotência | Normalização UTC; resposta terminal consistente |
| Reauth incorreta encerrava sessão HTTP | 401 AUTH_INVALID causava logout no ApiClient | Erro de credencial mantém operador/contexto; SESSION_INVALID continua invalidando |
| Criação ambígua permitia ferramentas normais | POST commit + erro/abort e descoberta indisponível voltavam ao portal | Estado unresolved bloqueia ferramentas até reconciliação autoritativa; regressões passaram |
| AbortController em StrictMode | E2E não emitia request de reauth; teste StrictMode falhou | Controller novo por montagem e sinal capturado por request; teste e E2E passaram |
| Sincronização de discovery no teste | Gate 249/250; foco disparado antes da instalação do efeito | Async act sem ampliar timeout; pai/header e ferramentas ocultas continuam exigidos; 250/250 |

As revisões independentes estão em [backend](phase-09-review-backend.md) e [frontend](phase-09-review-frontend.md). Revisores conferiram o código e correções; não reivindicam execução própria de testes. Execuções focadas dos implementadores: 70 casos integrados iniciais, dois adicionais de manutenção, três de contrato e 36 races/schema; frontend 34 focados. O gate integral do root abaixo é a evidência final.

## Quality gate executado pelo root

| Verificação | Resultado |
| --- | --- |
| Backend pytest completo | PASS — 596 testes, zero skips, 494.29s; um warning herdado |
| Backend Ruff app/tests/alembic | PASS |
| Ruff do fixture de browser | PASS |
| Frontend Vitest completo | PASS — 250 testes, 14 arquivos, zero skips, 13.84s |
| oxlint | PASS |
| TypeScript / Vite build | PASS — 68 módulos |
| Node syntax do E2E | PASS |
| git diff --check / staged diff | PASS — diff de trabalho e staged, incluindo arquivos novos |
| E2E Chrome real Admin / Support | PASS |

Primeira execução integral backend: 594 passaram e dois falharam porque o launcher temporário exportava DATABASE_URL/ENVIRONMENT/PUBLIC_ORIGIN e interferia nos testes de defaults/validação insegura. Essas três exportações genéricas foram removidas do launcher; os quatro testes focados passaram. Nenhuma regra de produto ou assertion foi relaxada. A suíte integral foi executada novamente com ambiente isolado, conforme resultado acima.

## PostgreSQL real, migrations, grants e concorrência

PostgreSQL descartável 18.6, somente loopback, banco atestado para testes. Owner e runtime distintos, ambos não-superusers; runtime não é owner e não possui bypass RLS, criação de banco/papel ou memberships privilegiados. Sem banco de produção.

Upgrade 0007→0008, downgrade 0008→0007 e upgrade novamente são executados pelos testes incrementais. Constraints físicas e metadata são comparadas. Runtime recebe SELECT/INSERT/UPDATE nas duas tabelas novas; DELETE/TRUNCATE são negados com SQLSTATE42501. Auditoria permanece imutável. A migração exige identidade owner.

109 casos novos: 70 de grants, três de contrato, 14 corridas e 22 de schema/grants. Corridas reais cobrem dois starts (201/409 e um efeito/audit), dois ends (idempotentes, um estado terminal/audit), expiry/logout/end concorrendo com leitura, revalidação após lock de sessão/contexto pai/tenant/contrato/papel, criação durante inativação de contrato/revogação do pai/remoção de papel/janela reauth vencendo. Nenhuma ressurreição de concessão.

Fixtures Tenant A / Contract A, Tenant A / Contract A2 e Tenant B / Contract B comprovam isolamento de concessão, contexto, histórico e scope. Nova AuthSession do mesmo operador não herda concessão; contexto normal continua sem capacidade financeira. Auditoria rollback, ator real e mutações POST/PATCH/PUT/DELETE são testados no backend real.

## E2E e inspeção visual

Harness versionado: frontend/e2e/phase09.mjs e scripts/phase09_browser_fixture.py. PostgreSQL, FastAPI, React/Vite HTTPS e Chrome headless reais, sem mocks HTTP ou demo autenticado. Transporte FakeEmailTransport controlado; nenhum SMTP real/destinatário real. Identidades e justificativas sintéticas.

Admin: login → Contract A → Acessos Temporários → reauth antiga negada → senha incorreta tratada sem logout → reauth correta → revisão contextual → grant → banner → módulo operacional indisponível → reload sem extensão → encerramento e contexto normal restaurado. Também expiry, parent revogado e nova sessão HTTP negada.

Support: menu ausente; endpoints de solicitação, histórico, leitura/encerramento de grant e tentativa de elevação de READ_ONLY negados. A/A2/B e aba/contexto normal comprovados com chamadas manuais ao servidor; writes POST/PATCH/PUT/DELETE em contexto privilegiado retornam 403.

Manutenção: catálogo real vazio e mensagem de indisponibilidade; nenhum handler fake de produção. Política positiva de ação injetada é comprovada nos testes backend.

Inspeção: desktop claro/escuro, mobile 390×844, sem overflow externo, banner sticky com empresa/contrato/ambiente/operador, foco visível, Enter/Escape, reauth, confirmação e encerramento. O harness verifica storage (somente ids opacos em sessionStorage e tema em localStorage), ausência de recursos externos e pageerrors. Histórico/auditoria real consultados após aguardar confirmação do novo contexto; uma corrida inicial de leitura do id antes da seleção foi corrigida no harness.

Capturas inspecionadas: [claro](phase-09-visual/financial-light.png), [escuro](phase-09-visual/financial-dark.png), [mobile](phase-09-visual/financial-mobile.png), [reauth](phase-09-visual/financial-reauth.png), [revisão](phase-09-visual/financial-confirmation.png), [encerramento](phase-09-visual/financial-end-confirmation.png), [expiração](phase-09-visual/financial-expired.png), [revogação](phase-09-visual/financial-revoked.png), [manutenção indisponível](phase-09-visual/maintenance-unavailable.png).

## Riscos e limites

- Não existem módulos Financeiro/Fiscal operacionais ou handlers de manutenção nesta entrega. Concessão não altera operational_available.
- Estado terminal e auditoria de expiração/revogação por dependência são persistidos na observação segura/controle; não há worker de expiração. Autorização consulta estado vigente e nega imediatamente, mesmo que histórico ainda mostre ACTIVE antes da observação.
- Escopo inicial de manutenção: organization_node, uma action_code por grant; futuros tipos/handlers exigem revisão própria.
- Um warning herdado Starlette/httpx no pytest; não representa skip ou falha.
- Não há MFA, dupla aprovação, impersonação, dados operacionais ou avanço da Fase 10.

## Encerramento

API e Vite temporários encerrados; portas próprias verificadas sem listeners. PostgreSQL descartável parado e cluster removido. Credenciais temporárias, chave de outbox, certificado/chave TLS, logs de execução e scratch removidos após validação dos caminhos e ausência de reparse points. Worktree preservada para revisão. Implementação registrada no commit indicado acima; evidências encerradas em commit complementar. Estado Git final deve permanecer limpo. Sem deploy, merge ou Fase 10.
