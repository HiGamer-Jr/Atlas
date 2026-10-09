# HiAtlas — Solicitação de Compra V1

Data: 2026-10-08. Mudança arquitetural. Status: proposta para aprovação do written spec; implementação e implementation plan ainda não autorizados por este documento.

## 1. Propósito, base e limites

O solicitante registra uma necessidade interna com vários itens, acompanha sua evolução e fornece especificações. Compras recebe uma fila formal, realiza triagem e atribui responsabilidade. Solicitação de Compra não é Pedido de Compra: não constitui compromisso com fornecedor, ordem de pagamento, movimentação de estoque ou autorização financeira.

Base exclusiva: `feat/hiatlas-customer-scope-v1`, `fa354b73cdb43d600949e54b81595f416ef5cd65`. Branch deste desenho: `feat/hiatlas-purchase-request-v1`, worktree exclusiva. Sem alterações em main, integration, release, Demo; sem deploy. Nesta etapa somente documentação. A próxima implementação exige aprovação deste spec e, depois, do plano.

Escopo proposto para futura implementação V1: agregado Solicitação, itens, submissão, triagem, aprovação simples, atribuição, registro manual de atendimento real, anexos privados, histórico e interface funcional mínima. Não haverá dados de exemplo, catálogo sintético, dashboard, Pedido de Compra, estoque automático ou ator PARTNER.

Decisão de negócio proposta para revisão: aprovação obrigatória após triagem na V1, por pessoa diferente do solicitante. Dispensa configurável por contrato e cadeias de aprovação ficam para evolução. Esta escolha não está sendo tratada como decisão previamente aprovada do cliente.

## 2. Entendimento do repositório atual

Leitura da base acima:

| Área | Evidência | Consequência |
|---|---|---|
| Procurement | `backend/app/organization/modules.py`: PROCUREMENT comercial; OPERATIONAL_MODULES contém apenas DATAHUB | Não existe serviço operacional de solicitações/pedidos a reutilizar; ativar comercialmente não concede operação |
| Demandas/estoque informativos | `backend/app/datahub/models.py` e `catalog.py` | Imports não são solicitações, catálogo mestre de materiais nem ledger de estoque; nenhuma conversão automática |
| Tenancy/context | `backend/app/tenancy/contexts.py`, `dependencies.py`, `models.py` | Contexto opaco vincula ator, sessão, tenant e contrato; revalidação atual obrigatória |
| Authorization | `backend/app/platform/capabilities.py`, `types.py`, `policy.py` | Catálogo fechado, capabilities com namespaces pontuados; TenantRole customizada e permissões persistidas; operador interno separado |
| Organization | `backend/app/organization/models.py`, `unit_authorization.py` | Nodes reais com contrato, tipos, hierarquia e atividade; ALL explícito ou grants RESTRICTED exatos |
| Self scope | `backend/app/tenancy/operational_scope.py`, `operational_scope_schemas.py` | Discovery limitado, fail-closed; capabilities descritivas, não credenciais |
| Auditoria | `backend/app/audit/models.py`, `schemas.py`, `service.py`; migração 0001 | Eventos append-only, snapshots tipados, ator real e request_id; actor_role representa somente PlatformRole |
| Transações | `backend/app/db/session.py` | Transação de request única e runtime não proprietário, não superuser, sem bypassrls |
| Projetos | Sem módulo backend de projetos; `frontend/src/workspace/projects/projectCatalog.ts` declara dados fictícios | Não usar seus IDs/nomeações; WORKSITE real pode identificar unidade de obra, não equivale a Project |
| Centro de custo | Não encontrado agregado/cadastro operacional backend | Não inventar cadastro ou aceitar ID sem validação |
| Frontend | `frontend/src/operational/`, ContextProvider e ApiClient existentes | Consumir contexto real; isolamento entre abas; limpar estado ao perder validade |

