# HiAtlas — Fundação de identidade, administração e suporte

Data: 22/09/2026
Status: APROVADA; Fase 1 revisada e aprovada, Fase 2 implementada e validada, aguardando revisão do usuário. Fases 3–11 não iniciadas.
Projeto: D:\Atlas
Origem: matriz e instruções fornecidas pelo usuário nesta tarefa.
Decisão de escopo do usuário: fundação completa, com backend e persistência reais.
Execução: fases pequenas e verificáveis, TDD e quality gate obrigatório por fase.
Plano: ../plans/2026-09-22-hiatlas-platform-foundation/README.md

## Ajustes aprovados em 22/09/2026

1. Suporte só associa perfis explicitamente support_assignable=true. Perfis
   administrativos, Financeiro/Fiscal e demais perfis sensíveis são inelegíveis,
   mesmo se houver tentativa de marcar a flag. Padrão da flag: false.
2. OrganizationNode usa WORKSITE/Canteiro quando necessário. Project/Obra é entidade
   do domínio Obras & Projetos e não será modelada pela organização.
3. Execução em fases pequenas com TDD e quality gate individual; não executar
   toda esta especificação como um único bloco.
4. Financeiro/Fiscal exige acesso temporário, explícito, justificado e auditado;
   seleção de contrato e papel de administrador não bastam.
5. Flags, parâmetros e integrações recebem somente infraestrutura necessária,
   sem CRUD genérico, editor de schemas ou gerenciador antes de um caso real.
6. Correções só usam handlers de domínio registrados e testados. São proibidas
   edição de tabela/coluna, SQL e payloads genéricos enviados pelo cliente.

## 1. Resultado esperado

Separar definitivamente a equipe interna da HiAtlas dos usuários das empresas
clientes. Administradores e suporte entram por identidade autenticada, selecionam
explicitamente um tenant/contrato e executam apenas ações permitidas no servidor.
A interface mantém empresa, contrato e ambiente visíveis durante todo o atendimento.

PLATFORM_ADMIN representa Administrador HiAtlas. PLATFORM_SUPPORT representa
Suporte HiAtlas. Nenhum dos dois é um perfil de cliente. Administrador do Cliente
fica reservado, sem conceder permissões ou criar esse perfil nesta entrega.

Esta especificação substitui, para este escopo, o conceito ambíguo de ADMIN dos
documentos antigos. O perfil demonstrativo administrador não será migrado
automaticamente para um administrador real.

## 2. Estado encontrado no repositório

- Frontend React/TypeScript com Vite, temas claro/escuro e testes Vitest.
- App.tsx aceita um perfil escolhido no navegador; não autentica uma identidade.
- LoginScreen.tsx contém credenciais explicitamente demonstrativas.
- workspace/catalog.ts mistura administrador com perfis operacionais.
- Workspace.tsx filtra amostras locais por nome de empresa; isso não é isolamento
  de dados real e não será reaproveitado como autorização.
- Backend FastAPI, SQLAlchemy, Alembic e PostgreSQL já previstos.
- A API atual oferece somente /api/health.
- Não foram encontradas entidades persistentes de identidade, tenant, contrato,
  auditoria ou operações, nem revisões de migração em backend/alembic/versions.
- Não foram encontrados arquivos AGENTS.md no projeto na inspeção.
- A árvore Git estava limpa no início da análise.

Os dados fictícios existentes não representam contas, contratos ou registros de
produção e não serão convertidos silenciosamente em dados reais.

## 3. Abordagem escolhida e alternativas

Recomendação: ampliar o monólito modular FastAPI existente, com sessões
persistentes no PostgreSQL, políticas centralizadas e frontend consumindo a API.
Isso permite revogação imediata e mantém auditoria e alterações na mesma transação.

Alternativa: provedor externo de identidade. É compatível com evolução futura,
mas exigiria escolher e configurar um serviço externo ainda não indicado.

