# HiAtlas Partner Portal V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar primeiro a fundação testável de identidade PARTNER, preservando os gates que impedem habilitar um portal sem COMEX operacional, scanner e payment intake reais.

**Architecture:** User/AuthSession são reutilizados; PartnerOrganization e PartnerMembership são separados de TenantRole. A primeira entrega contém lifecycle curado, convites tipados, contratos fechados e indisponibilidade explícita. Compartilhamento/logística e documentos/payment intake têm planos separados após as dependências arquiteturais aprovadas, sem processo fake ou autorização por unidade para parceiro.

**Tech Stack:** Python/FastAPI/Pydantic/SQLAlchemy/Alembic/PostgreSQL, uv/pytest/ruff; React/TypeScript/Vite/Vitest/oxlint; PowerShell e database_harness oficiais.

**Spec:** ../specs/2026-10-11-hiatlas-partner-portal-v1-design.md — aprovado pelo usuário em 2026-10-11; commit documental de referência 3f703ae0ed23943b72b2c38fb65b33d654cff7df.

## Global Constraints

- Base exclusiva de produto: feat/hiatlas-purchase-request-v1 em c50353aadba2e1ef6bb0b917b3e63736fa5f1f90; executar somente na worktree D:/Atlas/.worktrees/hiatlas-partner-portal-v1 e branch feat/hiatlas-partner-portal-v1.
- Classes INTERNAL, TENANT e PARTNER separadas; PARTNER não é TenantRole; plataforma ativa impede operar como PARTNER na V1.
- Partner access é resource-based, nunca unit-based. IDs do browser são candidatos. Capabilities de UX não são prova de autorização.
- Sem código nesta etapa de planejamento; execução exige revisão deste plano. Sem push, merge, deploy ou alteração em main/Demo/release/integration/Customer Scope/Purchase Request.
- Sem SQLite, skips, relaxamento de database_harness, bypasses ou seeds demonstrativos.
- Nenhum COMEX Process existe nesta base: não habilitar COMEX em OPERATIONAL_MODULES, não substituir por DataHubComexReference, não criar FK para tabela inexistente.
- Documento externo sem scanner fica QUARANTINED, sem download/evidência/submissão. Limites posteriores: 5 MiB por arquivo, 64 KiB de envelope, dez documentos por comando, 100 MiB por processo/organização incluindo versões.
- PARTNER solicita pagamento; nunca aprova/executa. Leitura própria é da organização com partner.payment_requests.read_org individual e grant atual.
- grant_epoch terminal e access_epoch do vínculo invalidam contextos antigos; mudança/revogação de grants é atômica com expected_version/audit.
- Lista autorizada: default 50, máximo 100; cursor máximo 2048 caracteres. Snapshot obrigatório excedido falha fechado, sem truncamento silencioso.
- Toda futura operação recalcula autorização atual, inclusive replay e dependências do snapshot original. Eventos/audit/receipt/version no mesmo commit.

## Review Focus

1. Mesmo e-mail já possui User TENANT: convite PARTNER preserva senha/status/roles/vínculos; testes T3.
2. PlatformRoleAssignment muda durante espera: servidor verifica classe depois dos locks, sem usar claim/frontend antigo; testes T4/T6.
3. Corpo, schema ou estado desconhecido: DTO/backend/frontend rejeitam, sem fallback para catálogo Demo; testes T4/T5.
4. Reissue e reset concorrem com aceite: somente alvo/token atual pode ser consumido e não há contexto residual; testes T3/T6.
5. Catálogo COMEX comercial ativo sem domínio real: discovery não expõe contrato/processo e comandos não viram disponíveis; testes T4/T5.

## Decomposição e sequência de entrega

| Entrega | Plano / condição | Resultado independente |
|---|---|---|
| A — identidade e fronteira indisponível | T1–T6 detalhadas neste documento | Lifecycle PARTNER real e testado; operação COMEX indisponível com mensagem clara |
| B — recursos, logística e timeline | Elaborar plano B somente após spec e implementação validados da COMEX Process Foundation | Sharing real, contexto PARTNER, logística/timeline isolados |
| C — documentos e payment intake | Elaborar plano C após B, scanner definido e contrato de intake Finance aprovado | Documentos privados e solicitação financeira, sem executor financeiro completo |