As tabelas atuais dependem de filtros e FKs compostas, com runtime de privilégio mínimo. Não assumir que RLS universal já protege toda query: consultas scoped continuam obrigatórias. Não relaxar database_harness, migrações, auditoria ou segregação financeira/fiscal.

## 3. Alternativas e recomendação

**A — Domínio próprio no monólito existente (recomendado).** Agregado relacional com comandos explícitos, autorização compartilhada, histórico transacional e integrações futuras por referências de itens. Mantém semântica distinta dos imports e usa infraestrutura já comprovada. Custo: novo módulo e catálogo de capabilities, sem duplicar tenancy.

**B — Evoluir DEMANDS do DataHub em solicitações.** Menos entidades iniciais, mas mistura importação informativa com workflow, ownership, aprovação e histórico operacional. Proveniência e permissões de import/export não representam poderes de solicitante/comprador. Rejeitado.

**C — Motor genérico de workflow/event sourcing ou serviço separado.** Flexível para workflows arbitrários, porém exige coordenação de autorização, projeções e operação adicional sem necessidade comprovada. Rejeitado na V1. Eventos imutáveis acompanham o agregado relacional; não reconstruiremos autorização por replay histórico.

## 4. Componentes e fluxo

Propor `backend/app/procurement/requests/` com modelos/schemas, policy, queries, commands, transitions, attachments e routes. As fronteiras são funcionais, não obrigação de criar um arquivo por função.

- Policy recebe Principal e AccessScope, recalcula autorização e unidade; nenhuma role histórica ou perfil de UI participa.
- Queries aplicam tenant/contract, ownership e unit scope antes de count, paginação, filtros ou projeção de nomes.
- Commands bloqueiam estado atual, exigem expected_version, validam transição e gravam agregado/evento/auditoria juntos.
- Transitions define tabela fechada de transições, pré-condições e campos congelados.
- Attachments controla bytes privados e metadados; não reutiliza retenção temporária do import XLSX.
- API reutiliza autenticação, CSRF, Context e contrato de erros existente.
- Frontend reutiliza OperationalScopeProvider; nova área mínima de lista própria, criação/edição de rascunho e detalhe/histórico; fila de triagem e ações apenas quando capabilities descritivas permitem apresentar controles. Backend sempre decide.

Fluxo: contexto autenticado → scope discovery completo → candidatos de unidade → comando com IDs candidatos → validação fresca → transação → representação autorizada. Scope inválido/desconhecido/oversized não libera controles. Nenhum fallback demonstrativo ou cache de autorização em localStorage.

## 5. Modelo de dados e invariantes

Todas as entidades de negócio têm tenant_id/contract_id não nulos; requester e buyer têm FKs compostas para memberships do contrato e autoria vincula user à membership; FKs compostas impedem referências cruzadas; exclusões físicas de solicitações submetidas e eventos são proibidas. UUID gerado no servidor identifica cada entidade. O UUID é também o identificador exibível inicial; numeração sequencial fiscal/comercial não é requisito nem fonte de autorização.

### PurchaseRequest

`id`, tenant/contract, `requester_user_id`, `requester_membership_id`, `requesting_node_id`, `title` (200), `description` (4000), `justification` (4000), `priority` (NORMAL/HIGH/URGENT), `needed_on` (date), `notes` (4000), `status`, `buyer_membership_id` nullable, `version` >=1, created/updated/submitted/triage_started/approval_requested/approved/assigned/fulfillment_started/fulfilled/closed timestamps UTC quando aplicáveis.

Requester deriva do principal/membership, não pode ser indicado pelo navegador; autoria e tenant/contract ficam imutáveis. Unidade pode mudar somente no rascunho, para candidato autorizado atual. V1 admite tipos UNIT, STORE, DISTRIBUTION_CENTER, WAREHOUSE, OFFICE, WORKSITE e BRANCH; COMPANY é agrupamento, não unidade solicitante. Isso restringe uso de negócio sem alterar a semântica dos grants existentes. Rascunho exige uma unidade real e título; demais conteúdos podem estar incompletos até submit.