Alternativa: JWT autossuficiente com roles e contratos no token. Evita algumas
consultas, mas acrescenta complexidade para revogar privilégios imediatamente.
Não será usado como fonte de autorização nesta fundação.

Não serão introduzidos microserviços, Redis ou um novo framework de frontend.

## 4. Limite da entrega

### Implementar nesta fundação

1. Login real, logout, sessão, senha com hash, convite e redefinição segura.
2. Usuários internos, usuários de clientes e seus vínculos separados.
3. Tenants, contratos e seleção explícita de contexto.
4. Catálogo de permissões, perfis de tenant e associação de usuários.
5. Portais de Administração HiAtlas e Suporte HiAtlas.
6. Gestão de usuários e status, inclusive bloqueio e inativação por contrato.
7. Configuração persistente de estrutura organizacional e módulos contratados;
   somente pontos de extensão mínimos para flags, parâmetros e integrações,
   sem cadastros ou gerenciadores genéricos antecipados.
8. Auditoria persistente, histórico de acesso e diagnósticos sanitizados.
9. Sessões de atendimento somente leitura e de manutenção autorizada,
   com expiração, encerramento e identidade do operador preservada.
10. Infraestrutura de correções administrativas e reprocessamentos por
    manipuladores explicitamente registrados, com auditoria e autorização.
11. Migrações, bootstrap seguro do primeiro administrador e testes de segurança.

### Dependências de módulos posteriores

Compras, estoque, COMEX, obras, cálculos financeiros/fiscais, importações e
integrações operacionais não possuem serviços persistentes neste repositório.
Esta entrega não implementa um ERP inteiro nem transforma amostras em operações.

A fundação fornecerá as políticas, contratos de serviço e registros de execução
necessários. Uma correção ou reprocessamento de negócio só ficará disponível
quando existir seu manipulador de domínio, com validação e testes. Ausência de
manipulador deve produzir indisponibilidade explícita, nunca sucesso simulado.

Não construir agora: painel agregado completo da Central de Operações, sistema
de chamados, MFA/2FA, regras fiscais, importadores genéricos ou conectores externos.
A referência de chamado é texto validado, sem integração com help desk.

## 5. Modelo persistente e limites

- User: identidade, e-mail normalizado único, nome, hash de senha e status global.
  Respostas públicas nunca incluem hash, tokens ou credenciais.
- PlatformRoleAssignment: relação interna separada de qualquer membership.
  Códigos aceitos: PLATFORM_ADMIN e PLATFORM_SUPPORT; um papel interno ativo
  por operador nesta fundação, sem acumular permissões por combinação.
- Tenant: organização contratante, identificador imutável e status.
- Contract: identificador, código único, tenant, ambiente e status.
  Um tenant pode possuir vários contratos; a seleção sempre inclui o contrato.
- Membership: usuário vinculado ao tenant/contrato, ativo/inativo e bloqueado
  como estados independentes, perfil de tenant e escopo de unidades.
  Status não são confundidos com senha.
- TenantRole e TenantRolePermission: perfil pertencente a um tenant/contrato;
  somente capacidades do catálogo de permissões de cliente. support_assignable
  começa false, e somente PLATFORM_ADMIN pode alterá-lo com auditoria.
  A elegibilidade exclui perfis administrativos, Financeiro/Fiscal e sensíveis;
  classificação explícita e capacidades do perfil são verificadas no servidor.
  Alterar permissões de perfil elegível exige revalidar essa restrição.
- OrganizationNode: empresa, filial, unidade, loja, CD, depósito ou WORKSITE/Canteiro,
  com vínculo ao contexto e hierarquia validada, sem ciclos ou pais externos.
  Não possui tipo PROJECT/Obra; Project pertence ao domínio Obras & Projetos.