Não declarar entrega A como Portal V1 operacional completo. Não gerar agora tarefas executáveis de B/C contra entidades ou adapters inexistentes: isso exigiria tomar decisões de domínio fora do spec aprovado. Os gates abaixo cobrem todos os requisitos restantes e determinam os insumos exatos dos planos posteriores.

## Mapa de arquivos da entrega A

Novos backend: app/partners/{models,schemas,capabilities,audit,lifecycle,invitations,availability,routes}.py e __init__.py. models contém somente PartnerOrganization/PartnerMembership/PartnerMembershipPermission; sem ProcessGrant, contexto operacional ou PaymentRequest prematuros. Novos testes: tests/fixtures/partners.py; tests/test_partner_{models,lifecycle,invitations,availability,concurrency}.py. Migration: alembic/versions/0016_partner_identity.py, revision="0016", down_revision="0015"; a revisão real atual é 0015, não o nome do arquivo. Convites usam revisão 0017 (down_revision 0016); receipt lifecycle usa 0018 (down_revision 0017), sem reescrever migration já commitada.

Modificar backend: app/db/models.py, app/audit/schemas.py, app/identity/{models,tokens,sessions}.py, app/platform/capabilities.py, app/api/router.py, tests/conftest.py, tests/test_migration_lifecycle.py. Manter alterações pequenas e responsabilidades nos arquivos partners. Se logout/reset já invalidam sessões suficientes, não alterar sessions.py sem teste que demonstre necessidade.

Novos frontend: src/partners/{types,validate,api,PartnerAvailability}.ts/tsx e respectivos testes. Modificar src/auth/AccessLifecycle.tsx e seus testes somente para consumir alvo de convite discriminado; não redirecionar App/AuthenticatedApp para portal operacional inexistente. Nenhuma alteração de DemoApp/workspace/catalog.

## Rotina RED/GREEN comum

Em cada tarefa: escrever teste com assertions abaixo; rodar e observar falha de comportamento/import esperado, não falha de harness; implementar o mínimo; repetir até PASS; revisar diff; commit local somente dos arquivos da tarefa. Revisor verifica spec e segurança antes da tarefa seguinte quando execução subagent-driven for escolhida. A escolha de método desta nova fase ainda precisa ser confirmada; método da fase Purchase Request não é autorização automática para implementar esta fase.

Backend: iniciar PostgreSQL descartável pelo módulo oficial, na raiz: Import-Module .\scripts\testdb.psm1; Start-HiAtlasTestDb -PostgresRoot 'D:\Atlas\.tools\pgsql18'; Assert-HiAtlasTestDb. Executar uv run --frozen pytest <arquivos> -q a partir de backend no mesmo ambiente atestado; finalizar Stop-HiAtlasTestDb em finally. Não usar banco de desenvolvimento, DATABASE_URL improvisada ou fixture que ignora harness. Provisionar dependências congeladas conforme lockfiles se worktree nova não as possuir.

Frontend: a partir de frontend, npm.cmd test -- <arquivo>; npm.cmd run lint; npm.cmd run build. Não rodar teste vermelho que dependa de arquivos ocultos de outra worktree.

### T1 — Persistência PARTNER com integridade e migração

**Files:** criar backend/app/partners/models.py, __init__.py, backend/alembic/versions/0016_partner_identity.py, backend/tests/fixtures/partners.py, backend/tests/test_partner_models.py; modificar backend/app/db/models.py, backend/tests/conftest.py e test_migration_lifecycle.py.

