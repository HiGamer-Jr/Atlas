# HiAtlas Data Hub — Excel v1: proposta de desenho revisada

STATUS: SPEC E PLANO APROVADOS PELO USUÁRIO EM 2026-10-06. Execução nativa sequencial autorizada; T1–T5 validadas; execução das próximas tarefas em andamento. Sem autorização implícita de Data Hub pelo papel PLATFORM_ADMIN.

## 1. Base e isolamento aprovados

Projeto exclusivo: D:/Atlas. Branch: feat/hiatlas-datahub-excel-v1. Base de desenvolvimento: Foundation v1, commit641e57502644935ff1c4ca9e06f54b009bb7adc4.

A verificação inicial encontrou árvore limpa no checkout anterior. O usuário aprovou a adoção da Foundation; o fast-forward ocorreu somente na feature de desenvolvimento. A aprovação da base e do isolamento não substitui a revisão desta spec.

Não alterar release/hiatlas-demo-v1, D:/Atlas/.worktrees/hiatlas-demo-v1, /var/www/hiatlas-demo, banco hiatlas_demo ou configuração VPS/Nginx/systemd. Nenhum deploy, promoção ou merge na release Demo. Somente dados sintéticos nos testes e artefatos, sem dados de clientes reais.

Destino aprovado: registros tipados e persistentes do Data Hub. Não gravar nem simular serviços operacionais inexistentes.

## 2. Fluxo e responsabilidades

Excel → Connector → Parsing / Validation → Preview persistente → Confirmação explícita → Data Hub → Registros tipados + Proveniência + Auditoria.

No futuro: Data Hub → Domain Adapter → domínios operacionais reais de Produtos, Estoque, Compras, COMEX ou Financeiro.

O núcleo de ingestão/exportação é reutilizável. Excel é o primeiro conector; CSV, mapeamento de planilhas externas, APIs, ERP, Sankhya, Sienge e SAP ficam como evolução, sem conectores reais nesta V1.

- datahub/catalog: catálogo fechado de datasets, schemas versionados e templates.
- datahub/connectors: interface de leitura/escrita; adaptador Excel.
- datahub/validation: tipos, enums, referências, duplicidade, limites e escopo.
- datahub/services: modelo, preview, confirmação, histórico e exportação; reutiliza Principal, AuthSession, AccessContext, capabilities, módulos e auditoria da Foundation.
- datahub/repositories: entidades de importação separadas dos registros finais do Data Hub.
- frontend/src/datahub: Excel no shell autenticado, com preview paginado, issues, confirmação contextual, histórico, exportação e cancelamento de respostas tardias.

Nenhuma tabela operacional, SQL, coluna genérica ou patch arbitrário pode ser escolhido pelo navegador. Não haverá execução de compra, pagamento, processo COMEX ou movimentação de estoque.

## 3. Template, Dataset e Perfil são conceitos distintos

**Dataset** define uma estrutura de dados: código conhecido, schema/versionamento, campos, validação, business key e classificação de sensibilidade. É independente do formato Excel e pode ser reutilizado por futuros conectores.

**Template** é uma composição versionada de datasets, abas, colunas e instruções de apresentação. Não é papel, TenantRole, capability ou autorização.

**Perfil** indica uma composição padrão útil ao usuário. Nome de perfil não constitui regra de segurança; selecionar Financeiro, Coordenação ou outro template não eleva privilégios nem altera o TenantRole autenticado.

Cada operação, dataset, campo e unidade é autorizado pelo backend conforme principal, contexto, módulos contratados/ativos, capabilities e classificação. Metadados do arquivo apenas identificam o documento; nunca concedem acesso. A autorização é revalidada na geração, upload/preview, confirmação, histórico e exportação.

Oito templates constituem o catálogo inicial versionado. Não criar TenantRoles, associações ou permissões automaticamente. Dataset sem política ou autorização suficiente permanece indisponível, com explicação explícita. Nenhum conteúdo financeiro é liberado a Admin/Suporte por gerar ou selecionar um template.

