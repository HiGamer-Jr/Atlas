# Fase 11 — fechamento da fundação HiAtlas v1

HiAtlas Platform Foundation v1

STATUS: VALIDATED

Data da execução: 2026-10-05.
Branch: feat/hiatlas-platform-phase-11.
Base aprovada: 5beb8dd91abb5d8d82e3606918eb75dab933f833.
Worktree isolada: D:/Atlas/.worktrees/hiatlas-platform-phase-1; árvore limpa e base confirmadas antes das mudanças.
Commits de fechamento: registrados abaixo após a conclusão operacional.

## Resultado do quality gate

|Verificação efetivamente executada|Resultado|
|---|---|
|Backend completo, uv run --frozen pytest -q --tb=no|767 PASS, zero skips, 639,30s|
|Ruff app/tests/alembic e quatro scripts Python modificados|PASS|
|Frontend completo, npm test|282 PASS, 16 arquivos, zero skips, 64,02s|
|oxlint, npm run lint|PASS|
|TypeScript/Vite, npm run build|PASS, 75 módulos|
|git diff --check e git diff --cached --check|PASS após remoção de duas linhas vazias finais|
|PostgreSQL real descartável|18.6, owner/runtime/recovery separados|
|Migrações full-chain, incremental, downgrade/upgrade|PASS|
|Grants físicos, constraints e negações reais|PASS|
|Backup lógico e restore em banco novo|PASS|
|Break-glass, concorrência e rollback|33 testes focados PASS; incluídos nos 767|
|Browser real Admin/Support e manutenção controlada|8/8 rodadas PASS, 78 capturas|
|A/A2/B, concorrência, idempotência e regressão de segurança|PASS nas suites e E2E descritos abaixo|
|Build normal sob CSP e headers do HTML/assets|PASS, zero violações CSP/pageerrors|
|Revisões independentes backend/frontend|Concluídas; achados relevantes encerrados|

O único warning backend é a depreciação conhecida Starlette/TestClient/httpx. Não é skip ou falha funcional. Nenhum PASS representa verificação não executada.

## Escopo e implementação

Fechamento integrado das Fases 1–10, sem novo domínio operacional. Recuperação administrativa offline; configuração explícita de produção que falha fechada; liveness/readiness, headers e erro interno sanitizado; política pós-restore; runbook, sanity, demo readiness e documento de release.

Migration 0010_offline_admin_recovery é incremental após 0009. Não cria domínio de negócio nem tabela nova: instala/revoga privilégios mínimos da identidade externa de recuperação, inclusive ACLs por coluna. A aplicação normal continua sem handlers operacionais de manutenção. O código de browser/fixture permanece fora de backend/app e frontend/src.

## RED / correção / GREEN

