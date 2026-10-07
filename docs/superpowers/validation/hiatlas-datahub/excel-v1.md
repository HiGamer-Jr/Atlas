# HiAtlas Data Hub — Excel v1: evidência de execução

STATUS: EM IMPLEMENTAÇÃO; não é encerramento nem aprovação operacional.

Branch: feat/hiatlas-datahub-excel-v1. Base aprovada Foundation v1: 641e57502644935ff1c4ca9e06f54b009bb7adc4. HEAD documental anterior à execução: 180989d53b1f1bdcea8f12047e96ba9290a8c112.

Execução nativa T1 → T9, sem agentes implementadores. Demo intocada; sem deploy/push/merge. Somente fixtures sintéticas. Correção do usuário incorporada: papel PLATFORM_ADMIN não concede capabilities/escopo de dados Data Hub por si só; PLATFORM_SUPPORT sem importação e Financeiro bloqueado.

Commit T1: e51e6d5b48ddc50f642127747f112327302af445.

## T1 — Catálogo, schemas e persistência

RED observado: nove falhas do catálogo ausente; dezessete falhas de tabelas/grants/constraints ausentes em PostgreSQL. Primeiro GREEN focado:49 testes. Números extremos receberam RED de dois casos InvalidOperation; corrigido para validação tipada sem truncamento.

Revisão independente backend /root/review_datahub_t1: achado P2 de zero negativo gerando canonização distinta. Reproduzido RED, corrigido e GREEN; zero/zero negativo agora têm representação 0.0000. Revisor também apontou cobertura física insuficiente; ampliados testes de Record/Row/dataset, Issue/Import, detalhe discriminado, IDs válidos estrangeiros de produto/parceiro/unidade, unicidade A/A2/B e estoque, grants das seis tabelas de detalhes e upgrade incremental com runtime inseguro.

GREEN focado final executado:83 testes, zero skips. Comando: uv run --frozen python -m pytest tests/test_datahub_catalog.py tests/test_datahub_schema.py tests/test_migration_lifecycle.py tests/test_runtime_privileges.py -q. Ruff completo executado: uv run --frozen python -m ruff check app tests alembic → PASS.

PostgreSQL18.6 real descartável, owner/runtime/recovery separados; runtime não owner/superuser. Upgrade full-chain e downgrade/upgrade executados pelos testes de migração; upgrade0010→0011 com owner/superuser/missing runtime recusado antes de DDL. Sem DELETE/TRUNCATE nas onze tabelas novas; auditoria continua append-only.

Migração0011_datahub_excel após0010; DDL congelado, não depende de modelos mutáveis no momento do upgrade. Entidades principais: DataHubImport, DataHubImportFile, DataHubImportRow, DataHubImportIssue, DataHubRecord. Seis detalhes relacionais tipados; row payload intermediário é objeto normalizado por schemas fechados, nunca instrução arbitrária. Ainda não há endpoint Data Hub habilitado na T1.

Uma rodada completa inicial foi interrompida por falta da identidade recovery exigida pela Foundation; NÃO é PASS. A infraestrutura foi corrigida e a reexecução completa passou:827 testes, zero skips, uma depreciação herdada; uv run --frozen python -m pytest -q, 800 segundos. Cluster descartável usa fsync/full_page_writes/synchronous_commit desativados somente para desempenho de testes sintéticos; não prova durabilidade em produção. O cluster anterior próprio foi parado, preservado temporariamente para cleanup.

Warning herdado Starlette/httpx: depreciação conhecida, sem supressão nem atualização de arquitetura. Launcher Windows pytest.exe apresentou trampoline obsoleto; execução via uv run --frozen python -m pytest usa o mesmo ambiente travado Python3.13.15.

## T2 — Autorização contextual validada

RED executado:10 testes falharam pela ausência de política/catalog capabilities. Primeiro GREEN:10. Rodada ampliada inicialmente revelou erro de fixture (cliente sem membership em B); corrigida para identidade com membership válido em B e sem capabilities Data Hub nesse contrato. GREEN focado final:55 testes, zero skips, uma depreciação herdada.

Capabilities gerais e por dataset fechadas; nenhuma adicionada a INTERNAL_GRANTS. Admin necessita membership ativo, role vigente, permissões tenant e escopo explícito; Support sem acesso de conector; contextos derivados de SupportSession/grants não autorizam Data Hub. Financeiro permanece bloqueado. Importação exige read e import do dataset porque o preview/duplicidade pode apresentar dados existentes; nenhum direito é inferido pelo nome do perfil/template.

