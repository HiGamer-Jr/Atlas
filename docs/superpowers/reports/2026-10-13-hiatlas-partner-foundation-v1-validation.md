# HiAtlas Partner Portal — entrega A validada

Fechamento: 2026-10-13. Branch local: feat/hiatlas-partner-portal-v1. Worktree exclusiva: D:/Atlas/.worktrees/hiatlas-partner-portal-v1.

Base exclusiva de produto: c50353aadba2e1ef6bb0b917b3e63736fa5f1f90, feat/hiatlas-purchase-request-v1; ancestry preservada sobre Customer Scope fa354b73cdb43d600949e54b81595f416ef5cd65. Código validado no commit 7a36821aeb33effc7b60dfd59bd9f825943e4c64. O commit de fechamento adiciona somente documentação; não altera código validado.

## Entrega e fronteiras

Seis tarefas executadas pelo método Subagent-driven, com implementadores dedicados, revisão independente de spec/qualidade por tarefa e revisão integral da branch. Findings importantes de ordem de locks, ownership de logout e downgrade destrutivo foram corrigidos e re-reviewados. Nenhum finding Critical/Important ficou aberto.

Entrega A: PartnerOrganization/PartnerMembership e catálogo PARTNER exclusivos; User/AuthSession reutilizados, sem TenantRole artificial; lifecycle curado por ADMIN atual, convites tipados, proteção de credenciais existentes, criação atômica de destinatário real, auditoria tipada, versões e receipts imutáveis; contratos frontend fechados, cancelamento e limpeza de credenciais. Migrations 0016–0018 preservam evidência e recusam downgrade preenchido, com locks antes de checks/DDL.

O portal operacional completo não foi habilitado. A COMEX Process Foundation é dependência da entrega B (processos, grants, contextos PARTNER, logística/timeline). Scanner/documentos privados/payment intake são entrega C. Não há processo, unidade, empresa ou indicador demonstrativo inserido no produto. Purchase Request permanece separado de Payment Request. PARTNER nunca aprova/executa pagamento.

## Contratos de API entregues

- GET /api/partner/availability: schema_version=1, status=DOMAIN_UNAVAILABLE, code=PARTNER_DOMAIN_UNAVAILABLE.
- GET /api/partner/access-options: [] autenticado, sem diretório de organizações/contratos.
- POST /api/partner/contexts: membership_id/client_link_id candidatos; domínio indisponível 503, INTERNAL negado; nenhum contexto operacional persistido.
- POST /api/platform/partners/organizations; POST /api/platform/partners/organizations/{id}/memberships; PATCH /api/platform/partners/memberships/{id}; POST /api/platform/partners/memberships/{id}/invite: origem/CSRF/reautenticação/ADMIN atual, capability dedicada, Idempotency-Key, versões e atomicidade.
- Membership: XOR entre user_id e recipient{email,display_name}; nova identidade passwordless real sem role tenant/plataforma; existente preservada, inativa/bloqueada rejeitada.
- /api/auth/token/validate distingue INTERNAL/TENANT/PARTNER/USER; /api/auth/invite/accept e alias anterior preservam compatibilidade. Aceite PARTNER exige discriminador confirmado pelo servidor e destinatário autenticado quando a conta já possui credencial.

IDs do navegador não são autoridade. Nenhuma autorização é armazenada em localStorage. Permissões administrativas não foram atribuídas a parceiros, compradores ou solicitantes.

## Quality gate oficial completo

Comando executado em 2026-10-12, diretamente da worktree:

    .\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'

Uma execução canônica completa após revisão/fixes; exit 0. Nenhum código mudou depois dessa execução.

| Etapa | Resultado |
|---|---|
| Backend completo | PASS — 1.323 testes, zero skips, 1 warning herdado |
| Backend lint | PASS |
| Scripts / segurança PostgreSQL Windows | PASS — 37 testes, zero skips |
| Scripts lint | PASS |
| Frontend completo | PASS — 441 testes / 32 arquivos, zero skips |
| Frontend lint | PASS |
| TypeScript/Vite build | PASS — 100 módulos, build concluído |
| git diff --check, working/staged | PASS |
| PostgreSQL cleanup | PASS — cluster próprio parado e removido normalmente |