**Interfaces:** produzir PartnerOrganization(id: UUID, name: str, category: Literal[TRADE,CUSTOMS_BROKER,LOGISTICS_OPERATOR,FREIGHT_FORWARDER,OTHER], active: bool, version: int); PartnerMembership(id: UUID, organization_id: UUID, user_id: UUID, active: bool, blocked: bool, invitation_pending: bool, version: int); PartnerMembershipPermission(organization_id: UUID, membership_id: UUID, code: str). version começa em 1; criação recebe expected_version=0. Permission pertence ao catálogo PARTNER, não TenantRolePermission.

- [ ] RED: test_partner_member_is_not_tenant_membership afirma nenhuma Membership/TenantRole criada; test_partner_permission_cross_org_fk_rejected afirma FK composta nega membership de outra organização; test_partner_user_org_unique afirma duplicata é rejeitada; test_partner_identity_migration_runtime_permissions verifica runtime não pode DDL, upgrade/downgrade e limpeza em ordem.
- [ ] Rodar uv run --frozen pytest tests/test_partner_models.py tests/test_migration_lifecycle.py -q; registrar FAIL por recurso ausente.
- [ ] GREEN: criar constraints/FKs/unique e registrar modelos. Integrar tabelas ao cleanup do fixture antes de users; sem grants/processos/contexto fake.
- [ ] Rodar comando anterior; exigir PASS sem skips e nenhuma regressão de migration lifecycle.
- [ ] Revisar e commit local: feat: add separate partner identity persistence.

### T2 — Lifecycle curado, catálogo exclusivo e auditoria atômica

**Files:** criar backend/app/partners/{capabilities,schemas,audit,lifecycle}.py e tests/test_partner_lifecycle.py; modificar app/audit/schemas.py e app/platform/capabilities.py somente para operações internas dedicadas.

**Interfaces:** PartnerOrganizationCreate(name,category,expected_version=0); PartnerMembershipCreate(organization_id,user_id,permissions,expected_version=0); PartnerMembershipReplace(active,blocked,permissions,expected_version,reason). Produzir create_partner_organization(db: Session, principal: Principal, command: PartnerOrganizationCreate) -> PartnerOrganization; create_partner_membership(db,principal,command: PartnerMembershipCreate) -> PartnerMembership; replace_partner_membership(db,principal,membership_id: UUID,command: PartnerMembershipReplace) -> PartnerMembership. Services exigem PLATFORM_ADMIN atual e capability interna partners.organizations.manage ou partners.memberships.manage; dependências de autenticação permanecem necessárias, não confiar no Principal sem revalidar role em lock.

- [ ] RED: test_support_and_tenant_cannot_provision afirma 403, sem linha/audit residual; test_partner_capabilities_never_enter_tenant_role_catalog afirma ausência na lista atribuível TENANT; test_membership_replace_version_and_audit_atomic afirma uma versão/audit, segundo expected_version antigo dá 409 e auditoria falha provoca rollback; test_reactivate_does_not_restore_removed_permissions afirma conjunto explicitamente substituído.
- [ ] Rodar uv run --frozen pytest tests/test_partner_lifecycle.py -q; confirmar FAIL comportamental.
- [ ] GREEN: usar catálogo fechado da seção 8 do spec, substituição atômica e snapshots audit tipados; actor_role permanece plataforma/NULL, actor_kind separado/versionado. Nenhum auto-seed de membro/capability ou permissão administrativa PARTNER.
- [ ] Rodar testes T1/T2 e regressões de roles/audit existentes identificadas por rg; PASS e diff check.
- [ ] Commit: feat: add curated partner lifecycle and audit.

### T3 — Convites discriminados e preservação da identidade existente

**Files:** criar app/partners/invitations.py e tests/test_partner_invitations.py; modificar app/identity/models.py,tokens.py, alembic/versions/0017_partner_invitation_target.py (revision 0017, down_revision 0016), schemas/rotas identity apenas nos pontos de invite realmente existentes.

**Interfaces:** produzir issue_partner_invitation(db: Session,principal: Principal,membership_id: UUID) -> None e accept_partner_invitation(db: Session,raw_token: str,authenticated_user_id: UUID | None,new_password: str | None) -> PartnerMembership. SecurityToken recebe partner_membership_id FK e constraint de alvo exclusivo tenant OU partner para INVITE; PASSWORD_RESET preserva alvo User e não ganha membership arbitrária. DTO de inspect/accept inclui target_kind TENANT/PARTNER, nunca inferido por null sem discriminação.

