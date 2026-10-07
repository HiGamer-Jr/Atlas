# HiAtlas Data Hub — Excel v1: evidência de execução

STATUS: VALIDATED — gate local Excel v1 concluído; sem implantação ou promoção da Demo.

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

Schemas fechados em duas passagens; referências adiante resolvidas, referências de outro contrato e unidades não atribuídas rejeitadas sem revelar IDs. Unit id/version congelados no preview; chave de estoque produto/unidade resolvida/data, sem código artificial. Contra registros já persistidos, duplicatas idênticas são SKIPPED com warning e conteúdo divergente rejeita todo o preview; duplicidade dentro do mesmo arquivo foi corrigida na T9 para ERROR em todos os casos; nenhum Record/detail é criado. Fórmulas não persistem como payload/issue bruto. Bruto cifrado expira independentemente do preview; normalizados/proveniência preservados.

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

## T9 — Revisão independente e regressão final

Base T9:2c1b805. Revisões independentes backend e frontend realizadas por agentes somente leitura, sem dividir a implementação. Cinco achados P2 reproduzidos RED pelo implementador e corrigidos antes do gate:

| Achado | Correção | GREEN executado |
|---|---|---|
| Duplicata idêntica dentro do arquivo recebia SKIP, contrariando spec§12 | Toda business key repetida no mesmo arquivo gera ERROR; SKIP continua somente contra registro já persistido idêntico | test_identical_duplicate_inside_file_is_error |
| Prefixo permanente de arquivos vivos podia impedir reconciliação de órfãos posteriores | Cursor privado rotativo, nomes UUID.enc, gravação atômica e links recusados | test_cleanup_cursor_cannot_starve_later_orphan, PostgreSQL real/lote1 repetido |
| Exportação de comprador podia incluir demandas da outra modalidade e produzir planilha incompatível com seu template | Filtro de modalidade no SELECT antes do limite, sem mudar autorização | test_export_template_filters_modality_before_limit |
| Confirmação não mostrava escopo completo de todas as linhas | unit_scope calculado pelo servidor sobre todas as linhas autorizadas; DTO e diálogo explícitos | confirmação com duas unidades fora de qualquer inferência por paginação |
| Foco podia cair no BODY depois da confirmação | Heading do preview recebe foco após COMMITTED; diálogo Foundation preservado | commit returns keyboard focus to preview heading |

Uma edição parcial de correção produziu rodada intermediária53 PASS/3 FAIL: NÃO é gate. Correções completadas e regressão final focada56 backend PASS, zero skips,155.75s (queries/retention/preview/confirmation). Frontend focado30 PASS, zero skips; suíte completa301 PASS em18 arquivos, zero skips,20.72s. Oxlint sem warnings e TypeScript/Vite build executados PASS depois das correções.

E2E real executado com PostgreSQL18.6 descartável, FastAPI real, Vite/React real, Chrome headless e HTTPS local. Factory isolada scripts/datahub_browser_fixture.py exige configuração explícita, endpoint/database/marcador descartáveis e owner/runtime distintos; não importada pela aplicação normal, sem endpoint secreto. FakeEmailTransport; nenhum e-mail real. Somente dados sintéticos Aurora/Beta/UNIT-SYN e identidades example.test.

Fluxos executados: Admin com membership/capabilities tenant explícitos baixa modelo oficial Coordenação; cinco datasets preenchidos; preview mostra cinco linhas sem Records; confirmação grava cinco Records e um AuditEvent; foco retorna ao heading; replay mesma chave mantém um efeito; outra chave409; exportação real; arquivo idêntico inteiro gera cinco SKIP sem duplicar Records; conteúdo alterado e fórmula rejeitados; membership comum usa somente workspace autorizado; Support sem menu e API403; imports de A ocultos por IDs válidos em A2/B; duas abas com contextos independentes; revogação de permissão entre preview/confirmação nega e descarta dados; módulo revogado403; reload, logout e storage limitado a preferência de tema/id opaco do AccessContext.

