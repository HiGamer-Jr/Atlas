# HiAtlas Purchase Request V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registrar necessidades internas multi-item com escopo real, aprovação obrigatória, comprador e histórico imutável.

**Architecture:** Agregado PostgreSQL próprio no monólito FastAPI, distinto dos registros DataHub. Queries/comandos reutilizam Context, membership_role, capability policy e unit_authorization. Estado, histórico, auditoria e idempotência são transacionais; UI apenas apresenta o contexto calculado pelo servidor.

**Tech Stack:** Python >=3.13.15, FastAPI/Pydantic, SQLAlchemy/Alembic, PostgreSQL 18, React 19, TypeScript, Vitest/Testing Library, PowerShell. Dependências locked existentes; nenhuma nova.

**Spec:** ../specs/2026-10-08-hiatlas-purchase-request-v1-design.md, aprovado em 2026-10-08, incluindo aprovação obrigatória por pessoa diferente do solicitante. Ler ambos antes de executar. Este plano aguarda revisão e escolha do método; nesta etapa somente documentação.

## Global Constraints

- Base exclusiva: `feat/hiatlas-customer-scope-v1`, `fa354b73cdb43d600949e54b81595f416ef5cd65`. Branch `feat/hiatlas-purchase-request-v1`, worktree `D:/Atlas/.worktrees/hiatlas-purchase-request-v1`.
- Sem alterações em main, integration, release, Demo; sem deploy. Sem push, merge, rebase, tags ou apagar branches.
- Solicitação de Compra não é Pedido de Compra: não constitui compromisso com fornecedor, ordem de pagamento, movimentação de estoque ou autorização financeira.
- Aprovação obrigatória após triagem na V1, por pessoa diferente do solicitante. Dispensa configurável por contrato e cadeias de aprovação ficam para evolução.
- Todas as entidades de negócio têm tenant_id/contract_id não nulos; FKs compostas impedem referências cruzadas; autoria deriva do servidor.
- X-HiAtlas-Context opaco; revalidar sessão/tenant/contract/membership/TenantRole/unit scope/node/módulo/capability; INTERNAL sem TenantRole artificial ou requests por suporte/grants.
- ALL não é node persistido; RESTRICTED não expande descendants implicitamente; ALL→RESTRICTED não restaura grants dormentes, atualização atômica/versionada/auditada preservada.
- Discovery acima do limite 1000 continua 503 explícito e sem árvore truncada. Capabilities são descrição para UX, nunca credencial.
- Unidade solicitante V1: UNIT, STORE, DISTRIBUTION_CENTER, WAREHOUSE, OFFICE, WORKSITE, BRANCH; COMPANY agrupamento.
- Limite 100 itens; Numeric(18,6)>0; Decimal no wire como string, sem float. UOM UN/KG/G/L/ML/M/M2/M3/CX/PCT; CX/PCT exigem conteúdo em specification.
- Título200; descrição/justificativa/notes/specification4000; descrição item2000; NORMAL/HIGH/URGENT; needed_on date e timestamps UTC.
- Estados DRAFT/SUBMITTED/IN_TRIAGE/AWAITING_APPROVAL/APPROVED/IN_FULFILLMENT/FULFILLED/CLOSED/REJECTED/CANCELLED. Atribuição atributo/evento; parcial projeção por item.
- expected_version em toda mutação existente; Idempotency-Key UUID obrigatório nos POSTs; replay reautoriza. Estado/histórico/auditoria/receipt no mesmo commit.
- Anexos bytea privados, 5 MiB/arquivo, 10/request, PDF/PNG/JPEG/TXT; sem HTML/SVG/executáveis/criptografados/fetch remoto. Download no-store/attachment/nosniff.
- project_id/cost_center_id não nulos: REFERENCE_DOMAIN_UNAVAILABLE. Sem catálogo sintético, dados demonstrativos, DeploymentBanner, PARTNER código, pedidos/estoque automático/pagamentos/dashboards/localStorage autorização.
- Não relaxar database_harness, migrações ou runtime; sem SQLite; zero skips. Preservar financeiro/fiscal/classificações sensíveis.