Projeto e centro de custo são associações opcionais futuras, não IDs livres armazenados agora. API V1 rejeita project_id/cost_center_id não nulos com `REFERENCE_DOMAIN_UNAVAILABLE`; não expõe select fictício. Um WORKSITE real pode ser unidade solicitante já na V1. Não existe promessa de autorização por nome textual de obra nas observações. Quando os domínios existirem, adicionar FKs scoped, atividade e associação à unidade; nunca resolver por catálogo da Demo.

### PurchaseRequestItem

`id`, tenant/contract/request_id, `position` única por solicitação, `description` (2000), `specification` (4000), `requested_quantity` Numeric(18,6)>0, `uom_code`, created/updated. Limite 100 itens por request. Decimal no wire como string, sem float. UOM V1: UN, KG, G, L, ML, M, M2, M3, CX, PCT; códigos técnicos reais, não materiais demonstrativos. CX/PCT exigem descrição do conteúdo na specification; nenhuma conversão automática. Material sem cadastro é descrição real fornecida pelo usuário; product_id de DataHub não vira autoridade de material. Rascunho pode ter zero itens; submit exige pelo menos um item válido e todos os campos obrigatórios de necessidade.

Depois de submit, quantidades, UOM, unidade, justificativa e itens congelam. Mudança substancial exige cancelar e criar nova solicitação; não há edição silenciosa após aprovação nem reset de autorização. Notes adicionais tornam-se eventos append-only, não sobrescrevem evidência anterior.

### PurchaseRequestEvent e ApprovalDecision

Evento privado do agregado: id, scope, request_id, sequence, aggregate_version, action, actor_user_id, actor_membership_id, tenant_role_id/code snapshot quando houver, occurred_at, reason, payload tipado limitado, audit_event_id. Unique(request_id,sequence). Imutável também no banco (runtime INSERT/SELECT, sem UPDATE/DELETE e proteção equivalente à auditoria).

ApprovalDecision: evento tipado APPROVED/REJECTED, aprovador real, versão aprovada, razão; não precisa de tabela mutável paralela na V1. Snapshot de conteúdo aprovado no histórico é evidência, nunca autorização futura. Não forçar TenantRole no campo actor_role da auditoria existente: para tenant actor_role é null, proveniência tenant fica no snapshot tipado.

### RequestFulfillmentEntry

id, scope, request/item, quantity Decimal positiva, UOM do item, actor e timestamps, source_kind MANUAL_EXTERNAL, evidence/reason obrigatórios, aggregate_version. É atestação manual de atendimento ocorrido, não reserva, baixa, transferência ou pedido. Soma não excede quantidade solicitada. Reversão é entrada compensatória explícita referenciando original, sem apagar/editar, validada contra saldo; somente antes de encerramento e por capability fulfill. Registro/reversão atualizam projeção e histórico atomicamente.

### RequestAttachment

id, scope, request_id, item_id opcional scoped, uploader real, filename sanitizado, media_type verificado, digest SHA-256, size, created_at e bytes privados. V1 PostgreSQL bytea, limite 5 MiB/arquivo, 10 arquivos/solicitação, PDF/PNG/JPEG/TXT; signatures e UTF-8 para TXT, sem HTML/SVG/arquivos executáveis, arquivos criptografados ou fetch remoto. Download autenticado attachment/disposition, nosniff, Cache-Control no-store; nunca URL pública. Sem remoção física após submissão; anotação de obsolescência por evento preserva evidência. Rascunho pode remover arquivo com evento. Retenção segue a solicitação; não usar TTL do DataHub. Scanner antimalware/storage externo são riscos de evolução documentados; limites e descarga não executável não equivalem a scanner. Anexo não contém autoridade de domínio.