- Produção inicialmente aceitava nove combinações inseguras. Exige agora origem/DB explícitos, chave outbox válida, delivery habilitado/desabilitado explícito e SMTP coerente; recusa debug/demo, HTTP, cookie inseguro, placeholders e DB de teste. Sender inválido e URL malformada também receberam regressões.
- Readiness inicialmente aceitava schema incompleto. A revisão reproduziu também tabelas presentes sem colunas: resposta200 em vez de503. Consulta de todas as colunas mapeadas com select(table).limit(0) confirmou os dois testes GREEN. Somente /health/live e /health/ready ignoram credenciais do browser; /api/health legado preserva a política restritiva.
- CLI de recuperação ausente produziu dois RED iniciais; validação tipada e a exceção estreita de perda de credencial receberam outros casos RED/GREEN. Resultado final focado:33 PASS em PostgreSQL. Não se inventou RED para regressões que já passavam.
- Primeira execução completa:751 PASS/16 FAIL. Quatorze testes HTTP esperavam propagação da exceção interna em vez da nova resposta500 sanitizada. O helper agora exige envelope genérico exato, UUID válido igual ao header, no-store e ausência de detalhes privados; todas as asserções de rollback foram preservadas. Worker/service direto continua esperando sua exceção. Sete módulos completos:198 PASS em211,38s; fixtures Unicode originais conferidas contra a base.
- A regressão de health legado foi corrigida restringindo o bypass aos dois probes novos. Segunda execução completa:766 PASS/1 FAIL. Alembic fileConfig desabilitava o logger no processo compartilhado de testes. Reprodução isolada confirmou RED; monkeypatch test-only restaura localmente logger.disabled e mantém todas as asserções. Mesma reprodução GREEN:1 PASS em0,24s. Não se alterou o logging de produção. Terceira execução completa:767 PASS.
- Runner E2E inicialmente aceitava a configuração do banco fonte descartável. RED puro retornou exit0, sem chamar clean. Guard dedicado antes de clean confirmou GREEN: fonte recusada exit1, E2E aceita exit0. Manifest deriva somente dados validados; as oito rodadas reais sempre usaram o banco/roles exclusivos corretos.
- Revisões identificaram lacunas no logging de query do servidor/proxy e headers do HTML estático. Runbook corrigido, sanity explícito e build validado no Chrome com CSP/headers reais; achados encerrados. A lacuna de equivalência de migrações foi encerrada com comparação física de catálogo/ACLs.
- pip-audit comprovou três advisories urllib3 2.7.0; alterado somente para2.8.0. npm audit completo comprovou advisories undici8.10.0/jsdom; alterado somente para8.10.2. Novas auditorias:zero vulnerabilidades conhecidas, 60 entradas Python e npm completo sem achados. Não houve atualização geral de dependências.

## PostgreSQL, schema e privilégios

Instância descartável em loopback, separada de qualquer ambiente real. Owner/runtime/recovery são distintos e não superuser; sem CREATEDB/CREATEROLE/BYPASSRLS. Runtime não é owner e não possui DDL/CREATE indevido. O E2E usa banco e roles diferentes da suíte pytest, evitando efeitos concorrentes sobre fixtures ou atributos dos logins.

Cadeia 0001–0009, incremental 0009–0010 e downgrade-base/upgrade-head executados. Snapshot fresh versus incremental comparou tabelas, colunas, tipos/defaults, constraints, índices e ACLs de tabela/coluna: equivalente. Downgrade/upgrade é ensaio técnico descartável, não promessa de rollback destrutivo seguro em produção.

Tentativas reais SQLSTATE42501 confirmaram runtime sem CREATE de schema/DB, sem SELECT de alembic_version e sem UPDATE/DELETE/TRUNCATE da auditoria; negócio sem DELETE. INSERT audit e privilégios técnicos estritamente necessários funcionaram. Recuperação não recebe criação de usuário, DELETE/TRUNCATE, ownership ou leitura de snapshots completos da auditoria.

## Backup e recuperação de dados

Dump custom restaurado em banco novo. Usuários, tenant, contrato, auditoria e OrganizationNode com id/code/version7, FKs e escopo preservados. Revisão Alembic e grants restaurados verificados.

A política offline database/post-restore-invalidate.sql invalidou sessões, contextos, SupportSessions, grants, preauth, tokens e outbox pendente; preservou negócio e auditoria histórica. Não reexecuta UNKNOWN ou ProcessingRun. Falha induzida na auditoria reverteu toda invalidação. Sessão antiga401; novo login200 e logout204.

Backup protegido fora do Git. Runbook documenta backup diário/pre-update como sugestão, retenção e RPO/RTO como decisão operacional, proteção do arquivo/chave correspondente e ensaio periódico de restore. Não foram definidos SLA, PITR ou failover.

## Recuperação administrativa break-glass

CLI offline, nenhuma rota HTTP, botão escondido ou senha padrão. Exige ambiente, identidade existente verificada, operador técnico, motivo, referência, evidência de incidente e confirmação. Senha somente em prompt protegido; política central e Argon2id. Runtime comum é recusado e a identidade de recuperação é isolada da API/worker.