- ContractModule: persistência dos módulos contratados e seu estado.
- FeatureFlag, ContractParameter e IntegrationConfiguration: pontos de extensão
  tipados e privados à aplicação, implementados somente quando necessários ao
  primeiro caso real. Não criar tabelas de payload livre ou endpoints genéricos.
  Integrações futuras referenciam segredos protegidos, sem retorná-los ao cliente.
- AuthSession: hash de token aleatório, usuário, expiração e revogação.
- AccessContext: identificador opaco ligado à sessão, operador, tenant/contrato,
  expiração e eventual sessão de atendimento.
- SupportSession: operador real, usuário visualizado, contexto, modo, motivo,
  chamado, expiração, escopo autorizado e encerramento.
- SecurityToken: hash do token, finalidade, destinatário, validade e consumo.
- EmailOutbox: entrega transacional e estado real de envio; conteúdo sensível
  protegido e eliminado após entrega ou expiração.
- AuditEvent e AccessEvent: eventos imutáveis de ações e acessos.
- ProcessingRun: diagnóstico sanitizado, manipulador, contexto, resultado e
  referência da execução original para reprocessamentos.

Chaves estrangeiras compostas e restrições devem impedir vínculos de perfil,
unidade, entidade ou contrato entre tenants diferentes. Identificadores UUID
não substituem as verificações de autorização.

## 6. Autenticação e ciclo de vida

- Senhas com hash Argon2id por biblioteca mantida, nunca criptografia reversível.
- Cookie de sessão HttpOnly, SameSite e Secure em produção; token aleatório
  armazenado apenas como hash no banco. Não guardar sessão no localStorage.
- Proteção CSRF nas mutações, inclusive entrada e saída de sessão, e validação
  de origem. Frontend/API sob mesma origem em produção e proxy local no Vite.
- Sessão com limite inicial de 30 minutos de inatividade e 8 horas absolutas;
  validação no servidor em toda requisição. Parâmetros configuráveis.
- Respostas de login/recuperação não revelam se um e-mail existe.
- Limitação persistente de tentativas por origem e identificador, sem depender
  apenas da memória de um processo e sem bloqueio global permanente por ataque.
- Senha redefinida, conta global bloqueada/inativada ou papel interno alterado
  revogam sessões e contextos afetados.
- Remoção de vínculo, alteração de perfil ou status de contrato invalida o
  acesso correspondente imediatamente, inclusive em sessões já abertas.
- Cliente não fornece roles, identidade do operador ou privilégios confiáveis.

Bootstrap: comando local de execução única cria o primeiro PLATFORM_ADMIN,
sem senha padrão, sem endpoint público e sem imprimir segredo. A senha é
informada de forma interativa protegida ou definida por convite seguro.
O comando registra o evento e recusa nova execução se já houver administrador.

Outros operadores internos são geridos por fluxo exclusivo de PLATFORM_ADMIN.
Promoção exige reautenticação recente e confirmação explícita vinculada ao alvo
e papel solicitado, registrada na auditoria. Impedir remoção/bloqueio do último
administrador ativo e a própria elevação de privilégio.

## 7. Convites, redefinição e status

- Usuário novo recebe convite de uso único, inicialmente válido por 24 horas.
- Redefinição usa token de uso único, inicialmente válido por 30 minutos.
- Reenvio invalida tokens anteriores da mesma finalidade e destinatário.
- Consumo atômico impede uso concorrente/repetido; tokens expirados falham.
- Somente o destinatário define a senha; suporte não recebe senha temporária
  nem vê links/tokens nas respostas da API ou telas.
- URLs usam origem configurada, sem confiar no cabeçalho Host da requisição.
  Páginas de token não carregam recursos de terceiros nem divulgam referer.
- E-mail por adaptador SMTP configurado no ambiente. Testes usam adaptador falso.
  Sem transporte configurado, a interface informa indisponibilidade; não
  afirma que a mensagem foi enviada.
- Outbox registra solicitação e entrega separadamente, com tentativas limitadas
  e cancelamento de mensagens cujo token tenha sido invalidado.