Índices scope/status/created_at/id, scope/requester, scope/node, scope/buyer; eventos por request/sequence; itens por request; needed_on para consultas futuras. Campos de timestamps, quantidades e dimensões reais suportam indicadores sem simulação.

## 6. Máquina de estados

Estados persistidos: DRAFT, SUBMITTED, IN_TRIAGE, AWAITING_APPROVAL, APPROVED, IN_FULFILLMENT, FULFILLED, CLOSED, REJECTED, CANCELLED.

| Comando | Origem → destino | Regra |
|---|---|---|
| create/edit | DRAFT → DRAFT | Próprio rascunho e create; campos limitados |
| submit | DRAFT → SUBMITTED | Próprio autor; conteúdo completo, needed_on presente (atrasada é permitida e claramente sinalizada), justificativa obrigatória, URGENT exige razão |
| start-triage | SUBMITTED → IN_TRIAGE | triage; timestamp real |
| request-approval | IN_TRIAGE → AWAITING_APPROVAL | triage; descrição/itens válidos; nenhuma dispensa implícita |
| approve | AWAITING_APPROVAL → APPROVED | approve; aprovador != solicitante |
| reject | IN_TRIAGE ou AWAITING_APPROVAL → REJECTED | triage na primeira, approve na segunda; razão obrigatória |
| assign/reassign | APPROVED ou IN_FULFILLMENT → mesmo estado | assign; candidato comprador válido; timestamp/evento; não é novo estado |
| start-fulfillment | APPROVED → IN_FULFILLMENT | buyer atribuído atual + fulfill; alvo elegível |
| record/reverse-fulfillment | IN_FULFILLMENT → mesmo estado ou FULFILLED | fulfill pelo buyer atribuído; soma por item; completo quando todos atingem quantidade |
| close | FULFILLED → CLOSED | close e autor original ou buyer atribuído; confirma encerramento; sem alterar atendimento |
| cancel | DRAFT/SUBMITTED/IN_TRIAGE/AWAITING_APPROVAL/APPROVED/IN_FULFILLMENT → CANCELLED | cancel; DRAFT somente autor; demais estados antes da execução autor ou triage; durante execução apenas triage; razão; conserva atendimento já realizado |
| add-note | estado não DRAFT nem CLOSED | permissão de leitura + comment; evento sem editar conteúdo; REJECTED/CANCELLED permitem explicação posterior |

Parcialmente atendida é `fulfillment_state=PARTIAL`, derivado das somas reais, enquanto status IN_FULFILLMENT; sem quantidade positiva é NONE; completo é COMPLETE. Atribuída é atributo buyer e evento, não estado. Aprovada é estado porque delimita autorização para executar. CLOSED distingue atendimento registrado de encerramento confirmado. REJECTED/CANCELLED/CLOSED não reabrem. FULFILLED não permite reversão nesta V1: erros após atendimento completo exigem processo de correção futuro, nunca adulteração do histórico.

Não há atribuição antes de aprovação ou avanço por PATCH status. Campos temporais representam primeira ocorrência; reatribuições e detalhes posteriores ficam nos eventos. assigned_at registra primeira atribuição, buyer_membership_id a atribuição atual. Solicitação parcialmente cancelada preserva quantidades e saldo não atendido, sem declarar atendimento completo. Aprovação não é aprovação de pagamento e não aumenta poderes financeiros.

## 7. Autorização e capabilities

Namespaces pontuados seguem `datahub.<dataset>.<action>`. Proposta: `procurement.requests.create`, `read_own`, `read_unit`, `triage`, `approve`, `assign`, `fulfill`, `cancel`, `close`, `comment`. Descritores domain procurement, module PROCUREMENT, tenant_role/tenant_enabled true; read_own/read_unit read_only_safe true e mutates_business_state false; demais mutam. Sem inclusão em INTERNAL_GRANTS ou classificação FINANCIAL_FISCAL; nenhuma concessão por nome da role. Atualizar catálogo fechado e constraint SQL de TenantRolePermission coerentemente, preservar permissões sensíveis existentes.