- [ ] RED: test_partner_invite_existing_user_preserves_identity afirma password_hash/status/roles/TENANT memberships idênticos; destinatário diferente é negado; test_invite_target_exclusive_and_single_use afirma XOR alvo e segundo aceite negado; test_reissue_invalidates_old_partner_invite afirma somente novo token/outbox válido; test_reset_revokes_partner_user_sessions afirma sessão antiga rejeitada em todas as classes.
- [ ] Rodar uv run --frozen pytest tests/test_partner_invitations.py tests/test_access_tokens.py -q; confirmar RED sem bypass de envio/credenciais.
- [ ] GREEN: lifecycle_lock antes de usuários/sessões/memberships; hashes, expiração e outbox existente; conta existente precisa autenticar destinatário, sem troca de senha via convite. Criar credencial de novo User somente pelo fluxo inicial existente. Não alterar comportamento de convites TENANT.
- [ ] Rodar testes anteriores + tokens/outbox atuais; PASS zero skips.
- [ ] Commit: feat: support typed partner invitations safely.

### T4 — API mínima, disponibilidade fechada e isolamento de classe

**Files:** criar app/partners/availability.py,routes.py,receipts.py, alembic/versions/0018_partner_lifecycle_receipts.py e tests/test_partner_availability.py; modificar app/api/router.py, partners/models.py, db/models.py e tests/conftest.py. Contratos Pydantic em partners/schemas.py.

**Interfaces:** PartnerAvailability(schema_version: Literal[1], status: Literal[DOMAIN_UNAVAILABLE], code: Literal[PARTNER_DOMAIN_UNAVAILABLE]); get_partner_availability(db: Session,principal: Principal) -> PartnerAvailability. Catálogo operacional real não existe: adapter indisponível é o único estado de produção desta entrega. GET /api/partner/access-options retorna lista vazia autenticada, sem contratos/orgs que não possuem grants reais. POST /api/partner/contexts autentica/valida entrada fechada e retorna 503, sem criar AccessContext ou PartnerAccessContext.

Lifecycle interno expõe POST /api/platform/partners/organizations, POST /api/platform/partners/organizations/{id}/memberships, PATCH /api/platform/partners/memberships/{id}, POST /api/platform/partners/memberships/{id}/invite. Usar autenticação/reautenticação/CSRF e políticas internas atuais; sem busca/listagem global TENANT. Para POSTs internos, criar receipt idempotente namespace user/session/route/target/key com digest e resultado, autorização atual antes de replay, mesma transação; adicionar PartnerLifecycleReceipt(id,user_id,session_id,route,target_id nullable,key,digest,response_json,status_code,created_at), unique user/session/route/target/key com NULLS NOT DISTINCT e proteções append-only; namespace não inclui tenant/contract pois lifecycle global não opera processo. Produzir run_lifecycle_command(db: Session, principal: Principal, route: str, target_id: UUID | None, key: UUID, payload: BaseModel, execute: Callable[[], BaseModel]) -> LifecycleCommandResult(status_code: int, body: dict). Revalidar autoridade e alvo da resposta original antes de replay; recibo/audit/mutação no mesmo commit. Não confundir com PartnerCommandReceipt de processo futuro.

- [ ] RED: test_comex_commercial_active_is_not_operational afirma access-options=[], seleção 503 e nenhuma tabela de contexto tenant alterada; test_internal_cannot_select_partner_context afirma 403; test_unknown_fields_fail_closed afirma 422 para tenant/role/grant arbitrários; test_lifecycle_post_idempotency afirma mesma chave um efeito, payload diferente 409, role revogada nega replay; CSRF ausente nega mutação.
- [ ] Rodar uv run --frozen pytest tests/test_partner_availability.py tests/test_partner_lifecycle.py -q; FAIL esperado.
- [ ] GREEN: ligar T2/T3 às rotas e somente DTOs mínimos de indisponibilidade. Contexto tenant no header nunca aceita entrada PARTNER. Revalidar platform assignment depois dos locks. Nenhum feature flag do browser liga COMEX ou Finance.
- [ ] Rodar testes T1–T4 e auth/context existentes; PASS sem expor dados estrangeiros.
- [ ] Commit: feat: expose guarded partner lifecycle and unavailable domain boundary.

