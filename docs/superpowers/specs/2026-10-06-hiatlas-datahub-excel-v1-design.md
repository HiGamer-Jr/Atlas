# HiAtlas Data Hub — Excel v1: proposta de desenho

STATUS: PROPOSTA PARA REVISÃO; nenhuma implementação de produto iniciada.

## Verificação inicial e decisões necessárias

Projeto exclusivo D:/Atlas. git status --short sem saída; branch inicial feat/hiatlas-obras-phase-2-schedule; HEAD621668d15d7151f0e1321ae68daadef64bd43d0d. Feature criada: feat/hiatlas-datahub-excel-v1, mesmo HEAD. Nenhuma alteração local não relacionada.

A base inicial possuía login demonstrativo com profile selector e backend apenas /health, sem autorização real. O usuário escolheu a Foundation v1 como base; fast-forward aplicado somente na feature em D:/Atlas para641e57502644935ff1c4ca9e06f54b009bb7adc4, sem alteração de branch/worktree Demo. Não copiar ou reimplementar parcialmente a segurança do protótipo.

Destino escolhido pelo usuário: dados tipados persistentes do Data Hub, com integração futura por adaptadores de domínio. Não gravar ou simular serviços operacionais inexistentes. Os schemas abaixo são propostas concretas para revisão, não cadastros operacionais já entregues.

## Fronteira congelada

Não alterar release/hiatlas-demo-v1, sua worktree, /var/www/hiatlas-demo, banco hiatlas_demo ou configuração VPS/Nginx/systemd. Nenhum deploy, promoção ou merge na release Demo. Não executar ferramentas contra sua infraestrutura. Somente dados sintéticos nos testes e artefatos; nenhum cliente real.

## Abordagens

1. Recomendada: núcleo de ingestão/exportação tipado e persistente com conector Excel e adaptadores de destino. Reutiliza identidade/contexto/auditoria da Foundation, suporta a evolução CSV/API/ERP sem antecipar conectores reais.
2. Conector direto para cada domínio operacional: útil quando serviços já existem, mas nesta base faltam esses destinos e a autorização. Exigiria escopo funcional adicional.
3. Leitor XLSX acoplado ao protótipo: não atende autorização, isolamento ou histórico real; descartado.

## Arquitetura proposta

- datahub/catalog: registry fechado de datasets, schemas versionados e templates por perfil. Perfil escolhe a composição padrão, nunca concede autorização.
- datahub/connectors: interface de leitura/escrita de documento; Excel é o primeiro adaptador. Não implementar CSV/API/ERP agora.
- datahub/validation: tipos, enums, referências, duplicidade e escopo. Schema do servidor é autoridade; metadados da planilha são somente identificação.
- datahub/services: gerar modelo, criar preview, confirmar importação, consultar histórico e exportar. Reutilizar Principal, AuthSession, AccessContext, capabilities, module gating e auditoria atômica.
- datahub/repositories: ImportBatch, ImportRow/Issue e registros tipados por dataset; nenhuma tabela operacional escolhida pelo navegador, SQL ou patch genérico.
- frontend/src/datahub: página Excel com catálogo autorizado, upload, preview paginado, erros/warnings, confirmação contextual, histórico e exportação. Usar shell autenticado e cancelamento de respostas tardias.

## Schemas candidatos v1

Escopo base de cada registro: tenant_id/contract_id vindos do servidor; unidade por código validado dentro do contrato, chave externa estável e proveniência. Dataset e versão são fechados no registry; não aceitar JSON arbitrário de negócio.

|Dataset|Campos de entrada propostos|Chave contextual|
|---|---|---|
|Produtos|codigo, descricao, unidade_medida, categoria, ativo|codigo|
|Parceiros|codigo, nome, tipo(FORNECEDOR/CLIENTE/TRANSPORTADOR), pais_iso, ativo|codigo|
|Demandas de compra|codigo, produto_codigo, unidade_codigo, quantidade, data_necessidade, modalidade(NACIONAL/INTERNACIONAL), prioridade|codigo|
|Posições de estoque|codigo, produto_codigo, unidade_codigo, quantidade_disponivel, data_referencia|codigo|
|Referências COMEX|codigo, parceiro_codigo, moeda, incoterm, data_prevista, status|codigo|
|Previsões financeiras|codigo, referencia_externa, unidade_codigo, moeda, valor, vencimento, natureza(ENTRADA/SAIDA)|codigo|

Datas ISO date, decimal exato para valores/quantidades, boolean estrito e textos limitados. Referências precisam existir no contrato e respeitar escopo vigente. Não executar compra, movimento de estoque, pagamento ou processo COMEX; esses registros são entradas do Data Hub até existir adaptador de domínio real.

Dados financeiros são classificados sensíveis. A implementação deve especificar e testar sua política junto ao catálogo existente; não ativar Financeiro operacional ou conceder acesso a Admin/Suporte por gerar um template. Dataset sem política/módulo/capability suficientes permanece indisponível, explicitamente. Nenhum bypass pelo nome Financeiro.

## Composição padrão dos oito templates

|Template|Datasets candidatos, sujeitos a autorização e disponibilidade|
|---|---|
|Coordenação|Produtos, Parceiros, Demandas, Estoque, COMEX|
|Supervisão|Produtos, Demandas, Estoque|
|Comprador Nacional|Produtos, Parceiros, Demandas nacionais|
|Comprador Internacional|Produtos, Parceiros, Demandas internacionais, COMEX|
|Financeiro|Previsões financeiras e referências permitidas|
|Diretoria|Projeções/exportações autorizadas; importação não concedida pelo perfil|
|Loja|Produtos, Demandas e Estoque no escopo da unidade|
|Centro de Distribuição|Produtos, Estoque e referências logísticas permitidas|