- read_own: somente próprio usuário e membership/contrato da autoria, ainda dentro do unit scope atual; ownership não sobrevive como bypass à perda de escopo.
- read_unit: solicitações das unidades atualmente autorizadas; nunca amplia para todo tenant. Rascunho permanece privado ao autor mesmo com read_unit/triage.
- create inclui editar/submeter próprio rascunho; não inclui leitura alheia nem execução de comprador.
- Capabilities de ação não concedem automaticamente read_unit: operadores do fluxo precisam também read_unit para fila/detalhe. Autor usa read_own; comandos em registro existente exigem autorização de leitura correspondente além da ação.
- fulfill é capacidade de comprador operacional, sem administração. Assignment não concede role/capability/scope a ninguém. Comprador candidato: usuário tenant ativo, membership real do mesmo contrato, role ativa com fulfill + read_unit, PROCUREMENT contratado/ativo e escopo atual da unidade. Cada ação revalida ator e candidato; se comprador perdeu acesso, objeto mantém histórico e triage pode reatribuir, sem exibir dados pessoais além dos autorizados.
- approve exige segregação solicitante/aprovador. Ter assign não implica approve. Comprador/aprovador podem coincidir se forem pessoas distintas do solicitante; não criar regra hierárquica fictícia.
- cancel exige capability própria e relação indicada na tabela; triage sozinha não cancela. comment não concede leitura.
- Lista de candidatos do comprador exige assign e unidade autorizada, retorna apenas id da membership e nome necessário, sem e-mail ou catálogo administrativo; limite 100/paginação e total só do filtro autorizado.

Cada operação: Context opaco + autenticação/CSRF quando mutação → revalidate → membership_role fresca → capability → PROCUREMENT contratado, ativo e implementação disponível → require_authorized_node na unidade do registro → ownership/visibilidade/estado → validações de IDs referenciados → revalidação após espera em locks → mudança/retorno. Tenant/contract/requester/role/status não são campos editáveis no payload. Cross-scope lookup retorna 404 uniforme; ação não permitida 403, sem revelar existência em outro contrato.

Node disponível é entidade ativa; unit scope autorizado é direito real sobre ela; módulo contratado é elegibilidade comercial; módulo ativo é configuração atual; capability efetiva é grant atual do ator. Nenhum deles isolado concede operação. ALL não é node persistido; RESTRICTED não expande descendants implicitamente. Transição ALL→RESTRICTED continua exigindo grants explicitamente novos ou zero; comando atômico/versionado/auditado existente não será modificado por este domínio.

operational-scope continua descrição para UX; nunca recebe de volta capabilities como prova. Futuramente incluir PROCUREMENT em OPERATIONAL_MODULES somente junto do domínio funcional e testes; filtrar capabilities de solicitações quando não houver unidade elegível; frontend reconhece os novos códigos sem aceitar desconhecidos. Não alterar schema_version 1 para modificar semântica existente: acréscimos seguem catálogo protocolar, frontend/backend atualizados em conjunto. Discovery acima do limite 1000 continua 503 explícito e sem árvore truncada; paginação de solicitações não é paginação do grafo de autorização. INTERNAL não recebe tenant role artificial nem acessa requests por grants de suporte/admin nesta V1.

## 8. Contratos de API propostos

Prefixo `/api/procurement/requests`. Todas as respostas privadas no-store, envelope de erros existente. Campos desconhecidos forbidden; IDs UUID candidatos. version é inteiro positivo; expected_version obrigatório em toda mutação de agregado existente, inclusive anexos/notas. Sem PATCH genérico de estado.