### T5 — Frontend tipado, convite PARTNER e estado indisponível

**Files:** criar frontend/src/partners/types.ts,validate.ts,api.ts,PartnerAvailability.tsx e validate.test.ts,api.test.ts,PartnerAvailability.test.tsx; modificar auth/AccessLifecycle.tsx e AccessLifecycle.test.tsx apenas para alvo discriminado.

**Interfaces:** parsePartnerAvailability(value: unknown): PartnerAvailabilityDTO | null; fetchPartnerAccessOptions(client: ApiClient, signal: AbortSignal): Promise<PartnerAccessOptionsDTO>; PartnerAvailability(props: {state: 'loading'|'unavailable'|'invalid'|'unauthenticated'}). Nenhum provider operacional fake ou lista de processos local nesta entrega.

- [ ] RED: unknown schema/status/extra autoridade resulta null e controles bloqueados; resposta atrasada após logout/convite trocado não altera view; convite PARTNER mostra alvo correto sem catálogo de perfis; DOMAIN_UNAVAILABLE apresenta mensagem clara, sem empresas/unidades fake ou controles financeiros.
- [ ] Rodar npm.cmd test -- src/partners/validate.test.ts src/partners/api.test.ts src/partners/PartnerAvailability.test.tsx src/auth/AccessLifecycle.test.tsx; FAIL esperado.
- [ ] GREEN: DTO discriminado e validation runtime; reutilizar ApiClient/AbortSignal, guards de geração e sessão; sem inferir classe de platform_role=null ou alterar operational/types.ts. Não introduzir entrypoint operacional na Demo/Workspace.
- [ ] Rodar comando anterior, npm.cmd run lint e npm.cmd run build; PASS.
- [ ] Commit: feat: consume partner invitation and unavailable domain contracts.

### T6 — Concorrência, regressão integral e fechamento da entrega A

**Files:** criar backend/tests/test_partner_concurrency.py; complementar testes das tarefas proprietárias; atualizar docs/superpowers/plans/2026-10-11-hiatlas-partner-portal-v1.md com evidências e limites entregues.

**Interfaces:** consumir services T2/T3/T4; usar Session/engines reais e barreiras como tests/test_access_tokens.py, sem mocks de autorização/DB para aceitar segurança.

- [ ] RED: test_concurrent_invite_accept_has_one_effect; test_reissue_vs_accept_linearizes; test_platform_role_revoked_while_waiting_denies_lifecycle; test_membership_replace_same_version_one_winner; test_receipt_audit_failure_rolls_back. Assert um único efeito/audit, conflito explícito, permissões finais completas e ausência de sessão privilegiada residual.
- [ ] Rodar uv run --frozen pytest tests/test_partner_concurrency.py -q; documentar falha real antes de corrigir tarefa proprietária. Se invariantes já passam, registrar teste de regressão GREEN e não inventar RED artificial.
- [ ] Aplicar somente correções necessárias com ordem de locks do spec; rodar testes T1–T6.
- [ ] Revisar branch integral: diff desde c50353a, nenhuma Demo/main/outro módulo habilitado, nenhum Process fake, nenhum catálogo PARTNER atribuível a TenantRole, nenhuma edição de classificação financeira.
- [ ] Executar da raiz .\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'. Exigir backend/frontend/scripts/lint/TypeScript/Vite/build/diff PASS, zero skips e cleanup PASS com exit 0. Guardar contagens e saída real; gate falho requer diagnóstico/correção/reexecução, sem declarar sucesso parcial.
- [ ] Commit final local, git status --short vazio, registrar SHA e limites. Nenhum push. Entrega A permanece fundação sem processos operacionais.