## Review Focus

1. Replay após perda de escopo não devolve detalhe antigo nem duplica atendimento (Tasks4–5).
2. Count/cursor/filtros não revelam nomes/contagens estrangeiros antes de autorização (Task3).
3. Limites Numeric(18,6), float JSON, NaN e concorrência não causam perda de precisão/excesso (Tasks1/5).
4. Revogação/candidato durante lock administrativo não sobrevive revalidação nem causa deadlock não tratado (Tasks2/4).
5. Resposta tardia/anexo malformado/troca de aba não restaura workflow antigo ou conteúdo executável (Tasks6–7).

## File map, ordem e execução

Uma feature com invariantes compartilhadas: executar 1→2→3→4→5→6→7→8. Nenhuma task é release separada. Commits locais após testes focados verdes; entrega apenas após gate integral. Sem agentes antes da escolha do método.

- Novo `backend/app/procurement/__init__.py` e `requests/__init__.py` junto Task1.
- `backend/app/procurement/requests/`: models.py, schemas.py, command_schemas.py, policy.py, queries.py, commands.py, transitions.py, events.py, idempotency.py, assignment.py, fulfillment.py, attachments.py, routes.py. Responsabilidades nas tasks.
- `backend/alembic/versions/0014_purchase_requests.py`; model discovery em backend/alembic/env.py e backend/app/main.py apenas conforme padrão existente.
- Modificar backend/app/tenancy/models.py, platform/capabilities.py, organization/modules.py, tenancy/operational_scope.py, audit/schemas.py, api/router.py.
- `backend/tests/fixtures/purchase_requests.py`, `test_purchase_request_{schema,policy,queries,commands,fulfillment,attachments,concurrency}.py`; conftest registra fixture/tabelas cleanup, database_harness intacto.
- Novo `frontend/src/procurement/requests/`: types.ts, validate.ts, api.ts, state.ts, RequestWorkspace.tsx, RequestForm.tsx, RequestDetail.tsx, testes colocalizados e CSS local. Modificar operational/validate.ts/test, datahub/TenantWorkspace.tsx/test; api/client.ts/test apenas se faltar transporte binário.
- docs/architecture/purchase-request-v1.md e docs/superpowers/validation/2026-10-08-hiatlas-purchase-request-v1-report.md / -quality-gate.txt.

## Convenções e fixtures

Backend cwd backend: `uv run --frozen pytest tests/<arquivo> -q`. Usar módulo oficial `./scripts/testdb.psm1`, Start-HiAtlasTestDb -PostgresRoot 'D:\Atlas\.tools\pgsql18', Assert-HiAtlasTestDb e Stop-HiAtlasTestDb em finally na mesma sessão proprietária. Ambiente ausente não conta como RED. Não imprimir credenciais/URLs. Frontend cwd frontend: `npm.cmd test -- src/<arquivo>`.

Fixture `purchase_case` registrada em conftest, dataclass PurchaseCase em fixtures/purchase_requests.py: requester/triager/approver/buyer (TestClient tenant distintos); headers dict[str,dict[str,str]]; ids dict[str,UUID] com dois tenants, dois contratos no mesmo tenant, memberships/roles e nodes COMPANY/UNIT/WORKSITE/estrangeiro; owner:Engine. `post(actor:str,suffix:str,body:dict,*,key:UUID|None=None)->Response` injeta contexto/CSRF/chave; `ready_request(status:str)->dict` percorre comandos reais após Task4. Antes das routes, testes usam PostgreSQL/model/schema scoped diretamente. Dados de fixture somente em testes.

Signaturas abaixo usam Session, Request, Principal de identity.schemas, AccessScope de tenancy.schemas, UUID e Decimal. Sem segundo Context e sem commits internos: get_db controla transação. Schemas compartilham nomes entre tasks.

### Task 1: Persistência e invariantes scoped