Primeiro E2E RED por seletor ambíguo que correspondia ao resumo e à paginação, sem defeito de produto. Diagnóstico privado sanitizado; seletor restringido ao resumo; reexecução completa GREEN. Screenshots desktop claro/escuro, mobile390×844, preview, fórmula rejeitada, Support e permissão revogada inspecionados. Sem overflow externo no mobile; navegação Tab e header contextual sticky comprovados. Chrome somente: não alegar multibrowser nem conformidade WCAG completa.

Inspeção separada dos XLSX realmente baixado/exportado PASS: cinco datasets; imagens embutidas byte a byte iguais à logo oficial; LEIA-ME visível; _HIATLAS_META oculto; freezeA13; tabelas; ausência de células fórmula; exportação preserva código000123. T3 já inspecionou os oito modelos sintéticos/35 abas visíveis com as limitações de renderer documentadas acima. Captura preservada em visual/templates-synthetic-inspection.png; Financeiro nela é somente fixture de formatação isolada, indisponível pela API.

Primeira rodada backend completa:971 PASS/1 ERROR, zero skips,1055.39s; NÃO é PASS. Erro de setup UniqueViolation de admin@example.test em test_reset_valid_revokes_sessions_and_contexts: o E2E deixou fixtures sintéticas e o harness pytest limpa somente no teardown. Corrigido apenas teardown do harness E2E para limpar o banco próprio após encerrar API/Vite; sem alteração da Foundation ou dos asserts. Uma tentativa de iniciar pytest no mesmo processo que carregou/zerou o ambiente privado foi recusada antes de coletar testes: PUBLIC_ORIGIN ficou vazio após SetEnvironmentVariable(null). Não é PASS. Teardown corrigido para remover variáveis pelo provider Env do PowerShell; sintaxe e remoção verificadas. Reexecução em processo limpo e banco vazio:972 testes PASS, zero skips, uma depreciação herdada,1052.16s. Comando final:uv run --frozen python -m pytest -q --tb=short --basetemp=<raiz própria descartável>/pytest-final; owner/runtime/recovery separados. Inclui migrations full-chain/incremental, downgrade/upgrade, grants físicos, isolamento e concorrência.

Inspeção final encontrou lacuna adicional de UX: preview mostrava apenas versão sem identificar nominalmente o template real do upload. Caso em que modelo selecionado para download difere do template recebido foi reproduzido RED1/13 PASS; correção mínima usa label do catálogo server-side correspondente ao template_id do preview, independentemente do seletor. Preview e confirmação agora exibem o modelo identificado; política de duplicidade no texto também distingue arquivo de registros existentes. Sem mudança de backend ou autorização.

GREEN final frontend:302 testes em18 arquivos, zero skips,18.21s; npm.cmd test. Oxlint sem warnings; TypeScript/Vite build PASS na árvore final. Ruff completo app/tests/alembic/factory E2E PASS. E2E completo reexecutado na interface final PASS, incluindo identificação efetiva de Coordenação, Financeiro indisponível e confirmação contextual. Harness encerra apenas API/Vite próprios e limpa todas as fixtures do banco atestado; verificação independente final comprovou users/imports/records/audit zerados, PostgreSQL18.6 e auditoria runtime imutável.

Capturas finais revisadas em visual/:desktop-light-preview, desktop-dark, mobile-light, mobile-dark, confirm-contextual, invalid-formula, permission-revoked, support-denied e templates-synthetic-inspection. Sem arquivo de banco, credencial, token ou chave nesses artefatos.

Cleanup executado e verificado: PostgreSQL próprio parado; raiz descartável removida com clusters/banco/brutos/TLS/chaves/credenciais/basetemp final. Artefatos pytest próprios53–56 removidos após checagem de caminho/nome/data; links removidos isoladamente. Portas temporárias API/Vite/PostgreSQL sem listener. Workspace técnico deste plano é descartado após o commit local, preservando capturas/decisões neste relatório e o target Node compartilhado. SHA final e árvore limpa informados na entrega. Sem push/merge/deploy e Demo intocada.

## Arquitetura e schema entregues