## 4. Modelo de persistência conceitual

As cinco entidades abaixo são distintas. Preview, arquivo recebido e linha analisada não são registros finais de negócio nem DataHubRecords já importados.

### DataHubImport

Identidade e ciclo de vida da importação:

- id/import_id;
- tenant_id e contract_id obtidos pelo servidor;
- access_context_id e auth_session_id de origem;
- actor_user_id e identidade real do ator;
- connector_code, template_id, template_version e versões de schema;
- source_digest calculado pelo servidor;
- status, version e request/correlation id;
- created_at, validated_at, preview_expires_at, committed_at e finished_at quando aplicáveis;
- resultado estruturado: linhas analisadas, válidas, com erros/warnings, inseridas e ignoradas, além de código de resultado sanitizado;
- vínculo persistente da confirmação/idempotency key ao comando autorizado.

Datas em UTC. Expiração do preview não apaga a identidade ou o histórico da importação. Status/resultados vêm do servidor, não do navegador.

### DataHubImportFile

Identifica o arquivo recebido, separado de seu conteúdo bruto:

- id e import_id; um arquivo XLSX por importação na V1;
- nome sanitizado, digest e tamanho;
- metadata técnica permitida e tipada, como formato detectado e contagens de abas/entradas;
- referência opaca de armazenamento protegido;
- política de retenção, raw_expires_at e raw_deleted_at quando removido.

Não guardar path fornecido pelo usuário, URL pública, segredo ou metadata arbitrária. A remoção do XLSX bruto não remove o registro DataHubImportFile, seus digests ou a proveniência.

### DataHubImportRow

Uma linha de origem analisada:

- id e import_id;
- dataset_code e schema_version;
- sheet e source_row originais;
- normalized_payload construído pelo servidor, limitado aos campos reconhecidos pelo schema;
- validation_status: VALID, INVALID ou SKIPPED;
- fingerprint determinístico quando houver dados suficientes para calculá-lo;
- referência ao DataHubRecord criado ou já existente, quando aplicável.

Payload normalizado não é JSON aberto nem instrução de manutenção. Erro de conversão impede classificar a linha como válida. Linhas de preview podem existir sem qualquer DataHubRecord final.

### DataHubImportIssue

Uma ocorrência de validação separada da linha:

- id, import_id e import_row_id quando aplicável;
- sheet, source_row e column quando identificáveis;
- severity: ERROR ou WARNING;
- stable_error_code;
- mensagem sanitizada.

Problemas do documento inteiro podem ter row/column nulos. Não incluir stack, SQL, segredo ou reprodução desnecessária de conteúdo sensível nas mensagens/logs.

### DataHubRecord

Registro final informacional persistido no Data Hub:

- id, tenant_id e contract_id;
- dataset_code e schema_version;
- business_key contextual calculada pelo servidor;
- payload tipado e validado pelo schema fechado do dataset;
- fingerprint;
- provenance apontando para a importação/arquivo/linha de origem;
- version, created_at e updated_at.

A representação física será especificada no plano, preservando schemas fechados, constraints, chaves contextuais e referências sem cruzamento de contratos. Não aceitar payload livre como substituto de tipagem. Não confundir DataHubRecord com Produto, Pedido, Processo COMEX ou outra entidade operacional definitiva.

### Relações e proveniência

DataHubImport possui um DataHubImportFile e zero ou mais DataHubImportRows/Issues. Uma linha aceita pode originar um DataHubRecord; uma linha idêntica ignorada pode referenciar o registro existente sem substituir sua origem inicial.

Cada registro inserido preserva import_id, nome sanitizado do arquivo, aba, linha, template/versão, usuário real e data/hora. Reimportações sem alteração preservam a proveniência original e registram o novo resultado na importação/linha correspondente.