**Files:** packages, models.py, schemas.py, command_schemas.py, migração0014, fixtures e conftest; tenancy/models.py e platform/capabilities.py. Tests test_purchase_request_schema.py, test_foundation_schema.py, test_migration_lifecycle.py.

**Interfaces:** Models PurchaseRequest, PurchaseRequestItem, PurchaseRequestEvent, RequestFulfillmentEntry, RequestAttachment, RequestCommandReceipt. Schemas RequestCreate, DraftPatch, VersionCommand, ReasonCommand, AssignmentCommand, FulfillmentCommand, NoteCommand, RequestView, ItemView, RequestPage, RequestHistoryPage, BuyerCandidatePage, AttachmentView. Literals RequestStatus/Priority/UomCode com valores globais. RequestView schema_version1 e campos do spec; ItemView quantidades string. Receipt unique tenant/contract/actor/context/route/target/key, digest/resultado tipado sem TTL.

- [ ] Escrever `test_scoped_foreign_keys_and_immutable_history`, `test_runtime_grants_and_migration_lifecycle`, `test_payload_limits_and_exact_decimals`:

```python
assert RequestCreate(requesting_node_id=unit_id,title="Necessidade real").items == []
assert FulfillmentCommand(expected_version=1,item_id=item_id,quantity="0.000001",evidence="Recebimento documentado",reason="Atendimento real").quantity == Decimal("0.000001")
# ValidationError: float0.1,0,NaN,1.0000001,1000000000000.000000; title201; items101; CX/PCT sem specification.
# IntegrityError: scope estrangeiro em membership/node/item/event/attachment; runtime UPDATE/DELETE histórico/entry/receipt e DELETE request denied.
```

- [ ] Rodar schema/lifecycle/foundation tests e confirmar RED pelas novas interfaces/invariantes.
- [ ] Implementar models/payloads com FKs compostas e extra=forbid; project_id/cost_center_id opcionais somente null, não nulos produzem 422 REFERENCE_DOMAIN_UNAVAILABLE por validação de comando (não aceitar IDs sem domínio). Testar erro/código exatos e rejeição de tenant/contract/requester/role/status nos payloads. Autoria `(tenant,contract,membership,user)` referencia uq_membership_support_target existente; buyer scoped. Children incluem request/item nas FKs para impedir cross-request. Events sequence único; entries compensatórias com original único e signo interno, quantity do browser positiva. Bytea privado; runtime UPDATE/DELETE apenas dados mutáveis allowlisted. Migração guard owner/runtime da0013 e downgrade recusa perda de evidência não vazia. Dez capabilities `procurement.requests.{create,read_own,read_unit,triage,approve,assign,fulfill,cancel,close,comment}` tenant_role/tenant_enabled true, domain procurement/module PROCUREMENT; reads read_only_safe e não mutam, demais mutam; catálogo e constraint SQL coerentes. Sem grants automáticos; PROCUREMENT operacional só Task4.
- [ ] Reexecutar mesmos testes e ruff dos arquivos: PASS/zero skips.
- [ ] Commit local `feat: add scoped purchase request persistence`, git add apenas arquivos da task.

### Task 2: Policy e comprador candidato reais

**Files:** policy.py, test_purchase_request_policy.py, fixtures complementares.

**Interfaces:** `require_request_actor(db,principal,scope,action:str)->Membership`; `require_request_unit(db,principal,scope,node_id:UUID,action:str)->OrganizationNode`; `authorize_request_read(db,principal,scope,row:PurchaseRequest)->None`; `require_buyer_candidate(db,principal,scope,node_id:UUID,buyer_membership_id:UUID)->Membership`. Antes Task4, patch do catálogo operacional somente no teste; não simular grants de produção.

- [ ] Escrever `test_custom_role_without_admin_permissions`, `test_all_zero_one_multiple_units`, `test_own_read_still_requires_scope`, `test_company_ancestor_foreign_node_and_internal_denied`, `test_candidate_same_contract_current_scope_permissions`:

```python
assert require_request_unit(db,requester_principal,scope,unit_id,"create").id == unit_id
# ApiError403: capability/module/role/member/node inativo, scope estrangeiro, INTERNAL/support/grant.
# read_unit não lê draft alheio; owner sem unidade denied; buyer sem fulfill+read_unit/scope denied e grants intactos.
```

- [ ] Rodar policy tests, confirmar RED no comportamento/interfaces novos.
- [ ] Implementar por revalidate/membership_role/require_capability(module_code="PROCUREMENT")/require_authorized_node; bloquear INTERNAL antes de permissões. read_own exige user+membership autoria+unidade atual; read_unit scope atual, rascunho privado. Action não concede read. Cancel também exige cancel além da relação. Candidate tenant real ativo, mesmo contrato, role fulfill/read_unit e scope atual; nome role nunca autoriza. Registrar ordem atual de locks contexts/organization/membership no doc arquitetura; não introduzir locks invertidos de usuários candidatos. Testes concorrentes definitivos Task4.
- [ ] Reexecutar policy/schema PASS/zero skips; classificações sensíveis intactas.
- [ ] Commit local `feat: enforce real scope on purchase requests`.

### Task 3: Queries privadas e paginação

**Files:** queries.py, routes.py GETs, api/router.py; test_purchase_request_queries.py.

**Interfaces:** `get_request(db,principal,scope,request_id:UUID)->RequestView`; `list_requests(db,principal,scope,filters:RequestFilters)->RequestPage`; `request_history(db,principal,scope,request_id,limit:int,cursor:str|None)->RequestHistoryPage`; `buyer_candidates(db,principal,scope,node_id,limit,cursor)->BuyerCandidatePage`. RequestFilters schemas.py: visibility own|unit defaultown, status/node/requester/buyer, limit1..100,cursor. Page items/total/next_cursor; cursor bounded valida scope/filtros/versão, inválido422. Prefixo /api/procurement/requests, buyer-candidates antes /{id}; no-store.

- [ ] Escrever `test_count_cursor_filters_never_leak`, `test_private_draft_and_history_without_audit_read`, `test_minimal_scoped_candidates`, `test_uniform_foreign_missing_404`:

```python
assert body["total"] == len(authorized_matches)
assert {row["id"] for row in body["items"]} <= permitted_ids
assert response.headers["cache-control"] == "no-store"
assert "FOREIGN_NODE" not in response.text and "email" not in candidates_response.text
# cursor estrangeiro/filter diferente rejected; requester filter own422; foreign/missing404; zero scope total0.
```

- [ ] Rodar queries tests e confirmar RED de leitura/scoping; seeds SQL até Task4.
- [ ] Implementar tenant/contract+unit+own/draft predicates antes de count/paginação/projeção. resolve_unit_scope bounded para listas, require_read detalhe; history privado nunca audit.read. Candidates assign/read_unit/unidade, filtrar elegibilidade antes count/limit e expor só membership_id/nome. Revalidar após locks/antes retorno. Cursor não prova autorização nem permite trocar contexto.
- [ ] Reexecutar query/policy PASS/zero skips.
- [ ] Commit local `feat: add private purchase request queries`.

### Task 4: Workflow, assignment, auditoria e idempotência

**Files:** commands.py, transitions.py, events.py, idempotency.py, assignment.py; audit/schemas.py, routes.py, organization/modules.py, tenancy/operational_scope.py; test_purchase_request_commands.py/concurrency.py e docs/architecture/purchase-request-v1.md.