- Segredos da outbox são cifrados com chave externa ao banco; não entram em logs.

Suporte gerencia somente vínculos do contrato selecionado. Bloquear/inativar
um vínculo não bloqueia a identidade em outros contratos. Ativar não desbloqueia
implicitamente uma conta bloqueada; desbloquear não ativa vínculo inativo.

Suporte pode iniciar e-mail de redefinição para um usuário vinculado, mas não
alterar e-mail da identidade global, assumir contas ou gerenciar operadores.
Vincular uma identidade já existente depende de aceite pelo destinatário;
a pesquisa não expõe suas associações com outros clientes.

MFA permanece indisponível nesta etapa, sem botão que simule redefinição.

## 8. Contexto e autorização

Após autenticação interna, exibir lista pesquisável de empresas e contratos com
informações mínimas: nome, código, ambiente, status e módulos contratados.
Acesso aos dados depende de seleção explícita e criação de AccessContext.

Cada requisição de cliente leva o identificador opaco desse contexto; o servidor
confere sessão proprietária, operador, tenant, contrato, status e permissões.
Não aceitar apenas um tenant_id enviado livremente pelo navegador.

O contexto é por aba/fluxo, não uma variável global mutável da conta. Troca ou
encerramento limpa telas, cancela consultas pendentes e impede que respostas
antigas preencham o novo cliente. Sessões de atendimento não podem mudar de
cliente em silêncio; é necessário encerrá-las e selecionar novo contexto.

A política nega por padrão e avalia, nesta ordem:
identidade e sessão; contexto; papel e capacidade; membership e unidade quando
aplicável; módulo/feature; restrições de atendimento; necessidade de autorização
financeira ou de manutenção; pertencimento da entidade ao contrato.

Listas, buscas, detalhe, exportações, jobs e serviços seguem o mesmo isolamento.
Dados externos ao escopo retornam resposta que não revela a existência do objeto.
Menus ocultos são conveniência visual; cada ação é protegida novamente na API.

## 9. Matriz efetiva

| Capacidade | Administrador HiAtlas | Suporte HiAtlas |
|---|---|---|
| Listar e selecionar empresas/contratos | Sim | Sim |
| Consultar módulos e informações básicas | Sim | Somente leitura |
| Configurar módulos, flags, parâmetros e estrutura | Sim | Não |
| Criar/editar perfis e permissões de tenant | Sim | Não |
| Criar usuário/vínculo e enviar/reenviar convite | Sim | Sim, no contexto |
| Ativar/inativar/bloquear/desbloquear vínculo | Sim | Sim, no contexto |
| Iniciar redefinição de senha | Sim | Sim, por e-mail ao titular |
| Associar perfil existente do mesmo contrato | Sim | Somente support_assignable=true e não sensível |
| Atribuir papel interno | Fluxo exclusivo com confirmação | Não |
| Ver histórico de acesso e auditoria | Sim | Leitura sanitizada no contexto |
| Ver logs e falhas | Diagnósticos sanitizados | Subconjunto de suporte |
| Configurar integração e importação | Capacidade reservada; exige caso implementado | Não |
| Corrigir dado operacional | Ação autorizada e auditada | Não |
| Reprocessar operação registrada | Sim, autorizado e auditado | Não |
| Acessar Financeiro/Fiscal | Necessidade explícita registrada | Não |
| Atendimento somente leitura | Sim | Sim |
| Atendimento com manutenção | Motivo, chamado e ações autorizadas | Não |
| Ler senha, segredo ou token | Nunca | Nunca |
| Apagar auditoria | Nunca | Nunca |
| Hard delete de negócio | Não disponível por padrão | Não |