FKs, constraints e consultas devem impedir referências de arquivo, linha, issue ou registro pertencentes a outro tenant/contrato. Histórico autorizado pode ser consultado por novo contexto válido do mesmo contrato; isso não permite confirmar um preview vinculado a outra sessão/contexto.

## 5. Lifecycle/status da importação

Catálogo fechado de status:

|Status|Significado|Registros finais gravados por esta importação|
|---|---|---|
|RECEIVED|Arquivo aceito para análise; preview ainda não pronto|Não|
|VALIDATING|Parsing/validação em andamento|Não|
|READY_FOR_CONFIRMATION|Preview válido, sem ERROR bloqueante, aguardando confirmação|Não|
|REJECTED|Documento/dados rejeitados: schema, formato, referências ou conflitos de dados|Não|
|EXPIRED|Prazo do preview encerrado antes do commit|Não|
|COMMITTED|Confirmação concluída e auditada; resultado persistido|Sim, ou zero inserções quando todas as linhas são no-op|
|FAILED|Falha técnica impediu concluir a análise ou a confirmação|Não; mutações parciais revertidas|

Transições: RECEIVED → VALIDATING → READY_FOR_CONFIRMATION ou REJECTED. Estados pré-commit podem terminar em FAILED por falha técnica ou EXPIRED pelo prazo. READY_FOR_CONFIRMATION → COMMITTED somente após confirmação e revalidação completas; conflitos de dados reavaliados podem levar a REJECTED e exigir novo preview.

REJECTED, EXPIRED, COMMITTED e FAILED são terminais para aquela importação. Novo processamento requer nova importação/preview, não ressuscita um estado terminal e não renova validade silenciosamente.

A V1 não faz importação parcial de arquivo com ERROR: um erro bloqueante impede toda gravação final. WARNING não bloqueia por si só, mas deve aparecer na revisão. Apenas linhas válidas são inseridas; linhas idênticas existentes são SKIPPED/no-op. Resultado distingue linhas inválidas, ignoradas e inseridas.

Falha técnica não é rejeição de dados nem expiração. Erro de autorização também não deve ser descrito como erro do arquivo: sessão/contexto/permissões revogados tornam a confirmação imediatamente inelegível, independentemente do status persistido.

Status COMMITTED, registros, proveniência e auditoria de sucesso pertencem à mesma transação. Falha de auditoria reverte tudo. Quando viável, FAILED e diagnóstico sanitizado são registrados com auditoria em transação independente depois do rollback; se a auditoria continuar indisponível, manter o último estado estável, retornar falha técnica e nunca alegar sucesso. Estado não deve contradizer a existência de commit.

## 6. Schemas candidatos V1

Escopo é definido pelo servidor: tenant/contrato e unidade autorizada. Dataset e versão são conhecidos no catálogo; referências devem existir no contrato ou no conjunto válido da mesma importação e respeitar escopo vigente.

|Dataset|Campos propostos|Business key dentro de tenant/contrato/dataset|
|---|---|---|
|Produtos|codigo, descricao, unidade_medida, categoria, ativo|codigo|
|Parceiros|codigo, nome, tipo(FORNECEDOR/CLIENTE/TRANSPORTADOR), pais_iso, ativo|codigo|
|Demandas de compra|codigo, produto_codigo, unidade_codigo, quantidade, data_necessidade, modalidade(NACIONAL/INTERNACIONAL), prioridade|codigo|
|Posições de estoque|produto_codigo, unidade_codigo, quantidade_disponivel, data_referencia|produto + unidade + data_referencia|
|Referências COMEX|codigo, parceiro_codigo, moeda, incoterm, data_prevista, status|codigo informacional|
|Previsões financeiras|codigo, referencia_externa, unidade_codigo, moeda, valor, vencimento, natureza(ENTRADA/SAIDA)|codigo|

Datas ISO date, decimal exato para valores/quantidades, boolean estrito e textos limitados. Valores de enum são fechados no schema do servidor. Datas, números e business keys são normalizados antes de comparação/fingerprint.