**Interfaces:** `create_request(db,request,principal,scope,payload:RequestCreate,key:UUID)->RequestView`; `update_draft(db,request,principal,scope,request_id,payload:DraftPatch)->RequestView`; `transition_request(db,request,principal,scope,request_id,command:RequestAction,payload:VersionCommand|ReasonCommand,key:UUID)->RequestView`; `assign_buyer(...,payload:AssignmentCommand,key:UUID)->RequestView`; `add_note(...,payload:NoteCommand,key:UUID)->RequestView`. Ellipsis expande exatamente db,request,principal,scope,request_id, na mesma ordem. RequestAction Literal submit/start-triage/request-approval/approve/reject/start-fulfillment/cancel/close em transitions.py; `transition_target(status:RequestStatus,command:RequestAction)->RequestStatus` tabela pura. `append_request_event(db,request,principal,scope,row,action:str,before:RequestAuditSnapshot|None,after:RequestAuditSnapshot,details:RequestEventPayload)->None`; RequestAuditSnapshot em audit.schemas contém request_id/scope/version/status/node/requester/buyer, actor_membership_id/tenant_role_id/code e changes allowlisted, sem bytes/texto irrestrito; RequestEventPayload em events.py é union fechada para transição, atribuição, item/quantidades, nota e attachment id/digest. Sem services importados em audit. `run_idempotent(db,principal,scope,route:str,target_id:UUID|None,key:UUID,payload_digest:str,operation:Callable[[],RequestView])->RequestView`; operação usa transação do request, replay após policy/read atuais. Nenhum commit interno.

- [ ] Escrever `test_workflow_and_every_invalid_state_pair`, `test_self_approval_denied_and_content_frozen`, `test_atomic_audit_event_sequence_and_assignment`, `test_retry_conflict_and_scope_revoked`, `test_revocation_wait_and_admin_lock_order`:

```python
assert submitted["status"] == "SUBMITTED" and submitted["version"] == draft["version"] + 1
assert self_approval.status_code == 403
assert reassigned["status"] == "APPROVED" and reassigned["assigned_at"] == assigned["assigned_at"]
assert duplicate.json() == original.json()  # autorização atual; um evento principal/audit
assert stale_version.status_code == 409
# audit failure: nada persistido; key payload diverso409; replay scope perdido denied sem detalhe.
# futures deadline10s: mutação/admin/revogação/assignment cruzadas terminam sem deadlock; após revoke commit denied.
```

- [ ] Rodar commands/concurrency tests, RED por comandos ausentes/comportamento; incluir separadamente removal de grant/capability, node/role/module/contract inativo e membership revogada durante espera, verificando próxima revalidação; ordenar concorrência com barreiras/eventos SQL, sem sleep determinando resultado.
- [ ] Implementar create/draft/transitions exatamente tabela do spec: submit exige conteúdo/needed_on/1..100 itens; URGENT reason no ReasonCommand; datas passadas válidas. Unidade draft mudança exige old+new autorizadas. Freeze conteúdo após submit. Approve por pessoa diversa; reject reason; cancel pela relação+capability; close apenas autor/buyer; notes1..4000 todos exceto DRAFT/CLOSED. Expected_version sob lock/populate_existing; timestamps primeira ocorrência, assignment somente APPROVED/IN_FULFILLMENT, assign obrigatório inclusive triager; candidato revalidado. Audit allowlisted actor_role tenant null, provenance membership/TenantRole nos snapshots; entrada/eventos/receipt atômicos. Idempotency usa IDs do contexto, não valor bruto do header como prova; canonical digest inclui expected_version e payload; replay reautoriza ação+read sem reaplicar transição, payload diverso409. Preservar snapshot do resultado privado sem vazar dados ao replay revogado.
- [ ] Completar POST/PATCH routes Context/CSRF/erros/no-store; PROCUREMENT em OPERATIONAL_MODULES e filtro request capabilities sem node elegível; não mudar actor union/DataHub. Rodar tasks1–4 + test_operational_scope_api.py/test_customer_scope_command.py PASS/zero skips. Registrar ordem de locks testada contra comandos existentes; se exigir alteração do desenho/garantia, apresentar ajuste, nunca contornar revalidate. Task4 é entrega de workflow, tasks5–6 completam domínio antes entrega final.
- [ ] Commit local `feat: add audited purchase request workflow`.

### Task 5: Atendimento real por item

**Files:** fulfillment.py, test_purchase_request_fulfillment.py; routes.py/events.py/queries.py.