PostgreSQL 18.6 descartável, owner/runtime/recovery verificados; database_harness intacto, sem SQLite ou bypasses. Log integral local preservado: [quality gate](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/logs/hiatlas-partner-foundation-gate-2026-10-12.log).

As contagens históricas por tarefa não foram somadas como total da branch. RED/GREEN incluiu faltas de persistência/lifecycle/convites/API/frontend, concorrência real, SQL NULL, ordem de locks, stale logout e downgrade. Testes de concorrência já corretos foram registrados como regressão GREEN, sem fabricar RED.

## Riscos conhecidos e preservação

Warning Starlette/httpx preexistente permanece. npm audit em leitura identificou advisory alto herdado de source-map-js, GHSA-68fv-2mgg-jv7q; lockfiles ficaram congelados. Não se declara audit limpo: remediação de dependência é trabalho separado. Alguns testes frontend compactos têm melhoria de legibilidade adiada, sem finding funcional aberto.

Downgrade com evidência persistida agora falha deliberadamente; reversão de dados exigiria desenho/ação explícita, não descarte silencioso. SMTP real, scanner, Finance, rollout/deploy e integrações externas não foram executados. Testes locais exercitaram outbox e worker, sem envio externo.

Main local/remoto, Demo, release, integration, Customer Scope e Purchase Request permaneceram nos SHAs registrados. Scripts, database_harness, catálogos de módulos operacionais, tipos Customer Scope, Demo/catalog e manifests/lockfiles não mudaram. Nenhum push, merge, rebase, tag, deploy ou force push; nenhuma branch foi apagada.

## Arquivos alterados desde a base
- [backend/alembic/versions/0016_partner_identity.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/alembic/versions/0016_partner_identity.py)
- [backend/alembic/versions/0017_partner_invitation_target.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/alembic/versions/0017_partner_invitation_target.py)
- [backend/alembic/versions/0018_partner_lifecycle_receipts.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/alembic/versions/0018_partner_lifecycle_receipts.py)
- [backend/app/api/router.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/api/router.py)
- [backend/app/audit/schemas.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/audit/schemas.py)
- [backend/app/db/models.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/db/models.py)
- [backend/app/identity/access_routes.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/identity/access_routes.py)
- [backend/app/identity/delivery.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/identity/delivery.py)
- [backend/app/identity/email_schemas.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/identity/email_schemas.py)
- [backend/app/identity/models.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/identity/models.py)
- [backend/app/identity/recover_admin.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/identity/recover_admin.py)
- [backend/app/identity/tokens.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/identity/tokens.py)
- [backend/app/partners/__init__.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/__init__.py)
- [backend/app/partners/audit.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/audit.py)
- [backend/app/partners/availability.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/availability.py)
- [backend/app/partners/capabilities.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/capabilities.py)
- [backend/app/partners/invitations.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/invitations.py)
- [backend/app/partners/lifecycle.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/lifecycle.py)
- [backend/app/partners/models.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/models.py)
- [backend/app/partners/receipts.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/receipts.py)
- [backend/app/partners/routes.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/routes.py)
- [backend/app/partners/schemas.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/partners/schemas.py)
- [backend/app/platform/capabilities.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/app/platform/capabilities.py)
- [backend/tests/conftest.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/conftest.py)
- [backend/tests/fixtures/partners.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/fixtures/partners.py)
- [backend/tests/test_admin_recovery.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/test_admin_recovery.py)
- [backend/tests/test_membership_invitations.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/test_membership_invitations.py)
- [backend/tests/test_migration_lifecycle.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/test_migration_lifecycle.py)
- [backend/tests/test_partner_availability.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/test_partner_availability.py)
- [backend/tests/test_partner_concurrency.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/test_partner_concurrency.py)
- [backend/tests/test_partner_invitations.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/test_partner_invitations.py)
- [backend/tests/test_partner_lifecycle.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/test_partner_lifecycle.py)
- [backend/tests/test_partner_models.py](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/backend/tests/test_partner_models.py)
- [docs/superpowers/plans/2026-10-11-hiatlas-partner-portal-v1.md](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/docs/superpowers/plans/2026-10-11-hiatlas-partner-portal-v1.md)
- [docs/superpowers/reports/2026-10-13-hiatlas-partner-foundation-v1-validation.md](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/docs/superpowers/reports/2026-10-13-hiatlas-partner-foundation-v1-validation.md)
- [docs/superpowers/specs/2026-10-11-hiatlas-partner-portal-v1-design.md](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/docs/superpowers/specs/2026-10-11-hiatlas-partner-portal-v1-design.md)
- [frontend/src/auth/AccessLifecycle.test.tsx](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/auth/AccessLifecycle.test.tsx)
- [frontend/src/auth/AccessLifecycle.tsx](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/auth/AccessLifecycle.tsx)
- [frontend/src/partners/api.test.ts](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/partners/api.test.ts)
- [frontend/src/partners/api.ts](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/partners/api.ts)
- [frontend/src/partners/PartnerAvailability.test.tsx](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/partners/PartnerAvailability.test.tsx)
- [frontend/src/partners/PartnerAvailability.tsx](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/partners/PartnerAvailability.tsx)
- [frontend/src/partners/types.ts](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/partners/types.ts)
- [frontend/src/partners/validate.test.ts](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/partners/validate.test.ts)
- [frontend/src/partners/validate.ts](D:/Atlas/.worktrees/hiatlas-partner-portal-v1/frontend/src/partners/validate.ts)

