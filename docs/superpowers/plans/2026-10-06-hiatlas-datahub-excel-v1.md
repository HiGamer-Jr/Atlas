# HiAtlas Data Hub — Excel v1: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar geração oficial XLSX, preview persistente, confirmação atômica, registros informacionais tipados, histórico e exportação contextual do Data Hub.

**Architecture:** Excel implementa um contrato de conector independente dos datasets. Importação, arquivo, linhas, issues e registros finais têm persistência separada; o servidor determina schemas, autorização, referências e duplicidade. Nenhum adaptador operacional ou conector adicional é entregue nesta V1.

**Tech Stack:** Foundation v1: Python/uv, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL; React/TypeScript/Vite, Vitest e oxlint. Acrescentar openpyxl e Pillow com versões resolvidas e travadas no uv.lock durante execução; cryptography já existente protege o arquivo bruto. Não atualizar dependências não relacionadas.

**Spec:** [Spec aprovada](../specs/2026-10-06-hiatlas-datahub-excel-v1-design.md).

## Global Constraints

- Trabalhar exclusivamente em D:/Atlas, branch feat/hiatlas-datahub-excel-v1, base Foundation 641e57502644935ff1c4ca9e06f54b009bb7adc4. HEAD documental inicial: 180989d53b1f1bdcea8f12047e96ba9290a8c112.
- Não alterar release/hiatlas-demo-v1, D:/Atlas/.worktrees/hiatlas-demo-v1, /var/www/hiatlas-demo, hiatlas_demo, VPS/Nginx/systemd; sem deploy, push ou merge na Demo.
- Apenas dados sintéticos em fixtures/planilhas/evidências. Sem criação automática de TenantRoles ou permissões em produção.
- Template ≠ Dataset ≠ Perfil. Perfil oferece composição padrão; capabilities/módulos/escopo reais autorizam cada operação no backend.
- Logo existente, título `HiAtlas — Supply Chain Intelligence`, slogan `Um novo horizonte para o seu negócio`; cabeçalho 12, dados 13, freeze A13 nas abas de dados; LEIA-ME visível e _HIATLAS_META oculta.
- Sem macros, execução de fórmulas, execução operacional, edição genérica, overwrite silencioso, importação parcial com ERROR ou confirmação sem preview persistente.
- Persistir no browser somente identificadores opacos de contexto já permitidos pela Foundation. Nenhum conteúdo Data Hub em storage.
- Este documento é plano, não evidência de execução. Iniciar produto somente após revisão/aprovação deste plano.

## Review Focus

1. Código textual `000123`: manter zeros; célula numérica em coluna de código é rejeitada, não convertida silenciosamente (Tarefa 3).
2. Texto `  =HYPERLINK(...)` ou prefixado por tabulação: exportar como texto literal, enquanto decimal negativo continua numérico (Tarefa 3).
3. Arquivo sem linhas: rejeitar com EMPTY_IMPORT; uma reimportação com todas as linhas SKIPPED pode confirmar com zero inserções (Tarefas 4–5).
4. Referência adiante no arquivo e unidades fora do escopo: resolver referências em duas passagens, negar unidade estrangeira/inativa mesmo com código válido (Tarefas 2–4).
5. Interrupção após armazenamento bruto ou commit com resposta perdida: limpeza de órfãos sem apagar evidência; retry autorizado devolve o mesmo resultado sem segundo evento de sucesso (Tarefas 5–6).

## Decisões de implementação para revisão

### Persistência física

Migração 0011_datahub_excel, após 0010_offline_admin_recovery. Cinco entidades principais: DataHubImport, DataHubImportFile, DataHubImportRow, DataHubImportIssue, DataHubRecord. Record possui metadata comum e exatamente um detalhe tipado: DataHubProduct, DataHubPartner, DataHubDemand, DataHubStockPosition, DataHubComexReference ou DataHubFinancialForecast. Detalhes usam colunas relacionais tipadas, não JSON livre. FKs compostas tenant/contract/record/dataset impedem detalhe de tipo/contexto errado.