Suporte não pode atribuir FINANCEIRO/Fiscal, perfis administrativos ou sensíveis,
mesmo que existam no contrato. A lista de opções e o endpoint de associação
aplicam support_assignable=true e a política de sensibilidade no servidor.
Perfis internos não aparecem nem são aceitos nesse endpoint. Reduzir um perfil
sensível para outro perfil também exige administrador; gestão de status e
redefinição de acesso não concede autorização para alterar perfis protegidos.

## 10. Sessões de atendimento

Suporte pode visualizar o ambiente de um usuário vinculado ao contrato ativo,
com faixa permanente SESSÃO DE SUPORTE — SOMENTE LEITURA, empresa/contrato,
nome do usuário visualizado e botão de encerramento.

O operador continua sendo o autor real. Não há emissão de credencial da vítima,
troca de senha ou transformação da sessão em login do cliente.
As capacidades efetivas são a interseção das permissões do usuário visualizado,
módulos contratados e limites do suporte, excluindo Financeiro/Fiscal.

A API rejeita toda mutação pelo contexto somente leitura, inclusive chamadas
diretas. Encerrar a sessão é uma ação de controle permitida. Gestão de acesso
ocorre fora desse modo, após encerramento explícito.

Administrador também começa em somente leitura. Para manutenção autorizada,
exigir motivo, chamado/referência e lista explícita de ações/entidades permitidas,
com confirmação de sessão autenticada recentemente. Validade inicial: 30 minutos,
limitada também à validade da sessão principal. Isso não remove as demais regras.

Acesso administrativo Financeiro/Fiscal exige concessão temporária específica,
com justificativa registrada; não é ativado pela simples seleção do cliente.

## 11. Correção administrativa e auditoria

Fluxo: escolher uma operação de domínio registrada; consultar estado atual;
informar novo valor, motivo e referência; revisar antes/depois; confirmar.
Referência é opcional em correção administrativa direta e obrigatória em
manutenção autorizada, conciliando os dois fluxos descritos pelo usuário.

O servidor captura valor anterior, autor e horário; nunca confia nesses campos
vindos do navegador. A versão esperada detecta mudança concorrente e retorna
conflito para nova revisão. Não aceitar nomes de tabelas/colunas arbitrários,
SQL, código ou correção genérica de campos.

Correção e evento são gravados na mesma transação. Falha ao auditar aborta a
mutação. Cada manipulador aplica regras do domínio e autorizações necessárias;
manutenção não significa ignorar integridade de estoque, compras ou financeiro.

Evento: id, horário UTC, ator real, papel, tenant, contrato, ambiente, entidade,
id da entidade, ação, valores anteriores/novos permitidos, motivo, chamado,
resultado, request_id e sessão de atendimento quando houver.
Interface apresenta horário local com fuso explícito.

Credenciais e tokens são excluídos por schema e lista permitida de campos,
inclusive em diff, erros, auditoria, histórico, e-mail e processamento.

Auditoria não possui endpoints de edição/exclusão. Migrações usam identidade
de banco separada da aplicação; a aplicação não pode UPDATE/DELETE/TRUNCATE a
trilha. Verificar essa restrição em PostgreSQL, não apenas em testes simulados.
Eventos de autenticação/negação são registrados separadamente quando não existe
uma transação de negócio bem-sucedida.

Listagem paginada e filtrada; suporte recebe projeção restrita que omite valores
operacionais sensíveis, payloads, stack traces e informações Financeiras/Fiscais.
Isso preserva consulta de auditoria sem ampliar o acesso aos dados do cliente.

## 12. Manutenção, jobs e integrações

Diagnósticos usam códigos e mensagens sanitizadas, sem logs brutos de infraestrutura.
Reprocessamento recebe id de execução do mesmo contexto e manipulador conhecido.
Exigir justificativa, idempotência, controle de concorrência e novo evento de
auditoria; suporte não pode disparar a ação nem por chamada direta.