**Interfaces:** `record_fulfillment(db,request,principal,scope,request_id,payload:FulfillmentCommand,key:UUID)->RequestView`; `reverse_fulfillment(db,request,principal,scope,request_id,entry_id:UUID,payload:ReasonCommand,key:UUID)->RequestView`; `fulfillment_totals(db,scope,request_id:UUID)->dict[UUID,Decimal]`; `fulfillment_state(items:list[ItemView])->Literal["NONE","PARTIAL","COMPLETE"]`. Consumir policy/events/idempotency da Task4; não escrever estoque/pedido.

- [ ] Escrever `test_multi_item_partial_complete_close`, `test_compensation_once_preserves_original`, `test_partial_cancel_keeps_quantities`, `test_decimal_overdelivery_and_foreign_item`, `test_concurrent_and_idempotent_fulfillment`:

```python
assert partial["status"] == "IN_FULFILLMENT" and partial["fulfillment_state"] == "PARTIAL"
assert complete["status"] == "FULFILLED" and complete["fulfillment_state"] == "COMPLETE"
assert cancelled["items"][0]["fulfilled_quantity"] == "1.000000"
# entrada original intacta; segunda reversão409; FULFILLED reverse409; float/NaN/cross-item rejeitados.
# soma concorrente <= requested; apenas assigned buyer+fulfill+read opera; record completo tem version+1, eventos recorded/fulfilled com sequences diferentes e mesma aggregate_version.
```

- [ ] Rodar fulfillment/concurrency tests; confirmar RED nas novas operações.
- [ ] Implementar MANUAL_EXTERNAL evidence1..4000/reason1..2000 obrigatórios, quantity Decimal positiva representável, saldo sob lock agregado/itens estável. Compensação exatamente original positivo não revertido, só IN_FULFILLMENT; signo/source_kind não editável no browser. Completo quando todos itens atendidos; cancel conserva quantidades/saldo. PARTIAL permanece projeção em cancel parcial, não some com status terminal. Uma versão por comando mesmo com evento fulfilled adicional; receipt/audit/entries/estado atômicos. Sem auto decisão estoque/compra.
- [ ] Reexecutar fulfillment/concurrency/commands PASS/zero skips; conferir nenhuma escrita em DataHub/finance/stock.
- [ ] Commit local `feat: record real request fulfillment by item`.

### Task 6: Anexos privados e especificações

**Files:** attachments.py, test_purchase_request_attachments.py; routes.py, schemas/events.

**Interfaces:** `add_attachment(db,request,principal,scope,request_id,expected_version:int,item_id:UUID|None,filename:str,content:bytes,key:UUID)->RequestView`; `download_attachment(db,principal,scope,request_id,attachment_id)->AttachmentDownload`; `remove_draft_attachment(db,request,principal,scope,request_id,attachment_id,expected_version:int)->RequestView`; `validate_attachment(content:bytes,filename:str)->ValidatedAttachment`. Dataclasses neste arquivo: AttachmentDownload(content:bytes,filename:str,media_type:str); ValidatedAttachment(filename/media_type/digest:str,size:int).

- [ ] Escrever `test_download_fresh_private_no_cache`, `test_type_size_encryption_malformed_and_filename`, `test_cross_item_denied`, `test_concurrent_tenth_file_and_audit_rollback`, `test_draft_delete_and_terminal_rules`:

```python
assert response.headers["cache-control"] == "no-store"
assert response.headers["x-content-type-options"] == "nosniff"
assert response.headers["content-disposition"].startswith("attachment;")
assert too_large.status_code == 413  # 5*1024*1024+1; limite exato válido
# MIME falso/SVG/HTML/executable/PDF criptografado ou truncado/UTF8 inválido rejected; CRLF/path sanitizados.
# 11º arquivo422; race<=10; foreign file/item404; failure não deixa bytes/metadados/version/event.
```