Row.normalized_payload é JSONB intermediário, produzido por schemas fechados com extra=forbid; datas ISO e decimals canônicos como strings. Linhas inválidas armazenam somente campos reconhecidos/conversíveis, nunca blob original; não podem gerar Record. Issues não reproduzem valores rejeitados. File metadata é schema fechado, não dicionário extensível.

Business keys são representação canônica de tuplas, calculada pelo servidor, com UNIQUE(tenant_id, contract_id, dataset_code, business_key); estoque usa produto resolvido + unidade resolvida + data_referencia. Fingerprint SHA-256 de schema/dataset/payload normalizado. Record mantém a origem inicial; linha SKIPPED referencia existente. Constraints de escopo também cobrem import/file/row/issues, origem e referências de produtos/parceiros/unidades. Sem DELETE/TRUNCATE runtime nas novas tabelas; SELECT/INSERT/UPDATE somente quando necessário, auditoria inalterada.

### Schemas V1 fechados

Versão 1 de cada dataset, campos da seção 6 da spec. Todos obrigatórios, salvo categoria e referencia_externa, opcionais com ausência canônica. Códigos: texto ASCII alfanumérico com `._-`, 1–64 caracteres, trim/uppercase, zeros preservados. Nomes/descrições NFC, 1–200 caracteres; categoria 0–120; referência externa 0–128; rejeitar controles. Datas: ISO YYYY-MM-DD ou célula Excel date/datetime sem componente de hora. Decimals NUMERIC(20,4), sem arredondamento/truncamento; quantidade >0, estoque >=0, valor >0; rejeitar NaN/Infinity.

Enums: unidade_medida UN/KG/TON/L/M/M2/M3/CX/PAL; tipo FORNECEDOR/CLIENTE/TRANSPORTADOR; modalidade NACIONAL/INTERNACIONAL; prioridade BAIXA/NORMAL/ALTA/URGENTE; moeda BRL/USD/EUR/GBP/CNY; natureza ENTRADA/SAIDA; status COMEX informacional PLANEJADO/EM_ANDAMENTO/CONCLUIDO/CANCELADO; Incoterm EXW/FCA/CPT/CIP/DAP/DPU/DDP/FAS/FOB/CFR/CIF. pais_iso: código ISO alpha-2 validado em catálogo local versionado. Booleanos: células booleanas ou textos SIM/NAO; LEIA-ME explica. Nenhum workflow operacional associado aos enums.

Referências de produto/parceiro apontam para registros tipados do mesmo contrato, existentes ou linhas válidas do mesmo arquivo; unidade_codigo resolve OrganizationNode vigente/autorizado, não cria unidade por importação. Imports ordenam resolução por dependências, não pela posição das abas.

### Autorização e disponibilidade

Introduzir datahub.read, datahub.template.download, datahub.import, datahub.export como capabilities tenant_role/tenant_enabled, domain=datahub; read/download/export seguros para leitura, import mutação. Complementar com capabilities datahub.<dataset>.read/import/export, usando códigos products, partners, demands, stock_positions, comex_references e financial_forecasts: cada dataset exige sua própria capability além da operação geral. TEMPLATE exige read do dataset; EXPORT exige read e export; IMPORT exige read e import, pois preview e resolução de duplicidade projetam dados do dataset. Capabilities financial_forecasts permanecem sensitive=True/tenant_enabled=False e não são concedidas nesta V1. PLATFORM_ADMIN não recebe capacidades Data Hub pelo papel interno. Operações sobre dados de cliente exigem contexto tenant autorizado e capabilities efetivas do membership/perfil vigente; ser operador interno ou selecionar contrato não basta. Support não recebe importação. Qualquer concessão explícita futura deve passar pela mesma política tenant e nunca usar INTERNAL_GRANTS como bypass. TenantRole existente só ganha acesso se tiver essas capabilities atribuídas por fluxo autorizado, nunca pelo nome. Histórico exige read e sua projeção continua limitada aos datasets/unidades atualmente permitidos.

DATAHUB será o único módulo acrescentado a OPERATIONAL_MODULES ao concluir esta feature. Produtos/Parceiros exigem DATAHUB; Demandas exigem também PROCUREMENT contratado/ativo; Estoque exige INVENTORY contratado/ativo; COMEX exige COMEX contratado/ativo. Verificação adicional significa disponibilidade para registros informacionais, não disponibilidade operacional: preservar operational_available=false desses módulos. Centralizar helper de módulo contratado/ativo em platform/policy.py; o require_capability operacional continua exigindo operational_available.