**Posições de estoque:** remover codigo artificial da identidade. Produto e unidade são resolvidos no escopo contextual; a chave composta é tenant + contrato + dataset + produto + unidade + data_referencia. Quantidade integra o conteúdo/fingerprint, não a identidade. Quantidade diferente para a mesma chave constitui conflito; nova data produz outra posição informacional. Não cria movimento, reserva ou saldo operacional.

**Referências COMEX:** são registros informacionais do Data Hub. Não são entidades definitivas de Processo, Proforma, Container, Booking ou Embarque, não substituem suas identidades/regras e não executam transições operacionais. Campo status descreve informação recebida segundo o schema do dataset, não um workflow COMEX entregue.

Dados financeiros permanecem sensíveis e submetidos à política da Foundation. A política específica e os schemas detalhados serão explicitados no plano e testados antes de qualquer uso. Ausência de política/capability/módulo suficiente falha fechada; não ativar Financeiro operacional nem dar acesso automático a Admin/Suporte.

## 7. Catálogo inicial versionado de templates

Os oito nomes abaixo identificam templates, não TenantRoles nem regras de autorização. Cada template possui identificador estável e versão própria; mudanças de composição/schema devem declarar compatibilidade ou nova versão.

|Template|Composição padrão candidata, sujeita à autorização|
|---|---|
|Coordenação|Produtos, Parceiros, Demandas, Estoque, COMEX|
|Supervisão|Produtos, Demandas, Estoque|
|Comprador Nacional|Produtos, Parceiros, Demandas nacionais|
|Comprador Internacional|Produtos, Parceiros, Demandas internacionais, COMEX|
|Financeiro|Previsões financeiras e referências permitidas|
|Diretoria|Projeções/exportações autorizadas; template não concede importação|
|Loja|Produtos, Demandas e Estoque no escopo autorizado da unidade|
|Centro de Distribuição|Produtos, Estoque e referências logísticas permitidas|

Seleção de template ou nome de perfil não altera principal, papel ou permissões. Conteúdo exposto é a composição autorizada pelo backend. Sem dataset autorizado, explicar indisponibilidade sem conteúdo fictício ou vazamento de schemas/dados restritos.

## 8. Documento Excel oficial

Reutilizar a logo PNG oficial já existente, preferindo variante para fundo claro. Não criar identidade visual nova.

Em todas as planilhas de dados: logo no canto superior esquerdo; título HiAtlas — Supply Chain Intelligence; slogan Um novo horizonte para o seu negócio; empresa, contrato, perfil, unidade/escopo, geração UTC e versão do template.

Cabeçalhos de dados na linha12, primeira linha de dados na13, freeze panes A13; tabela Excel com filtros, formatos consistentes e validações enumeradas. Cores têm legenda e não são a única indicação de obrigatoriedade/status. Modelos vazios não contêm dados de cliente; exemplos separados são exclusivamente sintéticos.

### LEIA-ME visível

Cada workbook oficial inclui uma aba visível LEIA-ME com identidade HiAtlas e instruções claras:

- finalidade da planilha e distinção entre Data Hub e domínio operacional;
- identificação e versão do template;
- campos obrigatórios de cada aba autorizada;
- legenda/significado das cores, acompanhada de texto;
- não renomear abas ou colunas;
- não alterar _HIATLAS_META;
- formatos aceitos de datas, números, booleanos e enums;
- preencher como valores, sem macros, fórmulas ou links externos;
- caminho Data Hub > Excel para upload, preview, correção de erros e confirmação/reimportação;
- política resumida de duplicidade e aviso de que reimportar não sobrescreve registros;
- aviso explícito: a planilha não concede autorização; o HiAtlas revalida acesso no servidor.

A convenção linha12/linha13/A13 aplica-se às abas de dados, não à página de instruções ou metadados.

### _HIATLAS_META oculta

Contém template_id, template_version, schema_version, datasets/abas/colunas e geração. Sem token, credencial ou segredo. Perfil/identificação do contexto são informativos, nunca autoridade de acesso.