Somente DATAHUB integra disponibilidade operacional do catálogo; disponibilidade informacional de Demandas/Estoque/COMEX exige módulos contratados/ativos sem habilitar seus domínios operacionais. Sem escopo de unidades, datasets unitários são omitidos; IDs de unidades estrangeiras/inativas/não atribuídas recebem404. Permissões/módulos são revalidados após waits. Casos concorrentes: módulo desativado e contexto expirado durante lock; ambos negados.

Migração incremental0012_datahub_scope: CHECK fechado de capabilities tenant; unit_id/unit_version no preview com FK composta OrganizationNode e CHECK de pareamento/version. Finalidade: congelar identidade da unidade resolvida, sem reatribuição silenciosa quando um código organizacional for reutilizado. Roundtrip0012→0011→0012 executado no banco descartável.

Regressão completa inicial NÃO foi PASS (834 passaram/17 falharam): migrations full-chain da rodada focada foram executadas sem RECOVERY_DATABASE_ROLE, removendo grants da identidade recovery no banco descartável. Diagnóstico somente leitura confirmou ausência dos três grants necessários. Banco descartável verificado vazio/com marcador próprio; full-chain base→0012 reexecutada com owner/runtime/recovery configurados. GREEN focado de recovery/suporte/policy/schema:159 testes. Regressão final completa executada:851 passaram, zero skips, uma depreciação herdada, 720.95 segundos. Um teste antigo de Support workspace foi ajustado para reconhecer somente DATAHUB como entregue, mantendo effective_access vazio e os outros domínios operacionais indisponíveis; nenhum bypass ou alteração do código break-glass foi feito. Ruff completo e git diff --check executados antes do commit.

## T3 — Conector e planilhas oficiais

RED inicial:25 casos pela ausência do conector. GREEN inicial:25. Casos adicionais receberam RED para metadados/versão tipada, coluna extra distante, linha além do limite, código ausente na primeira célula, texto acima do limite Excel, dropdown da modalidade e unidade fora da seleção autorizada; corrigidos sem executar fórmulas. GREEN focado final executado:77 testes (39 do conector, catálogo e configuração), zero skips. Comando: uv run --frozen python -m pytest tests/test_datahub_excel.py tests/test_datahub_catalog.py tests/test_production_config.py -q.

Bibliotecas travadas:openpyxl3.1.5, Pillow12.3.0, defusedxml0.7.1, et-xmlfile2.0.0. Gerador reutiliza frontend/src/assets/hiatlas-light.png; header12, dados13, freezeA13, tabela/filtros, listas enumeradas, LEIA-ME visível, _HIATLAS_META oculto e tipado. Parsing bounded ZIP/XML antes de openpyxl read_only/data_only=false; nenhuma execução de fórmulas ou cache usado como dado. Strings de exportação são células textuais explícitas; números acima da precisão Excel ficam textuais sem perder quatro casas ou zeros de códigos.

Artifact-tool do runtime Node foi usado exclusivamente para inspeção/renderização de oito arquivos sintéticos e suas35 abas visíveis. Capturas revisadas; ferramenta não reproduziu desenhos embutidos e converteu textos numéricos na representação visual. Limitação registrada, sem alegar inspeção visual da logo ou zeros pela captura. Verificação separada confirmou imagens embutidas byte a byte iguais à logo oficial em todos os modelos; testes openpyxl/OOXML verificam códigos e precisão. Não houve recálculo de arquivos recebidos. FINANCEIRO usado somente na fixture isolada de formatação; autorização pública financeira continua bloqueada.

Revisão independente /root/review_datahub_t3 encontrou P2: CellCoordinatesException e zlib.error escapavam da rejeição sanitizada. Reprodução RED: três coordenadas malformadas falharam, seguida de DEFLATE corrompido falhando. Corrigidos para PACKAGE_INVALID sem payload; GREEN ampliado82 testes, gate focado final44 testes do conector. Ruff completo PASS e git diff --check PASS. Regressão integrada adicional começou antes da correção e continua em execução; não representa gate final da branch. Nenhum frontend/E2E aprovado ainda.