## Gate B — antes do plano de sharing/logística/timeline

A COMEX Process Foundation precisa de spec próprio aprovado e implementação validada que forneça: processo scoped tenant/contract/unidade/projeto real; invariantes/ciclo de vida/componentes logísticos; fatos reportados versus aceitos; permissões TENANT customizáveis, capabilities/módulo operacional reais; identidade de evento/documento e locks. A arquitetura desse domínio NÃO é escolhida silenciosamente por este plano.

Com essa base, plano B terá tarefas independentes para: (B1) ContractPartnerLink/access_epoch e PartnerProcessGrant/grant_epoch com FK real; (B2) PartnerAccessContext opaco vinculado a sessão/member/link/epoch e discovery atual; (B3) policy membro ∩ grant ∩ módulo ∩ estado e grants TENANT com unit scope; (B4) publicação por organização/versão externa/listagem filtrada/cursor; (B5) comandos logísticos fechados, timeline imutável, correções e relatos de fechamento; (B6) receipt com autorização do snapshot original e testes de revogação/locks; (B7) provider PARTNER real com duas abas e controles fail-closed. O plano detalhado então deve nomear os arquivos/signatures efetivos do COMEX aprovado, em vez de inventá-los agora.

Aceitação obrigatória de B: dois tenants/contratos/parceiros, scopes distintos, unit ALL não autoriza parceiro, todos os motivos de revogação do spec, revogar grant incrementa access_epoch atomicamente, novo compartilhamento não reativa contextos/receipts/audiências, versão externa não vaza atividade oculta, replay autorizado no estado final não reexecuta efeito, cross-context/tab response não contamina UI. Nenhum evento de outro parceiro expõe autoria/evidência sem publicação redigida TENANT.

## Gate C — antes do plano de documentos/payment intake

Definir e aprovar integração de scanner real e contrato fechado de intake Finance; não construir mocks de produção que retornem clean/paid. Após B, plano C detalhará (C1) documentos privados, quotas/versões/audiências e QUARANTINED; (C2) scanner verdict autenticado/auditável, AVAILABLE/REJECTED e downloads privados; (C3) PartnerPaymentRequest separado com decimal/moeda, beneficiário server-side e estados intake; (C4) validação TENANT sem auto-validação e fronteira Finance; (C5) publicação explícita de status/comprovantes sem approvals/execution PARTNER; (C6) UI/testes race/replay/documentos/dependências originais. Finance executor completo permanece deferred.

Aceitação de C: limite 5 MiB real + envelope 64 KiB, dez evidências, quota 100 MiB incluindo retenção, formatos fechados, nenhum arquivo público, scanner ausente bloqueia disponibilidade, audiência revogada nega replay/download, read_org individual obrigatório mesmo para autor, grants do processo atuais, estados programado/pago apenas de Finance real, revogação bloqueia também acompanhamento financeiro. Preservar eventos e documentos submetidos; NF/NFS não é autorização fiscal/pagamento.

## Self-review e cobertura

Spec 1–5 e identidade de 6/8/9/13–15: T1–T6. Segurança operacional de 6–10/13–16: gate B; arquivos/pagamentos de 11–12/16: gate C. Requisitos não executáveis hoje estão explicitamente bloqueados, não omitidos ou substituídos por dados sintéticos. Riscos/deferred da seção 17 continuam fora da entrega A.

Assinaturas de T1–T5 são contratos deste plano; referências cruzadas usam os mesmos nomes. T4 não depende de contexto/processo inexistente; T5 não inventa login/role. A disponibilidade negativa é software real testável, sem afirmar testes positivos de sharing antes de B. Cada tarefa fecha ciclo de testes/revisão/commit. Review Focus possui testes nas tarefas indicadas. Habilitar B/C depende de novas bases validadas e planos revisados.

Status: plano escrito e self-reviewed; aguardando revisão do usuário e escolha de método para esta fase. Nenhum código foi implementado.