Linhas/abas ou campos sem autorização nunca são enviados à UI; preview/histórico também passam pela política por dataset, não apenas pela capability geral. Datasets unitários exigem escopo MembershipUnitScope para usuário cliente; ausência de escopo falha fechada. PLATFORM_ADMIN não possui escopo de ingestão por ser administrador: somente membership tenant autorizado e escopo vigente podem fundamentar operações sobre dados de cliente, sem fabricar membership nem impersonar. Produtos/parceiros são referências contratuais autorizadas pela capability; não expõem registros unitários. Derived SupportSession e grants não são contextos de importação; gates da Foundation continuam negando operações Data Hub não declaradas.

Financeiro: catálogo/schema/template são conhecidos, mas acesso real permanece bloqueado nesta V1 pela política financeira vigente e FINANCE operational_available=false. Não habilitar finance.read/fiscal.read, não dar permissão financeira a Admin/Support, não aceitar grant financeiro como autorização de escrita. UI informa indisponibilidade. Testar schemas financeiros isoladamente, sem rota de fixture em produção. Não prometer import/export financeiro funcional neste estágio.

Oito templates versionados: COORDENACAO, SUPERVISAO, COMPRADOR_NACIONAL, COMPRADOR_INTERNACIONAL, FINANCEIRO, DIRETORIA, LOJA, CENTRO_DISTRIBUICAO. Composição da spec intersectada com autorização; nenhum dataset permitido → indisponível. Diretoria não tem importação nesta versão do template; importação depende também da capability, nunca do nome do papel. Nacional/internacional restringem modalidade pelo schema do template. CD não inventa dataset logístico adicional; usa produtos/estoque disponíveis. Identificação de perfil no arquivo mostra o TenantRole real ou papel interno real; o template selecionado é mostrado separadamente.

### Limites e contratos públicos

Settings: preview 30 min; bruto 24 h; upload 10 MiB; ZIP descompactado 50 MiB/1000 entradas; 12 abas; 10000 linhas de dados totais; 250000 células; textos limitados pelos schemas; histórico/preview páginas de 50, máximo 100; export máximo 10000 registros e sem truncamento silencioso. Prazo de preview nunca ultrapassa sessão/contexto. Limites configuráveis, erro sanitizado ao ultrapassar.

RawStore privado fora de assets/static, referências UUID geradas; criptografia Fernet com chave Data Hub fornecida por ambiente, separada de outras finalidades, nunca versionada. Settings datahub_enabled=false por padrão; ativação explícita e chave/configuração válidas são necessárias, sem ligar módulos de contratos automaticamente. Configuração ausente/inválida → feature indisponível, não plaintext fallback; produção com Data Hub explicitamente habilitado rejeita startup inseguro. Normalizados persistem com controles de acesso e proteção operacional do PostgreSQL/backup; não ficam sujeitos à expiração do bruto. Sem endpoint de download bruto.

API sob /api/datahub: GET /templates; POST /templates/{template_id}/download (versão/escopo tipados); POST /imports (multipart XLSX); GET /imports (histórico paginado); GET /imports/{id} (summary); GET /imports/{id}/rows e /issues; POST /imports/{id}/confirm; POST /exports (template/filtros/escopo tipados). Reutilizar require_context, authenticated, CSRF/Origin, ApiError/request_id e transações existentes. ConfirmationInput: expected_version >=1, idempotency_key UUID; não aceita payload/registros. Chave em memória por confirmação, sem segredo ou persistência no browser. Respostas nunca incluem armazenamento bruto, hash de senha ou configuração interna.

## Mapa de arquivos

Criar backend/app/datahub/: types.py, catalog.py, schemas.py, models.py, policy.py, repositories.py, normalization.py, validation.py, duplicates.py, raw_store.py, retention.py, services.py, queries.py, routes.py; connectors/base.py e connectors/excel.py. Responsabilidades respectivamente: contratos, catálogos, DTOs, ORM, autorização, consultas de persistência, canonização, validação, comparação, armazenamento bruto, limpeza, lifecycle, projeções e API; conectores apenas formato.