Regressão integrada adicional executada na T3:890 testes, zero skips, uma depreciação herdada,663.64 segundos. Iniciada antes do achado da revisão; os cinco novos casos de sanitização foram verificados separadamente em GREEN. Não representa gate final das tarefas posteriores.

## T4 — Recebimento privado e preview persistente

RED real em PostgreSQL:seis cenários pela ausência do serviço. Armazenamento recebeu RED2, GREEN2; colisão de criação recebeu RED1 antes de correção. Primeiro GREEN de preview/storage:9 testes. Rollback posterior de sessão removendo arquivo já commitado recebeu RED e foi corrigido; falha na auditoria reverte receipt/linhas e remove seu bruto não commitado.

RawStore usa chave Fernet dedicada, referências UUID e criação exclusiva; sem plaintext fallback nem download público. Settings:feature desligada por padrão, ativação exige chave válida e diretório absoluto fora de assets/static/public/dist e sem links; chave separada da outbox. Logo oficial resolvida por configuração operacional ou asset existente do projeto. Chave e caminhos privados não entram no DTO/auditoria.

PreviewOrchestrator possui fases técnicas explícitas; serviços não fazem commit. Parsing limitado após autorização inicial e fora de locks; receipt/VALIDATING auditado e commitado antes da validação final. Outra conexão comprovou esse estado persistente. Resultado só retorna após commit da unidade de trabalho. Processo interrompido conserva VALIDATING sem poder confirmar; expiração/limpeza técnica é integrada na T6. Se validação falhar, rollback das linhas; FAILED em transação separada quando auditoria funciona, último VALIDATING quando auditoria continua indisponível; nunca falso sucesso.

Schemas fechados em duas passagens; referências adiante resolvidas, referências de outro contrato e unidades não atribuídas rejeitadas sem revelar IDs. Unit id/version congelados no preview; chave de estoque produto/unidade resolvida/data, sem código artificial. Duplicatas idênticas são SKIPPED com warning, conteúdo divergente rejeita todo o preview; nenhum Record/detail é criado. Fórmulas não persistem como payload/issue bruto. Bruto cifrado expira independentemente do preview; normalizados/proveniência preservados.

RED adicional:expiração durante validação produzia READY e falha técnica tinha outcome SUCCESS. Corrigidos; estado EXPIRED e outcome FAILURE comprovados. GREEN integrado focado T1–T4/config/audit:177 testes, zero skips; rodada final de preview/storage/isolation:20 testes, zero skips. Ruff backend completo PASS, git diff --check PASS. Nenhuma nova migration na T4 (0011/0012 já cobrem persistência). Nenhum endpoint/frontend concluído nesta tarefa.

## T5 — Confirmação atômica e idempotência

RED inicial válido:13 cenários após corrigir registro de fixtures transitivas. GREEN inicial13; ampliado19. Cobertos cinco datasets não financeiros, referências tipadas, proveniência, duplicata idêntica sem inserção, conflito após preview sem sobrescrita, replay condicionado à chave/versão/contexto/sessão e permissões atuais, escopo/versionamento de unidade e módulo revogado.

Concorrência real em PostgreSQL:duas confirmações da mesma importação produzem um commit/evento; imports distintos com chave de negócio conflitante produzem um commit e409; expiração e revogação de sessão/contexto/contrato/membership/permissão/módulo durante espera de lock são revalidadas. Erro de fixture SQL corrigido (TenantRolePermission tem PK composta, sem coluna id); rodada intermediária25 PASS/1 FAIL não foi gate aprovado.

Revisão independente /root/review_datahub_t5 apontou órfão de bruto ao fechar sessão/nested transaction, confirmação com feature desligada, conflito físico com unidade fora do escopo e ausência de FAILED técnico pós-rollback. Todos reproduzidos RED e corrigidos:receipt exige transação raiz explícita; cleanup em rollback/close sem apagar arquivo commitado; feature desabilitada503; colisão UNIQUE409 neutro; ConfirmationOrchestrator possui transação independente para FAILED quando auditoria disponível, preservando READY se auditoria indisponível. Nenhum serviço faz commit internamente. Follow-up independente sem novos achados relevantes; testes reais executados pelo implementador.

GREEN final executado:64 testes, zero skips,124.78 segundos. Comando:uv run --frozen python -m pytest tests/test_datahub_confirmation.py tests/test_datahub_races.py tests/test_datahub_preview.py tests/test_audit_integrity.py -q. Ruff focado e git diff --check executados e aprovados. Nenhuma migration adicional. Uma depreciação herdada Starlette/httpx.

