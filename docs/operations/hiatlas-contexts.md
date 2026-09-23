# Contextos e autorização — Fase 3

## Contrato HTTP

A autenticação segue [identidade e sessão](hiatlas-identity.md). Cookies seguros
continuam sendo a credencial de sessão. Mutação exige CSRF e origem HTTPS
configurada. O identificador de contexto não substitui a autenticação.

1. GET /api/contracts lista metadados mínimos. Operadores internos veem contratos
   ativos; clientes veem somente seus vínculos ativos com perfil ativo.
   search aceita até 128 caracteres; limit 1–100 e offset 0–10000.
2. POST /api/contexts recebe apenas {"contract_id":"UUID"} e devolve o id opaco,
   somente como {"id":"UUID"}. A leitura GET /api/context retorna tenant/contrato, código, ambiente, expiração e capabilities atuais.
   O servidor verifica o contrato e a identidade antes de criar o contexto.
3. Enviar esse id no header X-HiAtlas-Context para cada operação contextual.
   Ausência/header inválido: 403; sessão inválida: 401. Não há contrato implícito.
4. DELETE /api/contexts/{id} encerra somente contexto da sessão atual; GET
   /api/context permite consultar o contexto vigente. Encerrar contexto não
   encerra os demais. Logout invalida todos os contextos da sessão.

Na interface da Fase 4, o id fica em memória/sessionStorage **por aba**.
Não armazenar sessão autenticada ou contexto em localStorage. Não tratar
capabilities retornadas como autoridade: cada operação revalida tudo no servidor.
Consulte [a interface autenticada](hiatlas-frontend.md) para execução e validação da Fase 4.

CONTEXT_SECONDS: padrão 3600, intervalo 60–28800; expiração nunca ultrapassa a
sessão autenticada e não é renovada ao usar o contexto. Inatividade/expiração e
revogação da sessão também invalidam o acesso.

## Rotas e autoridade

| Rota | Autoridade |
|---|---|
| POST /api/tenants | PLATFORM_ADMIN, global, auditado |
| POST /api/tenants/{id}/contracts | PLATFORM_ADMIN, global, auditado |
| GET /api/contracts | sessão; filtragem de vínculos para cliente |
| POST/DELETE /api/contexts | sessão; seleção autorizada/propriedade da sessão |
| GET /api/context | contexto válido |
| GET /api/memberships/{id} | contexto + memberships.read |
| GET /api/roles | contexto + roles.read |
| GET /api/roles/assignable | contexto + roles.assign |
| POST/PATCH /api/roles[/{id}] | contexto + PLATFORM_ADMIN |
| PUT /api/memberships/{id}/role | contexto; admin ou suporte elegível |

Objetos de outro tenant **ou outro contrato do mesmo tenant** retornam 404,
igual a um id inexistente, após a verificação geral de capability.
tenant_id/contract_id enviados livremente não mudam escopo. Contrato na seleção
é um alvo solicitado, nunca prova de autorização. Não existe current_contract
na sessão. Plataforma e TenantRole têm tabelas e fluxos separados; códigos
PLATFORM_* são recusados em perfis de cliente.

PATCH role e PUT membership role exigem expected_version; divergência retorna
409. A atribuição recebe role_id, não nome ou código de papel interno.
Criação de memberships, convites e administração de cliente ficam para as fases
correspondentes; nesta fase o vínculo é persistente e usado para autorização.

## Elegibilidade do suporte

support_assignable começa false e só PLATFORM_ADMIN pode alterar a flag.
role_support_eligible verifica simultaneamente perfil ativo, opt-in explícito,
classificação STANDARD, ausência de histórico sensível e capabilities não sensíveis.
Listagem e atribuição aplicam a mesma política; a atribuição relê o estado vigente.

ADMINISTRATIVE, FINANCIAL_FISCAL e SENSITIVE são inelegíveis. Capabilities
finance.read, fiscal.read e roles.manage também tornam o perfil sensível.
sensitivity_locked registra permanentemente sensibilidade observada pelo servidor:
renomear, reclassificar ou remover uma permissão não torna esse perfil elegível.
Para uma função nova e não sensível, criar um perfil novo. Nenhum endpoint permite
limpar esse histórico. Combinação flag=true com sensibilidade é recusada com 422.

Suporte não pode trocar o perfil atual de um vínculo já sensível, nem gerenciar
identidades internas via memberships. PLATFORM_ADMIN pode associar perfis do
contrato, mas finance.read/fiscal.read continuam **sem concessão de acesso** nesta
fase. A futura concessão financeira temporária não é substituída pela seleção.

## Transações, revogação e auditoria

A autorização consulta usuário/sessão, contexto, tenant/contrato, membership,
perfil e permissões atuais. Contextos revogados/expirados e entidades inativas ou
bloqueadas são negados. Edição de perfil revoga contextos de clientes afetados;
atribuição revoga os do usuário no contrato correspondente, preservando outros.

Locks seguem identidade de plataforma compartilhada, usuário/sessão, tenant,
contrato e registros envolvidos. Mudanças de operadores usam o lock exclusivo
da identidade. Contrato serializa operações contextuais; isso prioriza correção
nesta fundação e deve ser medido antes de ampliar concorrência. Não há estado
global mutável de contrato selecionado. Atribuição revalida após aguardar locks.

Criações de tenant/contrato, seleção/encerramento, criação/edição de role e
atribuição geram audit_events na **mesma transação** da mutação. Falha da auditoria
reverte a alteração; não existe endpoint genérico para gravar auditoria arbitrária.
Negações seguem access_events sanitizados da Fase 2.

## Banco e limites

Aplicar Alembic até 0003 com a credencial de migração, conforme
[guia do banco](../../database/README.md). Preservar credencial runtime separada.
Membership/role/permission/context têm FKs compostas para integridade de escopo.
O isolamento das consultas é aplicado pelo servidor e pelas FKs; esta fase não
implementa PostgreSQL RLS nem concede SQL arbitrário aos clientes.

Dados de negócio novos: SELECT/INSERT/UPDATE, sem DELETE/TRUNCATE.
AccessContext é técnico: SELECT/INSERT/UPDATE/DELETE, sem TRUNCATE; retenção futura
deve remover apenas registros cujo ciclo de vida terminou. Auditoria continua
sem UPDATE/DELETE/TRUNCATE. Nenhum segredo é retornado pelas novas rotas.

O catálogo reserva códigos futuros, mas somente as concessões explícitas da
Fase 3 são efetivas. Não há endpoints de domínio financeiro, suporte simulado,
manutenção, correção operacional, reprocessamento ou gerenciadores genéricos.