Manifest incompatível/alterado é rejeitado. O schema do servidor prevalece mesmo quando os metadados parecem válidos. Pode haver aba auxiliar oculta para enums, sem macros, links externos ou recursos de terceiros.

## 9. Parsing e proteção contra formula injection

Parsing não executa fórmulas, macros, DDE, scripts, consultas, cálculos ou referências externas. Nunca confiar em resultado em cache de célula de fórmula como se fosse valor validado.

Fórmula encontrada em campo de dados é rejeitada com issue por aba/linha/coluna. Rejeitar XLSM/VBA, componentes executáveis e vínculos externos. Não fazer fetch de URL ou recalcular workbook durante validação/preview. Limites configuráveis protegem contra ZIP expandido excessivo, entradas, abas, linhas/células e textos gigantescos; extensão/MIME sozinhos não bastam.

Na geração/exportação, todo texto não confiável é serializado explicitamente como célula textual, nunca como fórmula. Prefixos perigosos como =, +, - e @, inclusive precedidos por controles/whitespace, não podem originar execução; usar mecanismo seguro do gerador para texto literal. Valores negativos tipados como número permanecem números: não confundir tipo decimal válido com string executável.

Não copiar fórmulas, hyperlinks externos ou elementos executáveis da origem para o arquivo exportado. A neutralização ocorre na representação do Excel, preservando o valor normalizado armazenado. Testes inspecionam o tipo/conteúdo das células e comprovam round-trip seguro sem execução.

## 10. Upload, preview e confirmação

1. Autorizar upload e validar documento oficial, limites, manifesto, versão e schemas conhecidos.
2. Criar DataHubImport/File; analisar linhas e persistir Row/Issue com status apropriado, sem escrever registros finais.
3. Mostrar preview paginado, erros/warnings e efeito previsto; permitir confirmação somente em READY_FOR_CONFIRMATION sem ERROR.
4. Vincular preview a ator, AuthSession, AccessContext, tenant/contrato, digest do conteúdo/schema, versão e validade configurável. O payload validado permanece no servidor.
5. Confirmação explícita envia import_id, versão esperada e chave de idempotência; não aceita before/after ou registros arbitrários enviados novamente pelo browser.
6. Após locks, revalidar sessão/contexto, capabilities/módulos/escopo, lifecycle, referências, duplicidade e versões atuais.
7. Gravar DataHubRecords, proveniência, resultado COMMITTED e AuditEvent em uma transação única. Falha técnica/auditoria reverte a gravação; sucesso só após commit.

Preview não é autorização irrevogável. Preview expirado, sessão diferente, contexto revogado ou restrições alteradas impedem execução. Não aceitar endpoint de importação direta sem preview persistente elegível.

## 11. Retenção do XLSX bruto e persistência da evidência

Na V1, reter temporariamente o XLSX bruto em armazenamento privado/protegido, sem URL pública ou endpoint de download irrestrito. Usar referência opaca gerada pelo servidor e nome sanitizado apenas para identificação. Não registrar conteúdo bruto em logs/auditoria.

Prazo configurável por Settings; valor inicial proposto de24 horas a partir do recebimento, sujeito à política operacional aprovada. Expirar/remover o bruto não apaga digests, metadata permitida, linhas normalizadas, issues, proveniência ou DataHubRecords. Esses itens permanecem persistentes conforme política própria de retenção/classificação, sem prometer retenção eterna.

Arquivo removido tem referência de retenção/status e raw_deleted_at atualizados. Falha de limpeza não torna o arquivo público nem aumenta autorização. Preview utiliza dados normalizados persistidos; acesso ao arquivo bruto não é pré-condição para consultar histórico ou confirmar preview ainda vigente. Retenção do bruto não renova o prazo de preview.

Política de preview e de arquivo são distintas. Ambos os prazos e o procedimento controlado de limpeza serão documentados/testados no plano, sem editor universal de retenção ou serviço distribuído nesta V1. Evidências históricas nunca armazenam credenciais, segredos ou payloads fora do schema permitido.