Qualquer outro admin utilizável recusa o procedimento. O caso de única identidade com senha perdida exige atestado interativo protegido, canal normal indisponível conforme a configuração real SMTP e ausência de recuperação anterior para o mesmo alvo/incidente. O banco não comprova conhecimento/perda da senha: autoridade de infraestrutura autorizada e verificação externa são a fronteira de confiança explícita. A flag sozinha não autoriza; não existe fluxo de dupla aprovação inventado.

Auditoria tipada distingue operador técnico do usuário alvo. Recuperação não cria identidade ou papel novo, e revoga sessões/contextos/atendimentos/grants, tokens e outbox dependentes na mesma transação. Os testes cobrem necessidade/recusa, alvo inválido, runtime indevido, argv/log sem senha, replay, concorrência com um único sucesso, confirmação divergente e rollback de auditoria.

## Hardening e segurança integrada

Ambiente production é explícito. Configuração/startup recusam produção insegura, runtime owner/superuser e pré-condições de banco ausentes. Demo é desabilitado por padrão e o bundle normal não inclui entradas/handlers controlados. Origem HTTPS vem da configuração, não de Host enviado pelo cliente.

Cookies Secure/HttpOnly/SameSite/host-prefix, rotação, CSRF/Origin, limites persistentes, logout/reset/role changes, sessões/contextos/grants expirados, READ_ONLY e FINANCE/MAINTENANCE sem concessão foram reexercitados pela suíte completa e pelos E2E. Papéis internos não são TenantRole. A matriz A/A2/B cobre memberships, roles, organização, módulos, auditoria, atendimento, grants, manutenção e ProcessingRun.

Headers: no-referrer, nosniff, frame protection/CSP e HSTS somente para produção HTTPS explícita. Erros inesperados retornam mensagem neutra e request_id; log registra somente identificação segura, sem stack/body/URL secreta. Runbook exige access log ASGI desativado e logging de path sanitizado no proxy, excluindo query/cookies/Authorization.

Nenhum .env real, backup ou artefato privado foi encontrado entre os arquivos versionados; scan das alterações não encontrou material de chave privada. Isso não é alegação de scanner universal de segredos. Credenciais/certificado de teste permaneceram em TEMP protegido até o cleanup.

## Browser, inspeção e acessibilidade

[Relatório das oito rodadas](phase-11-browser-checks.md): Chrome real headless, FastAPI real, React/Vite real e bundle normal real, PostgreSQL descartável e FakeEmailTransport. Não houve e-mail real ou API mock.

Fases05–09 normal,10 normal,10 controlled e10 normal -Build passaram. Cobrem Admin/Support e login de membership convidado; recuperação/convites; gestão contextual; organização/módulos; READ_ONLY; concessões temporárias; registry normal vazio; correção controlada/Antes x Depois/auditoria;409 por segunda conexão; reprocessamento idempotente e A/A2/B. Reload, logout, abas independentes, negação manual, light/dark, desktop,390×844, teclado e foco foram exercitados.

Foram78 capturas novas em phase-11-visual; capturas aprovadas anteriores permaneceram intactas. Inspeção root incluiu READ_ONLY mobile, acesso financeiro light e preview controlado de correção. Banners/contexto/identidades ficaram legíveis, sem clipping nas amostras; indisponibilidade operacional aparece explicitamente. Build servido em HTTPS sob CSP real confirmou headers de HTML/assets, ausência de marker de fixture e zero violações CSP/pageerrors. Essa prova não representa deploy de produção.

## Revisões independentes

[Backend](phase-11-review-backend.md) e [frontend](phase-11-review-frontend.md) revisados separadamente da implementação. Todos os achados relevantes receberam reprodução ou evidência da lacuna, correção e confirmação GREEN/closure. Relatórios distinguem inspeção do reviewer de testes executados por root/implementadores. Nenhum achado relevante permanece aberto.