Modificar backend/app/platform/capabilities.py e policy.py; organization/modules.py; api/router.py; db/models.py; core/config.py; main.py; audit/schemas.py; identity/recover_admin.py somente se a política de restore exigir revogar novos artefatos (imports nunca reativados por restore). Criar backend/alembic/versions/0011_datahub_excel.py. Dependências em backend/pyproject.toml e uv.lock.

Criar backend/tests/test_datahub_{catalog,policy,schema,excel,preview,confirmation,races,retention,queries,api}.py e fixtures/datahub_cases.py; ajustar conftest.py, test_runtime_privileges.py, test_migration_lifecycle.py e expectativas de módulos/capabilities comprovadamente afetadas. Nenhuma fixture carregada em produção.

Criar frontend/src/datahub/: types.ts, api.ts, useDataHub.ts, ExcelPage.tsx, TemplatePicker.tsx, UploadForm.tsx, ImportPreview.tsx, ConfirmImportDialog.tsx, ImportHistory.tsx, ExportDialog.tsx, DataHub.css, ExcelPage.test.tsx e DataHub.test.tsx. Modificar frontend/src/api/client.ts (binários/multipart no cliente seguro), App.tsx (permitir portal autenticado de membership autorizado), platform/ContractShell.tsx (navegação), support/Workspace.tsx (não declarar Data Hub operacional sempre indisponível se disponibilidade mudar), testes afetados. Reutilizar providers/headers/contexto, sem outro sistema de autenticação.

Criar scripts/datahub_browser_fixture.py, scripts/datahub_browser_checks.ps1; docs/operations/hiatlas-datahub-excel-v1.md e docs/superpowers/validation/hiatlas-datahub/excel-v1.md. Assets reutilizados: frontend/src/assets/hiatlas-light.png; nenhum logo novo. Resolver asset oficial por configuração/caminho de pacote verificado, nunca path enviado pelo browser; runbook inclui sua distribuição no backend.

## Contratos compartilhados

Tipos definidos em types.py/schemas.py: DatasetCode enum dos seis datasets, Operation enum READ/TEMPLATE/IMPORT/EXPORT; AuthorizedSelection (contexto, datasets, node_ids, limites); WorkbookContext (empresa/contrato/papel/escopo/data UTC); ParsedWorkbook (template/version/linhas/issues); NormalizedRow (dataset/schema/sheet/source_row/payload/fingerprint/key); ImportSummary/ImportDetail/ConfirmationResult/PagedRows/PagedIssues/RetentionSummary como DTOs fechados. Definir também DatasetDefinition, TemplateDefinition, NormalizedPayload (union dos seis schemas), WorkbookLimits, ValidationResult, RawFileReference, ImportQuery, ImportPage, ExportInput e WorkbookDownload nos mesmos módulos: nenhum tipo intermediário aberto. Metadata do template declara schemas/datasets/colunas e os enums, sem autoridade contratual.

Connector Protocol: parse(content: bytes, limits: WorkbookLimits) -> ParsedWorkbook; generate(selection: AuthorizedSelection, context: WorkbookContext, rows: Sequence[NormalizedRow]) -> bytes. Registry de conectores contém somente XLSX; sem plugin/código do browser. Schema do dataset governa ambos os sentidos.

Serviços usam Session, Request, Principal e AccessScope existentes; não fazem commit internamente em mutações de negócio, respeitam fronteira transacional do get_db. Rotas emitem sucesso somente após commit da dependency. Transição técnica independente pós-rollback exige unidade de trabalho separada explicitamente testada.

## Tarefa 1 — Catálogos, schemas e persistência física

**Files:** types.py, catalog.py, schemas.py, models.py, normalization.py; migração 0011; db/models.py, conftest.py; testes catalog/schema e privileges/migrations.
**Interfaces:** produzir dataset_definition(code: DatasetCode, version: int) -> DatasetDefinition; template_definition(template_id: str, version: int) -> TemplateDefinition; normalize_row(dataset: DatasetDefinition, values: Mapping[str, object]) -> NormalizedPayload. Produzir cinco ORM e seis detalhes conforme decisões; nenhuma API pública ainda.

