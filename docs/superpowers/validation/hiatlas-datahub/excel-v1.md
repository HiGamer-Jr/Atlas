# HiAtlas Data Hub — Excel v1: evidência de execução

STATUS: EM IMPLEMENTAÇÃO; não é encerramento nem aprovação operacional.

Branch: feat/hiatlas-datahub-excel-v1. Base aprovada Foundation v1: 641e57502644935ff1c4ca9e06f54b009bb7adc4. HEAD documental anterior à execução: 180989d53b1f1bdcea8f12047e96ba9290a8c112.

Execução nativa T1 → T9, sem agentes implementadores. Demo intocada; sem deploy/push/merge. Somente fixtures sintéticas. Correção do usuário incorporada: papel PLATFORM_ADMIN não concede capabilities/escopo de dados Data Hub por si só; PLATFORM_SUPPORT sem importação e Financeiro bloqueado.

## T1 — Catálogo, schemas e persistência

RED observado: nove falhas do catálogo ausente; dezessete falhas de tabelas/grants/constraints ausentes em PostgreSQL. Primeiro GREEN focado:49 testes. Números extremos receberam RED de dois casos InvalidOperation; corrigido para validação tipada sem truncamento.

Revisão independente backend /root/review_datahub_t1: achado P2 de zero negativo gerando canonização distinta. Reproduzido RED, corrigido e GREEN; zero/zero negativo agora têm representação 0.0000. Revisor também apontou cobertura física insuficiente; ampliados testes de Record/Row/dataset, Issue/Import, detalhe discriminado, IDs válidos estrangeiros de produto/parceiro/unidade, unicidade A/A2/B e estoque, grants das seis tabelas de detalhes e upgrade incremental com runtime inseguro.

GREEN focado final executado:83 testes, zero skips. Comando: uv run --frozen python -m pytest tests/test_datahub_catalog.py tests/test_datahub_schema.py tests/test_migration_lifecycle.py tests/test_runtime_privileges.py -q. Ruff completo executado: uv run --frozen python -m ruff check app tests alembic → PASS.

PostgreSQL18.6 real descartável, owner/runtime/recovery separados; runtime não owner/superuser. Upgrade full-chain e downgrade/upgrade executados pelos testes de migração; upgrade0010→0011 com owner/superuser/missing runtime recusado antes de DDL. Sem DELETE/TRUNCATE nas onze tabelas novas; auditoria continua append-only.

Migração0011_datahub_excel após0010; DDL congelado, não depende de modelos mutáveis no momento do upgrade. Entidades principais: DataHubImport, DataHubImportFile, DataHubImportRow, DataHubImportIssue, DataHubRecord. Seis detalhes relacionais tipados; row payload intermediário é objeto normalizado por schemas fechados, nunca instrução arbitrária. Ainda não há endpoint Data Hub habilitado na T1.

Uma rodada completa inicial foi interrompida por falta da identidade recovery exigida pela Foundation; NÃO é PASS. A infraestrutura foi corrigida e a reexecução completa passou:827 testes, zero skips, uma depreciação herdada; uv run --frozen python -m pytest -q, 800 segundos. Cluster descartável usa fsync/full_page_writes/synchronous_commit desativados somente para desempenho de testes sintéticos; não prova durabilidade em produção. O cluster anterior próprio foi parado, preservado temporariamente para cleanup.

Warning herdado Starlette/httpx: depreciação conhecida, sem supressão nem atualização de arquitetura. Launcher Windows pytest.exe apresentou trampoline obsoleto; execução via uv run --frozen python -m pytest usa o mesmo ambiente travado Python3.13.15.

## Ainda não executado/concluído

T2–T9; geração XLSX, preview/commit, histórico/exportação, retenção, frontend, E2E, inspeção de planilhas, gate final e cleanup final. Nenhum destes marcado PASS. Financeiro não será operacional nesta V1; adaptadores CSV/API/ERP/domínio permanecem futuros.
