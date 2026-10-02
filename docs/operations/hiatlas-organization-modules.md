# HiAtlas — Organização e módulos contratados (Fase 7)

O Administrador HiAtlas administra estrutura e módulos somente depois de selecionar
empresa/contrato/ambiente. Sessão e contexto vigentes continuam sendo revalidados pelo
servidor em toda chamada; o navegador representa essas decisões.

## Estrutura física

OrganizationNode pertence obrigatoriamente ao tenant e ao contrato. Tipos conhecidos:
Empresa, Filial, Unidade, Loja, Centro de Distribuição, Depósito, Escritório e Canteiro.
O código técnico WORKSITE representa o canteiro/unidade física. Não representa Obra,
Project, cronograma ou orçamento. Esses domínios não foram implementados nesta fase.

Cada unidade tem código estável, nome, tipo, parent opcional, active, versão e timestamps.
Código é normalizado e único dentro do contrato, e fica imutável após criação. Renomear
altera somente o nome. Não há exclusão definitiva. Raízes físicas independentes são
permitidas; a listagem mostra parent e nível explicitamente, além da relação visual.

A matriz de combinação de parent/child é central no servidor. Empresa recebe os outros
tipos físicos; Filial e Unidade recebem unidades operacionais; Loja/CD recebem Depósito
ou Escritório; Depósito/Canteiro recebem Escritório; Escritório é folha. Unidade pode
receber outra Unidade, sem ciclos. Empresa não pode ser filha.

Unidade ativa exige parent e ancestrais ativos. Para inativar, resolver primeiro filhos
ativos e escopos de membership ativos dependentes. A interface mostra contagens reais
que o servidor consegue provar. Histórico e relações não são apagados.

## Módulos

Catálogo fechado: Compras (PROCUREMENT), Compras Internacionais/COMEX, Estoque,
Financeiro, Obras & Projetos e DataHub. Nenhum código livre enviado pelo navegador é
aceito como novo módulo.

Contratado e ativo são independentes. Ativo exige contratado. A configuração não
implanta um domínio operacional: a interface informa sua indisponibilidade real quando
não há implementação funcional. Ausência de configuração persistida é apresentada
como não contratado, versão 0; uma leitura não cria registros no banco.

Ativar um módulo não atribui TenantRole, capability ou concessão temporária. Financeiro
continua protegido; configurar FINANCE não autoriza o operador a consultar seus dados.
A política central combina capabilities, disponibilidade contratada/ativa e escopo de
entidade quando a operação os exige. Não existe autorização paralela baseada em menu.

PLATFORM_SUPPORT pode consultar somente metadados básicos de módulos. Não administra
estrutura, escopos de unidade ou módulos. APIs negam essas mutações diretamente.

## Concorrência, escopos e auditoria

Mutações usam expected_version e locks do contrato. Revalidação após locks impede
confirmar alteração quando contrato, sessão ou contexto perderam validade durante a
espera. Conflito 409 exige recarregar e revisar; o navegador não sobrescreve silenciosamente.

MembershipUnitScope associa somente memberships e unidades do mesmo tenant/contrato,
com FKs compostas e lifecycle sem delete. A API administrativa mínima usa a versão do
membership; unidades inativas/estrangeiras não são aceitas. Não existe gestão visual
completa desses escopos nesta fase. Uma operação que exija unidade nega ausência de
escopo explícito; isso não vira acesso global implícito.

Toda alteração e seu evento tipado de auditoria compartilham a transação. Falha na
persistência da auditoria impede a mutação. Before/after vêm do servidor, não do browser.
Runtime não recebe DELETE/TRUNCATE das novas tabelas de negócio; migrações são do owner.

## Extensões e limites de fase

O plano executável aprovado adia FeatureFlag, ContractParameter e
IntegrationConfiguration até existir um catálogo/consumidor concreto. Esta fase não
cria tabelas vazias, JSON arbitrário, editor universal, URL executável, scripts ou
conectores reais. Contexto, catálogo de capabilities e auditoria permanecem a base para
essas extensões futuras.

Nenhuma sessão de suporte, impersonação, Obra/Project, concessão Financeiro/Fiscal,
manutenção, reprocessamento, MFA ou Administrador do Cliente foi introduzido.

## Validação controlada

scripts/phase07_browser_fixture.py reutiliza a fábrica FastAPI e FakeEmailTransport
controlados das fases anteriores, somente com banco descartável atestado.
frontend/e2e/phase07.mjs executa browser real com React/FastAPI/PostgreSQL, sem mocks HTTP.
Dados sintéticos e credenciais de teste nunca entram em evidências, logs de payloads
ou configuração de produção. O gate completo e as evidências de execução ficam em
[phase-07.md](../superpowers/validation/hiatlas-platform/phase-07.md).