## 12. Duplicidade, idempotência e concorrência

- Business keys contextualizadas por tenant/contrato/dataset; chave composta de estoque é calculada pelo servidor, sem concatenação ambígua controlada pelo cliente.
- Duplicatas no mesmo arquivo são ERROR e bloqueiam a importação completa.
- Chave existente com conteúdo normalizado idêntico gera WARNING/SKIPPED e no-op explícito.
- Chave existente com conteúdo diferente gera ERROR/conflito: sem sobrescrita, upsert genérico ou troca silenciosa de proveniência.
- Novo arquivo semanticamente idêntico não cria novos DataHubRecords; pode registrar nova importação com linhas ignoradas e resultado zero inserções.
- Repetir confirmação/chave de idempotência retorna o resultado existente ao solicitante ainda autorizado; duas confirmações concorrentes produzem um único commit e auditoria de sucesso para aquela importação/comando.
- Alteração de dados/versão entre preview e confirmação exige novo preview ou conflito409; não reaplicar silenciosamente.
- Estado terminal não é ressuscitado; idempotência nunca contorna isolamento, expiração ou autorização vigente.

## 13. Exportação, histórico e UX

Exportar somente projeções autorizadas e limitadas/paginadas do Data Hub, com gerador oficial, LEIA-ME, _HIATLAS_META, segurança de células e proveniência pertinente. Não exportar arquivo bruto de upload por conveniência.

Histórico contextual paginado/sanitizado diferencia rejeição de dados, expiração, falha técnica e commit. Sem conteúdo bruto, credenciais ou dados de outro contrato. Id estrangeiro retorna404/neutro.

UI: loading/erro/retry/empty, identificação de template, issues por aba/linha/campo, warnings, efeito previsto, resumo inseridos/ignorados/rejeitados e confirmação com empresa/contrato/escopo visíveis. Nenhum sucesso otimista antes do commit real.

Preservar tema claro/escuro, desktop/mobile390×844, teclado, foco, labels e mensagens não baseadas apenas em cor. Não persistir payloads, dados consultados, e-mails ou permissões em localStorage/sessionStorage; somente identificadores opacos de contexto conforme Foundation. Cancelar requests e descartar respostas tardias após logout/revogação/troca de contexto.

## 14. Provas e quality gate previstos

Backend: entidades separadas e lifecycle; geração/layout/logo/LEIA-ME/meta; schemas/enums/referências; parsing/limites/macros/fórmulas; exportação anti-injection; capabilities/módulos/sensibilidade; preview sem DataHubRecord; confirmação obrigatória; duplicidade e business key de estoque; idempotência concorrente; revogação durante lock; A/A2/B; proveniência; retenção/remoção do bruto sem apagar normalizados; auditoria e rollback.

Frontend: menu autenticado, geração/download/upload, preview/erros/warnings, confirmação, histórico/exportação e statuses distintos;403/409/expiração/cancelamento/respostas tardias; teclado/temas/mobile. Nenhuma autorização por seletor demo.

PostgreSQL descartável: migrations, grants mínimos, constraints/referências físicas e concorrência. E2E FastAPI/React/navegador reais com dados sintéticos, nunca Demo publicada. Renderizar/inspecionar planilhas geradas durante implementação.

Gate: backend pytest/Ruff; frontend Vitest/oxlint/TypeScript/Vite; git diff --check. Nenhum PASS não executado. Entregar arquitetura, arquivos alterados, schemas, testes, limitações e status final da branch. Sem deploy ou promoção automática.

## 15. Próximo passo

Spec e plano aprovados; executar T1 → T9 com RED → implementação → GREEN → commit, preservando as fronteiras aprovadas. Dados de cliente exigem contexto tenant autorizado e capabilities efetivas, sem bypass de PLATFORM_ADMIN. A Demo permanece congelada.