## Rastreabilidade da especificação

|Critérios da seção15|Provas|
|---|---|
|1–3 identidade, sessão/contexto, isolamento|identity/session/context suites; test_platform_acceptance; E2E05–10|
|4–5 limites Suporte e TenantRole|policy/roles/membership suites; E2E06/07/09/10|
|6–8 lifecycle, tokens, outbox/recuperação|membership_lifecycle/access_tokens/token/outbox suites; E2E05/06|
|9 READ_ONLY sem Financeiro|support sessions/gate suites; E2E08|
|10–11 manutenção/correção versionada e atômica|grants/correction_handlers suites; E2E09/10 controlado|
|12 último admin/reautenticação|operators/identity/grants/admin_recovery suites|
|13 auditoria física imutável|SQLSTATE42501 no PostgreSQL; audit/migration suites|
|14 reprocessamento idempotente|test_reprocessing; E2E10 controlado|
|15 contexto permanente/stale responses|Vitest; E2E06–09/reload/abas|
|16 projeções sanitizadas|audit/support/grants/reprocessing; produção/erro sanitizado|
|17 persistência após restart|test_platform_acceptance e suites anteriores sobre banco persistente|
|18 gates e migrations PostgreSQL|resultados completos deste relatório|
|19 WORKSITE distinto de PROJECT|organization suites; E2E07|
|20 nenhum editor genérico|OpenAPI/test_production_surface; reviews|
|21 evidências/review/gate antes de avançar|relatórios Fases1–11; encerramento para revisão|

## Operação, release e demo readiness

- [Runbook](../../../operations/hiatlas-platform-foundation.md): requisitos, configuração, owner/runtime/recovery, migração/bootstrap, HTTPS, backend/frontend, SMTP/outbox, saúde/logs, backup/restore, atualização/rollback, startup/shutdown e recuperação.
- [Sanity](../../../operations/hiatlas-post-deploy-sanity.md): procedimento não destrutivo após deploy futuramente autorizado.
- [Demo readiness](../../../operations/hiatlas-demo-readiness.md): banco/origem/segredos separados, dados sintéticos, SMTP controlado e aviso DEMONSTRAÇÃO; nenhum ambiente populado nesta fase.
- [Estado Foundation v1](../../../releases/hiatlas-platform-foundation-v1.md): funcionalidade real, inventário travado, ausência de domínios operacionais e próximos blocos sujeitos a autorização.

## Riscos e limitações

Registry normal vazio, zero handlers operacionais reais. PROCUREMENT/COMEX/INVENTORY/FINANCE/PROJECTS/DATAHUB no catálogo não significam domínios entregues. WORKSITE não é Project/Obra. Não há SQL/script executor, MFA, Administrador do Cliente, help desk ou dupla aprovação.

FakeEmailTransport não comprova SMTP real. Não houve deploy nem validação de infraestrutura de produção. Chrome headless não comprova multibrowser; acessibilidade básica não equivale a auditoria WCAG. Backup/restore lógico não comprova PITR/failover. Auditorias de dependências não provam ausência de vulnerabilidades desconhecidas. Break-glass depende da autoridade offline/verificação externa descrita, não de prova automática da perda da senha.

## Encerramento

Cleanup concluído e verificado: cluster/bancos/logins descartáveis, API/Vite, dumps, credenciais, chave outbox, certificado/TLS, logs privados e ferramentas TEMP removidos. Portas55491/8011/5181 e processos próprios ausentes. [Evidência de cleanup](phase-11-cleanup.md). A primeira espera limitada de shutdown preservou os arquivos; PostgreSQL terminou graciosamente, e só então a repetição validada removeu o diretório. Não houve force-kill arbitrário. Scratch local da execução removido após coleta das evidências. Commit local registrado no fechamento; worktree preservada para revisão. Sem deploy, push, merge, tag/release, ambiente Demo ou módulos operacionais. Parada obrigatória para revisão do usuário.