| Endpoint | Entrada e resultado |
|---|---|
| POST / | {requesting_node_id,title,description?,justification?,priority?,needed_on?,notes?,items?}; 201 DRAFT, IDs/escopo/autor/version do servidor |
| GET / | visibility=own ou unit; default own; filtros status, node_id, requester/buyer somente se leitura unit; limit 1..100, cursor opaco scoped; itens/total filtrados antes da paginação |
| GET /{id} | Detalhe autorizado com itens, buyer, fulfillment_state e quantidades; nenhum payload contém autorizações reutilizáveis |
| PATCH /{id}/draft | expected_version e campos permitidos/itens; itens existentes devem pertencer ao agregado; substituição atômica; somente DRAFT |
| POST /{id}/{submit,start-triage,request-approval,approve,reject,start-fulfillment,cancel,close} | expected_version, reason quando exigido; novo estado/version |
| POST /{id}/assignment | expected_version,buyer_membership_id; validar candidato atual; não aceita user/role arbitrários |
| GET /buyer-candidates | requesting_node_id candidato; assign + read_unit; candidates scoped/paginados |
| POST /{id}/fulfillments | expected_version,item_id,quantity string,evidence,reason; quantity positiva/UOM original; novo saldo/estado/version |
| POST /{id}/fulfillments/{entry}/reverse | expected_version,reason; compensação exatamente do original não revertido; só IN_FULFILLMENT |
| POST /{id}/notes | expected_version,text; evento append-only |
| GET /{id}/history | leitura do registro; eventos de negócio paginados, nunca audit.read administrativa |
| POST /{id}/attachments | multipart bounded com expected_version e item_id opcional; DRAFT pelo autor/create; SUBMITTED/IN_TRIAGE/AWAITING_APPROVAL/APPROVED/IN_FULFILLMENT/FULFILLED por comment + leitura; estados terminais rejeitam novos anexos; arquivo/metadados/evento atômicos |
| GET /{id}/attachments/{attachment}/download | mesma autorização atual do registro; sem URLs públicas/cache |
| DELETE /{id}/attachments/{attachment} | expected_version; somente próprio DRAFT; evento no mesmo commit |

Detalhe inclui schema_version=1, id, tenant_id/contract_id derivados, requester mínimo, requesting_node mínimo autorizado, buyer mínimo ou null, campos da necessidade, status, version, timestamps, items com requested/fulfilled/remaining e UOM, attachment metadata. Nomes snapshots usados no histórico não abrem visibilidade a nodes fora do escopo atual. Cursor não permite alterar filtro/tenant, não é credencial e sempre revalida contexto.

Erros: 401 sessão inválida; 403 capability/module/unit; 404 NOT_FOUND uniforme; 409 VERSION_CONFLICT, INVALID_TRANSITION, OPERATIONAL_SCOPE_INVALID, IDEMPOTENCY_CONFLICT; 413 ATTACHMENT_TOO_LARGE; 422 conteúdo inválido/REFERENCE_DOMAIN_UNAVAILABLE; 503 OPERATIONAL_SCOPE_TOO_LARGE. Nenhum erro devolve informações de outro tenant.

## 9. Auditoria e evidência

Eventos `procurement.request.created`, `.draft_updated`, `.submitted`, `.triage_started`, `.approval_requested`, `.approved`, `.rejected`, `.assigned`, `.fulfillment_started`, `.fulfillment_recorded`, `.fulfillment_reversed`, `.fulfilled`, `.cancelled`, `.closed`, `.note_added`, `.attachment_added/removed` em catálogo fechado de snapshots tipados. Incluir request scope/version, origem/destino, IDs de itens/quantidades relevantes, reason, ator real, membership/role usadas e request_id. Não copiar bytes, credenciais ou contexto opaco; texto livre limitado ao histórico privado, auditoria central registra hashes/referências e campos allowlisted necessários.

Sem fabricada PlatformRole para tenant. Ampliar AuditInput entity_type/snapshot validators com precisão; registros de auditoria e histórico no mesmo commit da mudança. Falha na auditoria aborta mutação. Não publicar histórico pela rota administrativa, nem exigir audit.read ao solicitante. Denials usam mecanismo de observação de acesso existente, sem gravar evento de sucesso na transação abortada. Histórico não pode ser reescrito pela runtime role, inclusive SQL direto.