## Registro das decisões de execução

- Ruling: headings normalized to Task N for skill extraction — no requirement change — cost if wrong is documentation naming only.
- Ruling: add GET /api/partner/availability for the approved availability DTO; apply same session/class gates and no-store — DTO otherwise has no transport — cost if wrong is removable route.
- Ruling: lifecycle PATCH uses Idempotency-Key as well as POST — all mutations require replay safety — cost if wrong is stricter client contract, not authorization weakening.
- Ruling: use exact real migration revisions 0016→0017→0018 — verified existing revision 0015 — cost if wrong is migration rollback/rework.
- Ruling: Task-scoped model/migration tests and covering lint per task; full canonical gate at Task6/final — developer limits redundant broadened testing — cost if wrong is late regression detection, mitigated by independent review and final gate.
- Task 2: RED eight expected missing lifecycle/capability failures, zero skips/errors, CLEAN. Corrected nonexistent role regression path before actual GREEN. Ruling: delivery A audit provenance in typed versioned snapshots, actor_role unchanged — only INTERNAL lifecycle actors exist now — cost if wrong is subsequent schema extension when actual PARTNER operations arrive, no artificial role.
- Ruling: invitation issue/accept integrations acquire LIFECYCLE_LOCK then OPERATOR_LOCK before sorted users/session — prevents order inversion between identity token lifecycle and partner lifecycle — cost if wrong is serialization overhead, not auth bypass.
- Ruling: preserve existing INTERNAL operator invitation target in addition to TENANT/PARTNER XOR; token inspection discriminates INTERNAL/TENANT/PARTNER and reset USER — repository has valid operator invites with null membership fields, so unconditional scoped XOR would break existing identity — cost if wrong is malformed null-target acceptance; mitigate actual current platform assignment/issuer binding and negative ordinary-user tests, no inference from null alone.
- Task 3: final GREEN123 PASS zero skips, CLEAN; commit8b4a9f7 under independent security review. Ruling: report reference to Task4 adding PartnerAccessContext is mistaken; approved delivery A explicitly has no operational context table. Global PARTNER context revocation stays gateB and AuthSession reset revocation is tested now — avoids inventing table absent Process — cost if wrong is future integration work already gated.
- Task 3: review Important lock-order conflict: new access_routes/delivery LIFECYCLE→OPERATOR vs recover_admin OPERATOR→LIFECYCLE. Fix round1/5 required. Ruling: align existing recovery to LIFECYCLE→OPERATOR and add realPG concurrency regression — approved new lock contract needs shared call-site consistency — cost if wrong is admin recovery serialization regression; cover actual recovery tests. No new PartnerAccessContext in A.
- Ruling: Task4 membership POST accepts closed XOR existing user_id vs recipient{email,display_name}, permissions and expected_version0. Add create_partner_recipient_membership savepoint for new passwordless realUser plusmembership — approvedspec newrecipient firstcredential had no suitable identityprovisioning path; current operator creation would fabricate role — cost if wrong is unintended identitycreation. Mitigate ADMIN+dedicatedcap, normalizeduniqueemail under lifecycle/operatorlocks, preserve existingcredentials/status, no directoryendpoint, typed audit/receiptatomic, new/existing/malformed/replay/rollback tests. Inactiveblockedexisting identities failclosed, neverreactivated.
- Ruling: final canonical gate run by controller after Task6 scoped tests/review and whole-branch review — prevents redundant fullgate before final fixes and follows developer testscope guidance — cost if wrong is delayed integration result; no completion claim before completecanonicalPASScleanup. Task6 may commit its reviewed concurrency tests and docs, controller commits final evidence aftergate.
- Task 5: review Important stale logout retry ownership: replacement doesnotclearlogoutPending; endSession retry withoutsignal catchescancel andsetsoldstateonnewinvite. Fix round1/5 required. Minor deferred compressedtest/codeformat; finalreviewtriage. npm audit readonly confirms inherited source-map-js 1.0.0–1.2.1 advisoryGHSA-68fv-2mgg-jv7q high, fixed>=1.2.2; frozenlockunchanged. Ruling: track dependency remediation separate from this productfoundation; no lockfile updates — explicit dependencyfreeze and no deployment — cost if wrong is inheritedtoolingDoS risk, disclose final and do notclaim auditzero.
- Finalreview Important: migration0018 drops populated receipts and permits duplicateeffects after downgrade/upgrade. ONE finalfixwave required. Ruling: refuse destructive populated-evidence downgrades0018 (receipts),0017 (partner tokenbindings),0016 (partner identity/permissions), preservingempty schema roundtrip — append-onlyhistory/idempotency durability are specbinding — cost if wrong is stricterdowngrade requiring explicit separatelyapproved migration, preferable to silentdata loss.
- Finalreview declined-to-judge adjudication: positiveCOMEX/sharing/grants/timeline and partnercontext/provider/two-taboperations remain approvedgateB; scanner/docs/paymentintake/Finance remaingateC; selfserviceorgediting/directory/federation/MFA/notificationsdashboards outofA. SMTP/deployedcompatibility untested because no deploy/externalmail authorized; localoutbox tested. Dependencywarnings/advisory separatelydisclosed. Canonicalgatepending untilactualcontrollerPASS. Ruling: all are explicitdelivery boundaries, not silently droppedrequirements — approvedplanseparatesA/B/C — costifwrong usercouldmistakeAforfullPortal; finalreportmuststatefoundationonly.
- Finalfix samewave extends preDDL check atomicity: AccessExclusive locks before evidence SELECT, plus established LIFECYCLE→OPERATOR advisory ordering before tablelocks to prevent FKDDL/member-token inversion with application writers. Ruling: maintenance shares application lifecycle serialization, not emptycheck/DROP race — costifwrong strictermigrationblocking/throughput; realPGlocking regressions and scoped rereview required. InitialguardGREEN100PASS, supplemental lockingRED3 missingAEX assertions confirmed; finalamend pending.