- [x] Escrever RED `test_stock_key_has_no_artificial_code`, `test_five_entities_are_separate`, `test_foreign_provenance_fk_rejected`, `test_runtime_cannot_delete_records`; asserts: stock fields não contêm codigo; tabelas independentes; FK estrangeira falha; DELETE/TRUNCATE runtime falham. Testar precisão/enum/status/version/timestamps, defaults, key igual em contratos diferentes.
- [x] Rodar em backend `uv run --frozen python -m pytest tests/test_datahub_catalog.py tests/test_datahub_schema.py -q`; esperar RED por catálogo/modelos ausentes, sem skips.
- [x] Implementar contratos/normalização/tabelas e constraints; atualizar metadados/limpeza owner das fixtures e grants mínimos, sem relaxar auditoria. Resolver dependências Excel na T3, que é a primeira consumidora do conector; não adicionar bibliotecas não utilizadas nesta T1.
- [x] Rodar os testes acima e lifecycle/privileges: esperar GREEN; migration full-chain e upgrade/downgrade/upgrade em banco descartável owner/runtime separados.
- [x] Commit explícito somente arquivos desta tarefa: `feat: add typed Data Hub catalog and persistence`.

## Tarefa 2 — Autorização contextual, datasets e escopo

**Files:** datahub/policy.py; platform/capabilities.py, policy.py; organization/modules.py; tests/test_datahub_policy.py e testes Foundation afetados.
**Interfaces:** consumir catálogos; produzir authorize_selection(db: Session, principal: Principal, scope: AccessScope, operation: Operation, template_id: str, template_version: int, node_ids: tuple[UUID, ...]) -> AuthorizedSelection. Helper central require_contracted_module(db: Session, principal: Principal, scope: AccessScope, module_code: str) -> None, reutilizado sem enfraquecer require_capability operacional.

- [x] RED `test_profile_name_never_grants_access`, `test_inventory_information_does_not_enable_inventory_operations`, `test_financial_template_fails_closed`, `test_foreign_or_inactive_unit_is_hidden`: asserts 403 sem capability; INVENTORY operacional continua negado; financeiro sem dados; unidade estrangeira 404 e inativa rejeitada.
- [x] `uv run --frozen python -m pytest tests/test_datahub_policy.py -q`: esperar RED pelos contratos novos ausentes.
- [x] Implementar interseção de template/datasets/permissões/módulos/unidades com revalidação vigente; Sem concessão implícita ao Admin; contexto tenant e capabilities efetivas obrigatórios, Support sem importação; DATAHUB disponível sem habilitar demais módulos ou alterar roles persistidos. Histórico filtra acesso vigente.
- [x] Rodar testes policy/role/support/grants/module existentes e novos: GREEN inclusive A/A2/B e ausência de permissões herdadas.
- [x] Commit `feat: enforce contextual Data Hub authorization`.

## Tarefa 3 — Gerador oficial e parsing XLSX seguro

**Files:** connectors/base.py, connectors/excel.py; config.py, pyproject/lock; tests/test_datahub_excel.py.
**Interfaces:** consumir catálogos e Connector Protocol; produzir ExcelConnector.parse e generate com assinaturas compartilhadas. Gerador recebe somente AuthorizedSelection servidor; não decide autorização por perfil.

- [x] RED `test_official_layout_and_readme`, `test_codes_preserve_leading_zeroes`, `test_formula_cache_is_not_a_value`, `test_export_literal_prefixes_and_negative_decimal`; asserts header=12/freeze=A13/logo/LEIA-ME/meta hidden, '000123' intacto, célula fórmula rejeitada, string com espaços/tab/= nunca data_type=f e Decimal negativo numérico. Incluir oito templates, enums/datas/números, células numéricas de código rejeitadas, ZIP bomb/path traversal/macros/external links/manifest alterado/colunas duplicadas/abas desconhecidas.
- [x] `uv run --frozen python -m pytest tests/test_datahub_excel.py -q`: esperar RED por conector ausente.
- [x] Implementar leitura sem cálculo, pacote ZIP inspecionado antes de openpyxl; rejeitar executáveis externos, fórmulas e schemas incompatíveis; escrita textual explícita sem hyperlinks herdados. Gerar só abas autorizadas e instruções correspondentes.
- [x] Rodar testes: GREEN; abrir/renderizar workbook sintético para inspeção visual, registrar ferramenta e limitações sem recalcular arquivos recebidos.
- [x] Commit `feat: add secure branded Excel connector`.