Catálogo fecha esses templates sem criar TenantRoles ou permissões automaticamente. Cada aba, campo e operação passa pela política vigente do backend. Composição sem dataset autorizado deve explicar a indisponibilidade, nunca gerar dados fictícios ou revelar registros sensíveis.

## Documento Excel oficial

Reutilizar PNG oficial existente, preferindo variante HiAtlas para fundo claro. Logo no canto superior esquerdo; título HiAtlas — Supply Chain Intelligence e slogan Um novo horizonte para o seu negócio. Cabeçalho com empresa, contrato, perfil, unidade/escopo, geração UTC e versão.

Posição padronizada: cabeçalhos de dados na linha12, primeira linha na13; freeze panes A13, tabela Excel com filtros, formatos de data/decimal uniformes, validações de enums. Modelos vazios não contêm dados de cliente; exemplos separados são sintéticos e explicitamente identificados.

Aba oculta _HIATLAS_META identifica template_id, template_version, schema_version, dataset/abas/colunas e geração; nenhum token ou credencial. Contexto declarado no arquivo nunca autoriza importação. Manifest incompatível/alterado é rejeitado, mas o registro no servidor continua sendo a autoridade. Esquema enum auxiliar oculto, sem macros, links externos ou recursos de terceiros.

## Upload, preview e confirmação

1. Upload XLSX autorizado; limites configuráveis de arquivo, ZIP expandido, quantidade de entradas, abas, linhas/células e texto. Rejeitar XLSM/VBA, links externos, DDE/formulas executáveis, planilha sem manifesto oficial ou schema não reconhecido. Não confiar somente na extensão/MIME.
2. Parsing estrito; erros por aba/linha/coluna e warnings com código estável, sem stack/SQL/conteúdo sensível em logs. Preview paginado persistente, sem alteração de registros finais.
3. Preview vinculado a operador/AuthSession/contexto/tenant/contrato, digest do conteúdo/schema e validade configurável; payload validado mantido no servidor. Preview não é autorização irrevogável.
4. Confirmação explícita envia import_id, versão esperada e chave de idempotência, sem before/after ou registros arbitrários fornecidos pelo browser. Revalidar estado, permissões/módulos/escopo e duplicidade após locks.
5. Transação única: registros tipados + proveniência + resultado + AuditEvent. Falha de auditoria ou destino reverte a operação. Não mostrar sucesso antes do commit.

Cada linha aceita referencia import_id, nome sanitizado do arquivo, aba, linha original, template/versão, ator real e horário UTC. Arquivo bruto não deve ficar público ou ser logado; retenção deve ser limitada/configurável e documentada.

## Duplicidade e concorrência

- Chaves contextualizadas por tenant/contrato/dataset. Duplicatas no mesmo arquivo são erros.
- Registro idêntico já importado gera warning/no-op explícito; chave existente com conteúdo diferente gera erro de conflito. Sem sobrescrita silenciosa ou upsert genérico.
- Novo arquivo semanticamente idêntico não cria novos registros finais. Repetir confirmação/chave de idempotência retorna o resultado existente; duas confirmações concorrentes produzem um único efeito auditado.
- Alteração entre preview e commit exige novo preview ou conflito409. Preview expirado, contexto revogado ou sessão diferente não podem executar.

## Exportação, histórico e UX

Exportar somente projeções paginadas/limitadas autorizadas do Data Hub, usando o mesmo gerador oficial e proveniência pertinente. Tratar strings iniciadas por indicadores de fórmula como texto literal; não avaliar fórmulas. Seleções/ids estrangeiros retornam404/neutro.

Histórico contextual paginado e sanitizado; sem arquivo bruto, credenciais ou dados de outro contrato. UI apresenta loading/erro/retry/empty, invalidade, warnings/erros por campo e linha, resumo inseridos/ignorados/rejeitados e confirmação com empresa/contrato/escopo sempre visíveis. Tema claro/escuro,390×844, teclado, foco e labels. Não persistir dados, e-mails, permissions ou payload de importação em localStorage/sessionStorage; somente id opaco de contexto conforme Foundation.

## Provas previstas

Backend: geração/layout/logo/meta, schemas/enums, parsing/limites/formulas/macros, capabilities/módulos/sensibilidade, preview sem mutação, confirmação obrigatória, duplicidade/idempotência concorrente, revogação durante lock, A/A2/B, proveniência, exportação segura e rollback audit.
Frontend: menu autenticado, downloads/upload, preview/erros/warnings, confirmação, histórico/exportação,403/409/expiração/abort/stale responses, teclado/temas/mobile; nenhuma autorização por seletor demo.
PostgreSQL descartável: migrations/grants/constraints físicas e concorrência. E2E FastAPI/React/navegador reais com dados sintéticos, nunca Demo publicada. Renderizar e inspecionar planilhas geradas usando skill de spreadsheets durante implementação.
Quality gate: backend pytest/Ruff, frontend Vitest/oxlint/TypeScript/Vite, git diff --check, sem declarar PASS não executado. Relatório de arquitetura, arquivos/schema/testes/limitações/status final. Sem deploy ou promoção automática.

## Próximo passo

Base Foundation v1 e destino Data Hub persistente confirmados pelo usuário. Revisar os schemas e esta proposta antes do plano de implementação e código. Nenhuma autorização anterior das Fases1–11 equivale a aprovar a nova semântica de datasets ou gravar em domínios não entregues.