## 10. Concorrência e idempotência

Row lock e populate_existing no agregado, expected_version antes de escrever, incremento uma vez por comando e único sequence/version de evento principal. Eventos complementares de fulfillment_complete no mesmo comando têm sequence distinto e mesma aggregate_version. Estado, itens, anexos, entradas, idempotency result e audit são atômicos. Nenhum estado intermediário visível.

Usar ordem determinística de locks compatível com revalidate e unit_authorization existentes: contexto/membership/role → módulos → nodes e grants → agregado → itens/entradas, candidatos múltiplos em ordem estável. Implementação deve testar essa ordem contra comandos administrativos existentes e resolver ciclos antes de aprovação de código; não duplicar ordem arbitrariamente no domínio. Revalidar após bloqueios; commits concorrentes de revogação são respeitados conforme ordenação transacional, nenhuma autorização sobreviverá na próxima requisição.

Idempotency-Key UUID obrigatório em POST de criação e comandos, incluindo atendimento/assignment/notes/anexos. Escopo da chave: tenant/contract/actor/context/rota/alvo; digest canonical inclui expected_version e bytes digest. Mesma chave/payload após revalidação retorna resultado anterior sem executar; payload diferente 409. Resultado antigo nunca contorna autorização atual nem devolve detalhe de unidade perdida. PATCH/DELETE exigem version, retry após resposta perdida conflita; cliente refaz GET autorizado. Idempotency persistida sem TTL na V1, crescimento é risco operacional monitorável, nunca motivo para reexecutar atendimento.

Duas abas mantêm contextos e rascunhos independentes; conflito de mesma solicitação em abas retorna 409, sem merge automático nem sobrescrita silenciosa. Não guardar escopo/capabilities como autoridade no navegador.

## 11. Evolução, indicadores e PARTNER

Futuros ProcurementProcess/Order e InventoryTransfer terão vínculo por item e quantidades alocadas/atendidas, permitindo many-to-many (um processo atende vários requests; um item atendido por vários processos/fontes). Não inserir purchase_order_id único no cabeçalho nem supplier/payment em request. RequestFulfillmentEntry poderá receber referência scoped a fonte real com migração; source_kind desconhecido é rejeitado na V1. Evitar polimorfismo baseado em UUID livre como autoridade. Registro manual atual não movimenta estoque nem cria pedido.

Projetos e centros de custo exigirão domínios oficiais e validação scoped da associação. Nome livre pode explicar necessidade, não substituir referência validada. Separar datas de eventos para tempo até triagem/atribuição/aprovação, lead time até FULFILLED/CLOSED; aberto = estados não terminais DRAFT excluído; vencido = aberto submetido com needed_on anterior à data do contrato (timezone oficial a definir na futura configuração; V1 reporta date sem calcular dashboard); urgente por priority. Quantidade por UOM/item é agregável; não somar KG com UN. Métrica itens mais solicitados por material mestre só após existir cadastro; texto livre não constitui identidade confiável. Rejeição/cancelamento e atendimento parcial preservam fatos e denominadores futuros sem números fictícios.

PARTNER é restrição arquitetural futura, sem código nesta branch: classe de ator própria e organização parceira própria, distinta de TenantRole e INTERNAL. Acesso apenas a processos explicitamente compartilhados; poderá atualizar milestones COMEX/logística, anexar documentos e NF/NFS, solicitar pagamentos e acompanhar seus próprios processos/pagamentos; nunca aprovar/executar pagamento, nem administração ou financeiro amplo. Requester V1 é tenant interno; compartilhamento futuro ocorre em processos downstream, sem inferir acesso à solicitação de origem ou à unidade por vínculo comercial. Proveniência de eventos admite evolução versionada do tipo de ator, sem codificar parceiros como buyer_membership_id ou role artificial. Não ampliar union de atores, memberships ou catálogo de pagamento agora.