## Tarefa 4 — Upload privado, análise e preview persistente

**Files:** raw_store.py, validation.py, duplicates.py, repositories.py, services.py; config.py/main.py; test_datahub_preview.py; fixtures/datahub_cases.py.
**Interfaces:** consumir ExcelConnector/authorize_selection; produzir create_preview(db: Session, request: Request, principal: Principal, scope: AccessScope, filename: str, content: bytes) -> ImportSummary. RawStore.put(import_id: UUID, content: bytes) -> RawFileReference; remove(reference: RawFileReference) -> None. validate_rows(db: Session, selection: AuthorizedSelection, parsed: ParsedWorkbook) -> ValidationResult.

- [ ] RED `test_preview_writes_no_records`, `test_empty_import_rejected`, `test_forward_reference_resolves`, `test_existing_changed_key_is_error`, `test_raw_not_public_and_key_missing_fails_closed`; asserts Record count=0, EMPTY_IMPORT, referência adiante válida, conflito não sobrescrito, nenhum fallback plaintext. Validar referências externas/unidades/duplicata intra-arquivo e mensagens sem valores brutos.
- [ ] `uv run --frozen python -m pytest tests/test_datahub_preview.py -q`: RED pelas interfaces ausentes.
- [ ] Implementar armazenamento privado cifrado e parsing limitado fora de locks longos; persistir RECEIVED/VALIDATING antes de finalizar READY/REJECTED/FAILED. Parsing síncrono controlado nesta V1, sem queue; recuperação de análise interrompida expira/falha, nunca confirma dados incompletos. Validar em duas passagens e gravar Rows/Issues sem Records, prazo min(settings/sessão/contexto).
- [ ] Rodar testes preview/config/key/storage: GREEN; provar rollback e limpeza de arquivo órfão se TX de recebimento falhar.
- [ ] Commit `feat: persist validated Excel import previews`.

## Tarefa 5 — Confirmação, duplicidade e auditoria atômica

**Files:** services.py, duplicates.py, repositories.py; audit/schemas.py; tests/test_datahub_confirmation.py e test_datahub_races.py.
**Interfaces:** consumir preview persistente; produzir confirm_import(db: Session, request: Request, principal: Principal, scope: AccessScope, import_id: UUID, command: ConfirmationInput) -> ConfirmationResult. DataHubImportSnapshot audit: id/status/version/contagens/template/digest, sem payload de linhas ou bruto.

- [ ] RED `test_confirm_requires_bound_preview`, `test_two_confirms_have_one_commit`, `test_all_skipped_can_commit`, `test_audit_failure_rolls_back`, `test_expired_while_waiting_lock_denied`; asserts sem preview nenhum Record; duas conexões um efeito/evento; zero inserções permitido; falha auditoria mantém dados/status anteriores; expiração após lock sem commit. Cobrir retry após resposta perdida, outra chave, outra sessão/contexto, conflicts posteriores e revogação de role/module/unit/contrato durante lock. A revalidação abrange capabilities por dataset, não apenas a capability geral.
- [ ] `uv run --frozen python -m pytest tests/test_datahub_confirmation.py tests/test_datahub_races.py -q`: RED por confirmação ausente.
- [ ] Implementar locks na ordem Foundation (lifecycle/identidade/contexto/contrato/import/refs), revalidar depois de esperas; UNIQUE + comparação final evita colisões entre imports distintos. Digest/chave/payload no servidor; replay autorizado retorna mesmo resultado somente para comando compatível. Conflito 409 exige nova importação/preview, não ressuscita terminal.
- [ ] Registrar committed/records/provenance/audit em TX única; testar FAILED pós-rollback quando auditoria disponível e último estado estável quando não disponível. Rodar testes e audit-integrity: GREEN, concorrência real sem mocks de locks.
- [ ] Commit `feat: commit Data Hub imports atomically and idempotently`.