O ponto de extensão de integração exige tipo e parâmetros conhecidos; não permite
executar código, enviar requisições para URL arbitrária ou consultar segredos.
Não haverá CRUD genérico de integração, flag ou parâmetro nesta fundação.
Importadores/conectores reais serão registrados ao implementar cada domínio.
Até lá, a interface informa que não há operações disponíveis.

## 13. Interface e fronteiras de código

Backend:
- identity: autenticação, sessões, convites, outbox e bootstrap.
- platform: operadores internos e política de capacidades.
- tenancy: tenants, contratos, memberships e contextos.
- organization: estrutura, módulos e parâmetros.
- audit: eventos, projeções e histórico de acesso.
- support: sessões de atendimento e escopo de manutenção.
- maintenance: registro de manipuladores e execuções.
- api: schemas e rotas finas, delegando transações aos serviços.
- db e alembic: modelos, constraints, migrações e privilégios.

Frontend:
- auth: login, convite, redefinição e sessão corrente.
- api: cliente HTTP, CSRF, erros e cancelamento de consultas.
- platform: seleção de contrato e áreas Administração/Suporte.
- tenancy: cabeçalho de contexto e associação de perfis.
- support: faixa de atendimento e encerramento.
- audit: consulta paginada e detalhes autorizados.
- workspace: acesso do usuário cliente conforme capacidades da API.

Manter componentes focados, tema, acessibilidade e identidade visual existentes.
Não concentrar as novas regras em Workspace.tsx ou duplicar a política de
segurança como fonte independente no frontend.

Administração: Configuração do contrato, Usuários, Perfis, Estrutura, Módulos,
Auditoria e Manutenção. Parâmetros, flags e integrações não recebem gerenciadores
nem formulários genéricos; aparecem como indisponíveis quando não houver caso real.
Suporte: pesquisa contextual, usuários, ações de acesso, histórico e diagnósticos.
A lista global pode ajudar a localizar usuário, mas revela apenas dados mínimos;
detalhes e ações exigem seleção explícita do contrato.

O login real não oferece seleção de privilégio. A demonstração fica separada,
explicitamente identificada, desabilitada por padrão e sem usar APIs reais.
Não exibir métricas fictícias ou registros de amostra no workspace autenticado.
Módulos ainda sem backend mostram seu estado real de indisponibilidade.

## 14. Erros e operação

- Não autenticado: 401; sessão limpa na interface.
- Capacidade negada: 403.
- Contexto ausente/expirado: erro identificado e retorno à seleção.
- Objeto fora do escopo: 404.
- Versão divergente/último administrador: 409.
- Validação de entrada: 422.
- Transporte ou manipulador indisponível: erro explícito, sem falso sucesso.
- Tentativas limitadas: 429 com orientação de nova tentativa.
- Falha interna: mensagem pública sanitizada e request_id.

Configuração por variáveis de ambiente; exemplos sem segredos. Produção recusa
configuração insegura, credenciais padrão, cookies inseguros e modo demo.
Documentar migração, bootstrap, SMTP, chave da outbox, origem pública, HTTPS,
execução do worker e permissões de banco. Não implantar nem enviar mensagens a
destinatários reais durante testes.

## 15. Verificação e critérios de aceite

Testes de API exercitam duas empresas e ao menos dois contratos da mesma empresa.
Não basta verificar funções de política isoladas.

1. Login real não aceita escolher papel; senha e hash nunca são serializados.
2. Falta de sessão/contexto impede qualquer consulta a dados do cliente.
3. Troca de ids, contextos de outra sessão e referências de outro contrato falham.
4. Suporte não altera contrato, perfil, flags, financeiro, integração ou negócio.
5. Associação aceita só perfis existentes do contrato e rejeita papéis internos.
   Suporte exige support_assignable=true e perfil não sensível; manipular flag,
   renomear perfil ou alterar permissões não contorna a restrição.
6. Bloqueio/inativação de vínculo não afeta outro contrato; revogação é imediata.
7. Convites/redefinição expiram, são de uso único e resistem a consumo concorrente.
8. Redefinição não vaza existência de conta, senha ou token; outbox não afirma
   entrega quando houve falha.