Connector → parsing/validação → preview persistente → confirmação explícita → registros próprios tipados/proveniência/auditoria. Adaptadores de domínio são futura fronteira; não há gravação em módulos operacionais inexistentes. Import, arquivo recebido, Row, Issue e Record são entidades distintas. Detalhes relacionais têm FKs compostas tenant/contract; payload de preview é normalizado por schema fechado, não instrução livre.

Lifecycle: RECEIVED/VALIDATING/READY_FOR_CONFIRMATION; REJECTED para erro de dados; EXPIRED para prazo; FAILED para falha técnica; COMMITTED somente após commit real. Services não fazem commit; orchestrators controlam unidades de trabalho. UNIQUE físico e locks na ordem Foundation protegem confirmação/replay. Auditoria falhando impede a mutação.

Todos os datasets abaixo são versão1. Campos obrigatórios salvo categoria de Produtos. Códigos textuais normalizados ASCII maiúsculo, até64 caracteres, zeros iniciais preservados. Datas ISO; decimais finitos com até quatro casas e magnitude menor que10^15, persistidos em NUMERIC(20,4), sem arredondamento silencioso; booleanos SIM/NAO. Nome/descrição até200; categoria até120.

| Dataset / aba | Campos | Business key no contrato |
|---|---|---|
| PRODUCTS / Produtos | codigo, descricao, unidade_medida, categoria opcional, ativo | codigo |
| PARTNERS / Parceiros | codigo, nome, tipo, pais_iso, ativo | codigo |
| DEMANDS / Demandas | codigo, produto_codigo, unidade_codigo, quantidade positiva, data_necessidade, modalidade, prioridade | codigo |
| STOCK_POSITIONS / Estoque | produto_codigo, unidade_codigo, quantidade_disponivel não negativa, data_referencia | produto e unidade resolvidos + data_referencia |
| COMEX_REFERENCES / COMEX | codigo, parceiro_codigo, moeda, incoterm, data_prevista, status | codigo |
| FINANCIAL_FORECASTS / Financeiro | schema fechado reservado; NÃO exposto/importável/exportável na V1 | bloqueado |

Enums: unidade_medida UN/KG/TON/L/M/M2/M3/CX/PAL; parceiro FORNECEDOR/CLIENTE/TRANSPORTADOR e país ISO fechado; modalidade NACIONAL/INTERNACIONAL; prioridade BAIXA/NORMAL/ALTA/URGENTE; moeda BRL/USD/EUR/GBP/CNY; Incoterms EXW/FCA/CPT/CIP/DAP/DPU/DDP/FAS/FOB/CFR/CIF; referência COMEX PLANEJADO/EM_ANDAMENTO/CONCLUIDO/CANCELADO. Referências COMEX são informacionais, não Processo/Proforma/Container/Booking/Embarque operacionais.

| Template versionado v1 | Composição padrão, filtrada pelas permissões/módulos/unidades atuais |
|---|---|
| Coordenação | Produtos, Parceiros, Demandas, Estoque, COMEX |
| Supervisão | Produtos, Demandas, Estoque |
| Comprador Nacional | Produtos, Parceiros, Demandas NACIONAL |
| Comprador Internacional | Produtos, Parceiros, Demandas INTERNACIONAL, COMEX |
| Financeiro | indisponível nesta V1 |
| Diretoria | cinco datasets não financeiros, download/exportação; não importável |
| Loja | Produtos, Demandas, Estoque |
| Centro de Distribuição | Produtos, Estoque |

Template≠Dataset≠Perfil. Esses oito templates nunca são TenantRoles nem concedem capability. Geral read/import/export/download e capabilities por dataset vêm do backend/membership vigente. PLATFORM_ADMIN sozinho não recebe direitos de cliente; PLATFORM_SUPPORT e contextos derivados não utilizam o conector. Exportação do template de comprador filtra modalidade; isso não amplia nem substitui RBAC.

Planilhas: logo oficial existente, título/slogan, empresa/contrato/perfil/unidade/data/versão; header12/dados13/freezeA13; tabela/filtro; validação de enums; números/data consistentes; LEIA-ME; _HIATLAS_META. Sem macro, segredo ou avaliação de fórmula. Arquivo bruto cifrado temporário; normalizados/digest/proveniência persistentes. Proveniência relaciona import, arquivo sanitizado, aba/linha, template/schema, ator e UTC.