## Tarefa 6 — Histórico, exportação e retenção

**Files:** queries.py, retention.py; services.py; tests/test_datahub_queries.py e test_datahub_retention.py; operations runbook.
**Interfaces:** produzir list_imports(db: Session, principal: Principal, scope: AccessScope, query: ImportQuery) -> ImportPage; get_import(db: Session, principal: Principal, scope: AccessScope, import_id: UUID) -> ImportDetail; list_rows/list_issues com os mesmos primeiros argumentos e import_id/pagination, retornando PagedRows/PagedIssues; export_workbook(db: Session, principal: Principal, scope: AccessScope, command: ExportInput) -> WorkbookDownload; cleanup_raw(db: Session, store: RawStore, limit: int) -> RetentionSummary.

- [ ] RED `test_history_rechecks_current_unit_scope`, `test_raw_expiry_preserves_normalized_preview`, `test_cleanup_retry_and_orphans`, `test_export_limit_never_silently_truncates`; asserts registros não autorizados omitidos/ocultos; bruto removido mas Row/Record/provenance persistem e preview vigente confirma; retry não apaga histórico; excesso explícito. Cobrir A/A2/B, export cells, redução de capability e filename sanitizado.
- [ ] `uv run --frozen python -m pytest tests/test_datahub_queries.py tests/test_datahub_retention.py -q`: RED pelos contratos ausentes.
- [ ] Implementar consultas paginadas/projeções e export somente dados autorizados; nunca bruto. Cleanup local limitado/idempotente, DB lifecycle sem DELETE; reconciliar órfãos após margem de segurança configurável e proteger contra paths externos/symlink. Documentar execução operacional da limpeza, chave/retention/backup sem segredos.
- [ ] Rodar testes: GREEN inclusive arquivo bruto expirado independentemente do preview.
- [ ] Commit `feat: add Data Hub history export and raw retention`.

## Tarefa 7 — APIs finas e transporte frontend seguro

**Files:** routes.py, api/router.py; frontend/src/api/client.ts e datahub/api.ts/types.ts; test_datahub_api.py e frontend/src/api/client.test.ts (criar se ausente).
**Interfaces:** rotas exatas em Decisões; FE produzir uploadExcel(file: File, signal: AbortSignal) -> Promise<ImportSummary>, confirmImport(id: string, expectedVersion: number, key: string, signal: AbortSignal) -> Promise<ConfirmationResult>, downloadTemplate/exportExcel -> Promise<Blob>; implementadas pelo ApiClient contextual, sem fetch paralelo sem segurança.

- [ ] RED `test_confirm_api_rejects_client_payload`, `test_upload_csrf_and_origin`, `test_foreign_import_is_neutral`; asserts 422 para campos extras, 403 CSRF/Origin, 404 id externo. Vitest `multipart uses credentials context csrf without manual boundary`, `binary response after context change is discarded`.
- [ ] Rodar backend `uv run --frozen python -m pytest tests/test_datahub_api.py -q`; frontend `npm.cmd test -- src/api/client.test.ts`: RED por novas rotas/transporte ausentes.
- [ ] Implementar DTOs/response_models e chamadas de serviço sem regras no controller; binários e multipart preservam geração, abort, status sanitizado e header contextual. Download não deixa object URLs vivos após uso/context switch. Gates Support/grants negam chamadas diretas.
- [ ] Rodar testes: GREEN, nenhum token/segredo/rawref/payload indevido em respostas, logs, erro Pydantic ou auditoria.
- [ ] Commit `feat: expose secure Data Hub Excel APIs`.

## Tarefa 8 — UX autenticada Excel, preview e confirmação

**Files:** datahub componentes/hook/CSS/tests; App.tsx, ContractShell.tsx, support/Workspace.tsx e testes de integração existentes.
**Interfaces:** produzir ExcelPage() componente contextual; useDataHub() fornece catálogo/preview/estado/actions via api.ts, com AbortController e generation. Consumir tipos públicos da Tarefa 7; não inferir elegibilidade por nome de perfil.