- [ ] Rodar attachments tests e confirmar RED nas novas regras.
- [ ] Implementar multipart allowlisted um arquivo, leitura incremental até limite+1, impedir corpo ilimitado antes de parse quando disponível; limites não dependem de Content-Length confiável. Pillow verify de PNG/JPEG com bound25M pixels/decompression-bomb; TXT UTF8 estrito e rejeitar HTML/SVG/executable disfarçado; PDF signatures/end marker, detector conservador de Encrypt/JavaScript/Launch rejeita, sem alegar scanner. Sanitizar filename/disposition sem CRLF/path. Lock agregado version/limite10; auth antes de bytes quando possível; digest na key. DRAFT autor/create; SUBMITTED/IN_TRIAGE/AWAITING_APPROVAL/APPROVED/IN_FULFILLMENT/FULFILLED comment+read; terminais não adicionam. Delete apenas próprio DRAFT com version/event/audit; downloads auth atual. Bytea privado sem URL/storage externo/TTL import; bytes não entram audit/history.
- [ ] Reexecutar attachments/schema/commands PASS/zero skips; risco scanner ausente documentado, sem nova dependência.
- [ ] Commit local `feat: add private request specifications and attachments`.

### Task 7: Frontend de contexto real e UI mínima

**Files:** frontend/src/procurement/requests/{types,validate,api,state}.ts, RequestWorkspace.tsx, RequestForm.tsx, RequestDetail.tsx, testes colocalizados e CSS local. operational/validate.ts/test, datahub/TenantWorkspace.tsx/test; api/client.ts/test só se necessário para binário privado.

**Interfaces:** Types espelham RequestView/Page/History/Candidates/AttachmentView sem floats. `parseRequest(value:unknown,expected:{tenantId:string;contractId:string}):RequestView`; parseRequestPage/parseRequestHistory com mesmos parâmetros; `purchaseRequestApi(client:ApiClient)` métodos list/detail/create/updateDraft/command/assign/fulfill/reverse/note/history/candidates/addAttachment/downloadAttachment/removeAttachment, mapeados às routes Tasks3–6. `usePurchaseRequests()` estado discriminado idle/loading/ready/unavailable, binding(contextId/scope signature), requestId/generation para abort/response stale. `RequestWorkspace()`, `RequestForm({draft:RequestView|null,onSaved:(value:RequestView)=>void})`, `RequestDetail({requestId:string})` usam provider real. Commands enviam expected_version e keys por intenção/payload, client preserva X-Context/CSRF existentes.

- [ ] Escrever em validate/api/state/Workspace/Form/Detail tests: `unknown_state_module_contradiction_closes_controls`, `late_response_cannot_restore_previous_context`, `tabs_are_independent`, `custom_role_real_unit_submission`, `actions_quantities_and_retry_keys`, `private_blob_download_revoked`:

```typescript
expect(screen.queryByRole('button', {name: 'Enviar solicitação'})).not.toBeInTheDocument(); // scope inválido/loading
expect(postBody.requesting_node_id).toBe(realAuthorizedNode.id);
expect(postBody.items[0].requested_quantity).toBe('0.000001');
expect(postBody).not.toHaveProperty('tenant_id');
expect(secondAttempt.headers['Idempotency-Key']).toBe(firstAttempt.headers['Idempotency-Key']);
// response A após contextB não mostra A; INTERNAL/inativo/uncontracted sem controles; erro409 exige refresh/decisão, sem auto merge.
```

- [ ] Rodar `npm.cmd test -- src/operational/OperationalScopeProvider.test.tsx src/procurement/requests/ src/datahub/TenantWorkspace.test.tsx`; RED nas interfaces/componentes novos, não setup.
- [ ] Implementar parser operacional aceitando PROCUREMENT implementado e dez capabilities, módulos/unidades elegíveis coerentes; desconhecido/fiscal/financial continuam fail-closed. Navegação DataHub/Solicitações só por permissões reais. Lista própria e fila unit quando read_unit; formulário multi-item com title/description/justification/priority/needed_on/UOM/specification reais; sem selects fictícios de project/costcenter/material. Detalhe/história/comments/arquivos/triage/approve/assign/start/cancel/close/fulfill/reverse conforme spec e capabilities; candidates privado, sem permissões administrativas. Exibir UUID identificador, "Atendimento registrado manualmente", sinalizar needed_on passada por data local, não afirmar estoque/pedido automático. Decimal como string até payload. Backend erro revogação fecha ação/recupera scope via client. Binding destrói workflow ao mudar contexto/scope; refresh loading pode guardar draft em Activity hidden, controles jamais ativos. Key retry preservada por mesma intenção e novo payload nova key, sem autorização no storage. Download blob privado e revokeObjectURL após uso; abort/generation impede reaparecimento de dados antigos. Sem dados Demo/dependências novas.
- [ ] Reexecutar testes novos e regressões operacional/TenantWorkspace/ApiClient; `npm.cmd run lint` e `npm.cmd run build` PASS.
- [ ] Commit local `feat: add real customer purchase request workspace`.