9. Sessão somente leitura rejeita mutações diretas e não expõe Financeiro/Fiscal.
10. Manutenção exige motivo/referência, expira e restringe ações e entidades.
11. Correção registrada gera antes/depois no servidor, detecta conflito e reverte
    se a auditoria falhar. Teste usa manipulador controlado, sem inventar domínio.
12. Perfil interno exige confirmação/reautenticação e protege último administrador.
13. UPDATE/DELETE/TRUNCATE de auditoria falham com o usuário de banco da aplicação.
14. Reprocessamento preserva contexto, autoria e idempotência.
15. Navegação mantém contexto visível; respostas antigas não vazam entre clientes.
16. Financeiro, logs e diffs são redigidos conforme papel e autorização temporária.
17. Reiniciar API mantém usuários, contratos, eventos, revogações e filas.
18. Frontend passa testes, lint e build; backend passa pytest e Ruff;
    migrações e constraints são verificadas em PostgreSQL.
19. WORKSITE é aceito na organização; PROJECT/Obra é rejeitado.
20. Sem editores genéricos de flags, parâmetros, integrações ou dados de negócio.
21. Cada fase exige evidência RED/GREEN, regressões, revisão e quality gate antes
    de avançar; teste ignorado por falta de infraestrutura não significa aprovado.

A entrega deve informar quais controles foram efetivamente exercitados e qualquer
dependência operacional ainda não configurada. Sem SMTP/PostgreSQL disponíveis,
não declarar validados envio real ou persistência de produção.

## 16. Sequência proposta

1. Banco, migrações e auditoria imutável.
2. Identidade, sessão, bootstrap e operadores internos.
3. Contextos de contrato, RBAC e elegibilidade de perfis.
4. Interface autenticada e isolamento da demonstração.
5. Convites, redefinição e ciclo de vida de acesso.
6. Gestão visual de usuários, perfis e consulta de auditoria.
7. Organização com WORKSITE e módulos contratados.
8. Atendimento somente leitura.
9. Concessões temporárias Financeiro/Fiscal e manutenção.
10. Handlers de correção e reprocessamento controlados.
11. Validação integrada e documentação operacional.

Cada fase encerra no seu quality gate; não executar o conjunto como um bloco.
Flags, parâmetros e integrações usam contexto, catálogo e auditoria existentes;
não criar abstrações sem consumidor só para antecipar o futuro.

O plano executável está separado em fases no documento vinculado no cabeçalho,
com arquivos, testes de aceite, dependências e gates por etapa. Nenhuma fase foi
executada pela aprovação arquitetural. Esta especificação não representa
funcionalidades já implementadas.

## Ajustes finais aprovados para execução da Fase 1

Cabeçalho contextual: `X-HiAtlas-Context`. AccessContext por aba em memória ou
sessionStorage; jamais localStorage para sessão/contexto autenticado. Manter uv,
confirmado como gerenciador canônico, sem migração de ferramenta.

Privilégios por categoria de tabela: dados de negócio não admitem DELETE/TRUNCATE
pelo runtime; auditoria/acessos também não admitem UPDATE. Tabelas técnicas usam
somente privilégios necessários e explicitamente definidos para seu ciclo de vida.

Fase 11 deve documentar/testar recuperação administrativa break-glass: operação
local restrita, identidade alvo verificada, motivo/referência, confirmação e
revogação de sessões, com auditoria atômica. Sem endpoint público, senha padrão,
logs de segredo ou bypass se a auditoria falhar. Não implementar isso na Fase 1.

Autorização atual: somente Fase 2 — identidade, sessão, bootstrap e operadores
internos; quality gate, evidências e commit. Parar para revisão antes da Fase 3.
Não antecipar RBAC completo, contexto tenant/contrato ou portais das Fases 3/4.