## T6 — Histórico, exportação e retenção

RED8 observado por interfaces ausentes. Primeira implementação7 GREEN/1 RED: expiração técnica requer actor_id na auditoria Foundation; corrigida preservando ator do lifecycle original e motivo explícito de expiração automática, sem alegar comando humano. Autofix Ruff removeu imports usados como fixtures; corrigido para aliases explícitos, não é falha de produto nem PASS.

GREEN final53 testes, zero skips,128.77 segundos:queries/retention/confirmation/preview. Histórico paginado oculta import misto integralmente se houver dataset/unidade fora das permissões atuais, incluindo contagens/rows/issues. Exportação usa detalhes relacionais tipados e código atual da unidade; excesso413, sem truncamento. Strings literais, logo oficial e LEIA-ME preservados.

Remoção de bruto cifrado independente de preview comprovada com confirmação posterior. Retry de falha/OSError e órfão UUID.enc comprovados; nenhuma evidência normalizada removida. Cleanup local runtime-only, sem scheduler/infra externos; diretórios grandes exigem acompanhamento do scan limitado. Expiração auditada e nenhum hard delete. Runbook operacional incluído. Ruff backend completo e diff-check executados, aprovados.

## T7 — APIs e transporte seguro

RED backend6 FAIL/2 PASS esperado por rotas ausentes; frontend2 FAIL/12 PASS por multipart/blob. GREEN inicial API8; ampliado43 testes de API/policy/query/retention, zero skips,77.19 segundos. A/A2/B com IDs estrangeiros reais, nova sessão HTTP lê histórico autorizado mas não confirma preview anterior; CSRF/Origin, DTO extra rejeitado sem eco, replay, limite upload, feature e papel interno sem bypass.

GREEN frontend14 testes do cliente seguro. Uma comparação inicial Blob instanceof falhou por realms Node/jsdom; teste corrigido para identidade Blob e conteúdo real, sem alterar comportamento de produto. Transporte FormData mantém credentials/context/CSRF sem boundary manual; blob revalida geração após leitura e descarta resposta tardia. Object URLs revogados após download.

ImportIdentity possui UoW curto que encerra locks antes da Preview/ConfirmationOrchestrator; gates Foundation e autenticação reutilizados. Envelope limitado antes de parsing multipart, somente um XLSX, arquivo igualmente limitado. python-multipart promovido a dependência direta; nenhum pacote existente atualizado. Controllers sem regras de negócio. Ruff completo, oxlint, TypeScript/Vite build e git diff --check executados/aprovados. Nenhum frontend workflow/E2E concluído ainda.

## T8 — Workflow autenticado e portal membership

RED real:workflow ausente e dois fluxos Admin/member sem menu; Support já sem menu. Implementação modular frontend/src/datahub com hook, template/upload, preview, Issues por linha/campo, paginação, confirmação, histórico e exportação. Portal membership limitado ao Data Hub autorizado pelo servidor; sem ferramentas de operadores internos ou selector de perfis demo. Cabeçalho contratual sticky preservado.

GREEN focado48 testes frontend, zero skips:ExcelPage/DataHub/AuthenticatedApp/ApiClient. Cobertos confirmação com payload fechado, sucesso somente COMMITTED, warnings/SKIP, erro por campo,403/409/503, preview expirado, exportação com confirmação, object URL liberado, dados/requests descartados no unmount, permissões atuais e navegação por papel. Nenhum storage Data Hub; somente id opaco contextual/preferência de tema existentes.

Falha intermediária de matcher textual corrigida no teste. Teste herdado de validação tardia de contexto falhou em rodada paralela; isolado passou (diagnóstico com testes filtrados não é gate), depois suíte relevante inteira48 passou sem mudança na Foundation. Registrar intermitência e acompanhar gate final. Dados de preview removidos após negação401/403/404; conflito409 exige novo preview, sem retry automático.

Oxlint sem warnings, TypeScript/Vite build e git diff --check executados/aprovados. Inspeção Chrome/light/dark/mobile/teclado e gate completo ainda são T9, não declarados PASS nesta tarefa.

## Ainda não executado/concluído

T9:E2E, revisão final, gate completo e cleanup final. Financeiro indisponível; nenhum módulo operacional simulado.