## 12. Plano de testes e critérios de aceitação futuros

- PostgreSQL oficial owner/runtime, migrations e constraints scoped: requests/itens/anexos/eventos/entries cross-tenant ou cross-contract não persistem; runtime sem UPDATE/DELETE histórico; falha audit rollback integral. Sem SQLite, harness relaxado ou skips.
- ALL, uma/múltiplas unidades RESTRICTED, zero grants, histórico dormente ALL→RESTRICTED, COMPANY inelegível, ancestors inativos, node estrangeiro, grant removido: create/list/detail/download/commands falham fechado conforme caso.
- Revogar sessão/context/membership, inativar role/tenant/contrato/node/module, remover capability durante espera de lock; próxima revalidação bloqueia, sem autorização por cache.
- Módulo contratado/ativo disponível; contratado/inativo informativo indisponível; não contratado inacessível; manipular capabilities/frontend/headers/IDs não autoriza.
- Role customizada não histórica com create/read_own funciona; solicitante sem powers de buyer/admin; read_own nunca amplia unidade; read_unit não vê rascunho alheio nem count/nomes estrangeiros. INTERNAL/support/grant não obtêm TenantRole/requests.
- Todos os caminhos da tabela, pares origem/comando inválidos, submit incompleto, URGENT sem justificativa, segregação de aprovação, assign sem target elegível, target revogado, reassign auditada, edição pós-submit proibida.
- Múltiplos itens, precisão decimal, UOM/limites, atendimento parcial/completo, overdelivery, reversão/dupla reversão, cancelamento parcial, terminal não reabre, fechamento explícito e evidence real obrigatória.
- Conflito de versão e respostas perdidas, mesma chave e payload diverso, retries com scope revogado; concorrência de aprovação/cancel/assign/fulfill e locks administrativos, ausência de dupla contabilização/deadlocks não tratados.
- Anexos sem disclosure, tipo real/tamanho/path traversal/UTF-8, cross-item, download revogado, atomicidade/versionamento e ausência de cache; projeto/centro de custo fictício rejeitados.
- UI scope desconhecido/inválido/árvore oversized: controles bloqueados com estado claro; sem fallback; duas abas/contextos independentes; reset na mudança de contexto; formulários com quantidades reais e sem dados demonstrativos.
- Ao implementar, gate integral `./scripts/check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'`: backend/frontend/scripts, lint/build, zero skips, git diff --check e cleanup PostgreSQL PASS. Nesta fase docs-only não foi executado e não se reivindica resultado de código novo.

## 13. Riscos, exclusões e self-review

Riscos: decisão de aprovação obrigatória requer revisão do usuário; ausência de projetos/centro de custo/material mestre limita referências estruturadas; armazenamento bytea e idempotency sem TTL crescem; anexos sem scanner exigem evolução operacional; atendimento manual é atestação, não evidência automática de estoque/compra; locks compartilhados precisam testes de concorrência reais; cap/module catalog precisa atualização backend/frontend/SQL coerente.

Exclusões deliberadas: dispensa/cadeias/alçadas monetárias de aprovação, notificações/e-mail, import que cria requests, produtos/projetos/cost centers fake, pedidos/cotações/fornecedores, estoque/transferência automática, pagamentos/financeiro/fiscal, dashboards, PARTNER/Trade código, alteração da Demo, configuração de deploy. Não mexer em perfis históricos para autorizar atores reais.

Self-review realizada: separamos estado de atribuição e projeção parcial; diferenciamos aprovação de pagamento; ownership não contorna scope; referências inexistentes rejeitadas; todos os comandos passam por permissão/versão e trilha; eventos e auditoria atômicos; módulos/capabilities não são prova reutilizável; Partner é exclusivamente restrição futura. Sem placeholders de implementação. Este documento é spec para revisão, não implementation plan.
