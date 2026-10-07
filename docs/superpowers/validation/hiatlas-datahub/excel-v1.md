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

## Ainda não executado/concluído

T3–T9; geração XLSX, preview/commit, histórico/exportação, retenção, frontend, E2E, inspeção de planilhas, gate final e cleanup final. Nenhum destes marcado PASS. Financeiro não será operacional nesta V1; adaptadores CSV/API/ERP/domínio permanecem futuros.