### Task 8: Revisão integral, documentação e gate oficial

**Files:** docs/architecture/purchase-request-v1.md; docs/superpowers/validation/2026-10-08-hiatlas-purchase-request-v1-report.md / -quality-gate.txt. Correções de domínio/testes apenas por achados comprovados; nenhum arquivo Demo/deploy/database_harness.

**Interfaces:** API/state/capabilities anteriores e matriz spec→test no report; sem novas interfaces.

- [ ] Completar doc contrato: request vs order/stock, cinco conceitos de autorização, estados/caps/errors/keys, immutable events/audit/locks, arquivo limits/risco scanner, quantidades/UOM; projetos/costcenter/PARTNER estritamente futuros. Conferir cobertura seção por seção do spec, testes e exclusões.
- [ ] Revisar diff inteiro contra fa354b73cdb43d600949e54b81595f416ef5cd65; buscar Demo/synthetic/DeploymentBanner/localStorage/finance/grants/SQLite/skips e inspecionar ocorrências. Review independente conforme método escolhido pelo usuário; corrigir achados com RED/GREEN antes de gate. Verificar constraints/migrations/runtime, nomes/capabilities, queries/count e lock concorrente. Sem escolher novo modelo unilateralmente.
- [ ] Na raiz rodar `.\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'` e guardar transcript sem segredos. Exigir backend/frontend/scripts completos PASS, lint backend/frontend/scripts PASS, TypeScript/Vite build PASS, zero skips, git diff --check e staged PASS, cleanup PostgreSQL parada+remoção PASS. Falha exige diagnóstico/fix e novo gate integral; não declarar sucesso parcial.
- [ ] Conferir fresh git status/diff check/ancestry e refs main/Demo/release/integration/customer-scope intactas. Report com comandos/totais reais (não reutilizar contagens da fase anterior), review findings resolvidos, limitações conhecidas, arquivos e exclusões.
- [ ] Commit local final evidências/documentação/correções verificadas, working tree limpa. Entregar SHA, arquivos, contrato API, decisões, riscos/futura fase e resultado integral. Não push/merge/deploy.

## Self-review e gate de execução

Coverage: spec1–4→file map/tasks1–4/7; spec5→Task1/5/6; spec6→Task4/5; spec7→Task2/3/4/7; spec8→Task3–7; spec9–10→Task4–6; spec11→Task8 e exclusões; spec12→testes1–7/gate8; spec13→riscos/report. Nenhuma lacuna além dos domínios explicitamente futuros.

Consistência: read_unit não amplia scope nem revela rascunho; cancel requer própria capability+relação; triage não concede assign; cancel parcial conserva fatos; final não reabre; RequestView compartilhada por commands/idempotency/UI; fixture/types/interfaces definidos antes de consumo. Os cinco Review Focus têm testes na task proprietária. Payloads/header não constituem autorização. Nenhum código/agent/dependência de produto foi iniciado nesta etapa.

Plano aguarda aprovação e escolha do método. Recomendação subagent-driven: autorização real, concorrência e evidência imutável justificam revisão por entregável antes de propagação para UI. Native: execução por mim nesta sessão e revisão independente da branch ao final, menor custo/contextos e sem revisão independente intermediária. Ambas preservam gates/testes/limites acima.