## Commits e arquivos

Foundation aprovada:641e57502644935ff1c4ca9e06f54b009bb7adc4. Spec/plano:180989d. T1:e51e6d5; T2:afb681a; T3:0ff6f3e; T4:0eb95c4; T5:5b9cd2d; T6:e12f300; T7:063bd80; T8:2c1b805. T9 é o commit que contém este relatório final, identificável por git log deste arquivo; SHA final informado na entrega, evitando hash autorreferencial.

Arquivos em relação à Foundation (mais harness e capturas T9):

- backend/alembic/versions/0011_datahub_excel.py
- backend/alembic/versions/0012_datahub_scope.py
- backend/app/api/router.py
- backend/app/audit/schemas.py
- backend/app/core/config.py
- backend/app/datahub/__init__.py
- backend/app/datahub/catalog.py
- backend/app/datahub/cleanup.py
- backend/app/datahub/confirmation.py
- backend/app/datahub/connectors/__init__.py
- backend/app/datahub/connectors/base.py
- backend/app/datahub/connectors/excel.py
- backend/app/datahub/dependencies.py
- backend/app/datahub/duplicates.py
- backend/app/datahub/models.py
- backend/app/datahub/normalization.py
- backend/app/datahub/policy.py
- backend/app/datahub/preview.py
- backend/app/datahub/queries.py
- backend/app/datahub/raw_store.py
- backend/app/datahub/repositories.py
- backend/app/datahub/retention.py
- backend/app/datahub/routes.py
- backend/app/datahub/schemas.py
- backend/app/datahub/services.py
- backend/app/datahub/types.py
- backend/app/datahub/validation.py
- backend/app/db/models.py
- backend/app/main.py
- backend/app/organization/modules.py
- backend/app/platform/capabilities.py
- backend/app/platform/policy.py
- backend/app/tenancy/models.py
- backend/pyproject.toml
- backend/tests/conftest.py
- backend/tests/test_contract_modules.py
- backend/tests/test_datahub_api.py
- backend/tests/test_datahub_catalog.py
- backend/tests/test_datahub_confirmation.py
- backend/tests/test_datahub_excel.py
- backend/tests/test_datahub_policy.py
- backend/tests/test_datahub_preview.py
- backend/tests/test_datahub_queries.py
- backend/tests/test_datahub_races.py
- backend/tests/test_datahub_retention.py
- backend/tests/test_datahub_schema.py
- backend/tests/test_support_sessions.py
- backend/uv.lock
- docs/operations/hiatlas-datahub-excel-v1.md
- docs/superpowers/plans/2026-10-06-hiatlas-datahub-excel-v1.md
- docs/superpowers/specs/2026-10-06-hiatlas-datahub-excel-v1-design.md
- docs/superpowers/validation/hiatlas-datahub/excel-v1.md
- frontend/src/App.tsx
- frontend/src/api/client.test.ts
- frontend/src/api/client.ts
- frontend/src/datahub/ConfirmImportDialog.tsx
- frontend/src/datahub/DataHub.css
- frontend/src/datahub/DataHub.test.tsx
- frontend/src/datahub/ExcelPage.test.tsx
- frontend/src/datahub/ExcelPage.tsx
- frontend/src/datahub/ExportDialog.tsx
- frontend/src/datahub/ImportHistory.tsx
- frontend/src/datahub/ImportPreview.tsx
- frontend/src/datahub/TemplatePicker.tsx
- frontend/src/datahub/TenantWorkspace.tsx
- frontend/src/datahub/UploadForm.tsx
- frontend/src/datahub/api.ts
- frontend/src/datahub/labels.ts
- frontend/src/datahub/types.ts
- frontend/src/datahub/useDataHub.ts
- frontend/src/platform/ContractShell.tsx
- frontend/src/support/Workspace.tsx
- scripts/datahub_browser_fixture.py
- scripts/datahub_browser_checks.ps1
- frontend/e2e/datahub.mjs
- docs/superpowers/validation/hiatlas-datahub/visual/*.png

## Limitações e decisões operacionais

Financeiro bloqueado; outros módulos operacionais não simulados. CSV/ERP/API/mapeamento externo/adaptadores de domínio posteriores. Importação integral limitada e síncrona; excesso rejeitado sem truncamento. Nenhum overwrite/atualização de registros existentes nesta V1. Histórico misto fica integralmente oculto quando qualquer dataset/unidade perde autorização.

Reutilização do lifecycle lock global da Foundation serializa confirmações; adequado ao volume inicial, limita throughput. Retenção limita trabalho de stat/consulta/remoção por categoria, mas enumera nomes do diretório para avançar o cursor; acompanhar diretórios grandes. Bruto requer diretório privado/ACL Windows e chave operacional protegida, feature desabilitada por padrão. Não demonstrada durabilidade produção pelo cluster otimizado de testes. Deprecated Starlette/httpx herdado; nenhuma atualização automática de dependências.

Sem deploy/push/merge ou operação na Demo. Nenhum dado real utilizado. Harness E2E atual específico desta estação Windows/D:/Atlas, com Chrome/Playwright geridos pelo runtime; adaptar caminhos e provisionar PostgreSQL descartável antes de repetir em outra máquina.

## Decisões registradas durante a execução

Lista integral das decisões do ledger, na ordem em que foram tomadas; nenhum achado minor foi adiado:

1. PLATFORM_ADMIN não concede Data Hub por si só; exigir autorização tenant efetiva. Custo: operadores precisam vínculo/capabilities explícitos, conforme correção do usuário.
2. Ledger/briefs nativos Python/PowerShell por ausência de Bash no ambiente. Custo: comandos operacionais específicos Windows, sem agentes implementadores.
3. pytest via uv run --frozen python -m pytest por launcher Windows obsoleto. Custo: não usar executável pytest.exe; ambiente/versões travados preservados.
4. Substituir somente cluster próprio descartável após interrupção; fsync/full_page_writes/synchronous_commit desligados no novo cluster sintético. Custo: testes não comprovam durabilidade de produção; cluster anterior removido no cleanup final.
5. Decimais acima de15 dígitos significativos Excel serializados como texto explícito. Custo: exigem interpretação numérica consciente ao editar; precisão NUMERIC(20,4) preservada.
6. defusedxml incluído junto de openpyxl/Pillow para XML não confiável. Custo: dependência adicional travada, sem mudar arquitetura.
7. Identidade/versão da unidade congeladas nas Rows antes da ingestão. Custo: mudança/reuso do código exige novo preview; evita reatribuir proveniência.
8. Dependências Excel resolvidas no primeiro consumidor T3. Custo: T1 não instala biblioteca sem uso; estado final contém dependências travadas.
9. Datasets unitários omitidos sem unidades ativas atribuídas. Custo: composição de template reduzida; não existe fallback ao contrato inteiro.
10. Migração incremental0012 amplia capability CHECK e congela escopo;0011 já commitada não foi reescrita. Custo: duas migrations testadas em vez de alterar história.
11. Import exige read por dataset além de import. Custo: roles precisam ambas; preview/duplicidade não autorizam leitura implicitamente.
12. Stack backend aprovada openpyxl/Pillow/defusedxml prevalece sobre autoria de artefato standalone; artifact-tool só para inspeção. Custo: limitações visuais do renderer documentadas, sem recálculo dos uploads.
13. Comparação canônica usa unidade resolvida; exportação mostra código atual e proveniência conserva código original. Custo: divergência exige nova revisão em vez de overwrite/rebind.
14. Preview tem UoW em fases explícitas para VALIDATING persistente, parsing fora de locks e revalidação final. Refinamento registrado: orchestrator controla transações; services nunca commitam a transação do caller. Custo: múltiplos commits técnicos de lifecycle; confirmação/dados/auditoria continuam em um único commit.
15. Import misto integralmente oculto se qualquer dataset/unidade perder autorização. Custo: inclusive contagens/histórico deixam de aparecer; novo contexto autorizado lê histórico, mas não confirma preview vinculado a outro contexto.