- [ ] RED Vitest `download official template`, `preview errors block confirmation`, `warnings show skipped count`, `confirm only shows committed success`, `financial unavailable`, `logout discards delayed preview`, `membership portal uses server capabilities`; asserts menu capability, contrato visível, row/field issues, diálogo explícito, sem toast sucesso antecipado, sem storage DataHub. Incluir 403/409/expiry/loading/error/retry/empty/history/export/teclado e duas abas independentes.
- [ ] `npm.cmd test -- src/datahub/ExcelPage.test.tsx src/datahub/DataHub.test.tsx`: RED por UX ausente.
- [ ] Implementar navegação Data Hub > Excel e portal mínimo para membership real autorizado, preservando demais ferramentas internas; sem workspace demo/perfilselector. Separar estados terminais e reason técnico sanitizado. Arquivo/input e dados são descartados ao trocar contexto/logout; confirmação usa somente id/version/key, novo preview após 409; Financeiro explica indisponibilidade.
- [ ] Rodar testes FE existentes afetados + novos: GREEN; tema, 390×844, labels, foco dos diálogos, Escape, status textual.
- [ ] Commit `feat: add authenticated Data Hub Excel workflow`.

## Tarefa 9 — E2E, revisão e gate final

**Files:** scripts/datahub_browser_fixture.py/checks.ps1; docs/operations/hiatlas-datahub-excel-v1.md; docs/superpowers/validation/hiatlas-datahub/excel-v1.md; somente correções comprovadas nos arquivos anteriores.
**Interfaces:** factory de teste isolada usa aplicação real e fixtures sintéticas A/A2/B; nenhuma rota/handler secreto na aplicação normal. Reutilizar harness PG e fake SMTP da Foundation.

- [ ] Registrar cenários E2E antes da execução: usuário autorizado baixa/preenche XLSX → upload → preview → confirma → histórico/export; arquivo inválido/duplicado; segunda confirmação; Support negado; isolamento e permission/module revogados; financeiro indisponível. Browser real/headless, light/dark/desktop/390×844/teclado; inspeção de XLSX e screenshots sem dados reais/segredos.
- [ ] Rodar cenários e registrar qualquer RED; corrigir somente defeitos reproduzidos e repetir o cenário correspondente até GREEN. Executar revisão independente backend e frontend após escolha do método pelo usuário; achados relevantes RED/correção/GREEN.
- [ ] Rodar gate completo: backend `uv run --frozen python -m pytest` e `uv run --frozen ruff check app tests alembic`; frontend `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`; raiz `git diff --check`. PostgreSQL real descartável: full-chain, upgrade/downgrade/upgrade, runtime grants, races A/A2/B. Zero skips obrigatórios, nenhum PASS sem comando executado.
- [ ] Completar relatório com branch/base/commits/migration/schema/contagens/comandos/E2E/concorrência/retention/capturas/revisões/limites; runbook explicita staging informacional, financeiro bloqueado, chaves privadas, cleanup e futuros adaptadores. Não chamar módulos operacionais de entregues.
- [ ] Commit final documental; conferir diff e árvore limpa; parar serviços/criar comprovação de remoção de DB/arquivos brutos/segredos de teste. Entregar arquivos alterados, schemas, arquitetura, resultados reais e limitações; sem Demo/deploy/push/merge.

## Autorrevisão do plano

Cobertura: spec §§1–3 → constraints/T2/T8; §4 → T1/T4/T5; §5 → T4/T5/T8; §§6–7 → T1/T2/T3; §§8–9 → T3/T7; §10 → T4/T5/T7/T8; §11 → T4/T6; §12 → T5; §13 → T6/T8; §14 → T9. Os cinco Review Focus têm testes atribuídos. Assinaturas compartilhadas são declaradas antes das tarefas, DTOs fechados em schemas.py e enum único em types.py. Nenhum teste/gate foi executado ao escrever este plano.

## Handoff

Revisar este plano e escolher execução nativa ou por subagentes antes do produto. Recomendação: execução nativa sequencial, com revisão independente ao final; as tarefas compartilham schema, autorização e fronteira transacional, portanto essa sequência reduz divergência entre interfaces. Subagentes por tarefa continuam opção com revisão intermediária e maior custo de contexto.
