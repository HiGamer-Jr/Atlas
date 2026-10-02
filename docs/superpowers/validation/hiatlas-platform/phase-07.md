# Fase 7 — Estrutura organizacional, WORKSITE e módulos contratados

## Identificação e escopo

- Branch: `feat/hiatlas-platform-phase-7`.
- Base aprovada da Fase 6: `ef9d080`.
- Commit de implementação: `d7dc2e16bb749cf342a1f672e2751771d68a3bfd`.
- Commit final desta evidência: consultar `git log -1 --format=%H` nesta branch.
- Execução iniciada em 2026-10-01 e retomada em 2026-10-02. Somente Fase 7; sem deploy, merge ou Fase 8.

## Entrega e schema

OrganizationNode persistente tem tenant/contrato, parent opcional, oito tipos físicos,
code estável e imutável após criação, name, active, version e timestamps. WORKSITE é
canteiro físico; PROJECT é rejeitado. Raízes opcionais formam uma floresta física.
Matriz central de parent/child, unicidade contextual, FKs compostas e revalidação após
locks protegem referências e ciclos. Inativação preserva histórico e rejeita filhos
ativos e escopos ativos dependentes.

ContractModule usa catálogo fechado PROCUREMENT, COMEX, INVENTORY, FINANCE, PROJECTS e
DATAHUB. Contratado e ativo são distintos; ativo exige contratado. Ausência projeta
versão zero sem escrever no GET. Configurar FINANCE não concede dados financeiros.
Nenhum módulo operacional foi implementado: operational_available permanece falso,
e a política central nega acesso funcional indisponível.

MembershipUnitScope dispõe de API administrativa mínima, FKs compostas, lifecycle e
versão do membership; a gestão visual completa fica para uma fase posterior.
FeatureFlag, ContractParameter e IntegrationConfiguration permanecem adiados conforme
a tarefa 7.2 do plano executável aprovado: não há consumidor ou catálogo concreto nesta
fase. Não foram criadas tabelas vazias, configurações arbitrárias ou conectores.

Migração `0006_organization_modules` sucede `0005`. Owner separado executa DDL; runtime
recebe apenas SELECT/INSERT/UPDATE nas três tabelas novas, sem DELETE/TRUNCATE. Auditoria
continua protegida. Testes físicos verificam SQLSTATE 23503, 23514, 23505 e 42501,
upgrade/downgrade/upgrade e guard de identidade antes do DDL.

## RED/GREEN e concorrência

| Caso | RED executado | Correção e GREEN executado |
| --- | --- | --- |
| Fundação organização/módulos/schema | 32 falhas, 1 passou: APIs/tabelas ausentes | 33 passaram |
| Códigos com hífen, COMEX e política central | 7 falhas | 21 passaram; ordenação hierárquica ainda identificada como RED |
| Parent antes de descendentes | 1 falha; primeira CTE teve 3 erros de tipo de array PostgreSQL | CTE contextual com cast para text; suíte focada final cobre árvore |
| Auditoria: pairing ação/snapshot | 4 tipos incorretos aceitos | Schemas fechados por ação; rollback e projeções sanitizadas verificados |
| Código de módulo explicitamente vazio | DID NOT RAISE | Default somente para None; vazio/desconhecido negados |
| Pesquisa por nome válido de 200 caracteres | 422 | Bound alinhado ao cadastro; consulta retorna o registro |
| Menus e componentes reais | 16 falhas iniciais | Componentes integrados ao contexto real |
| Foco ao fechar diálogo com trigger desabilitado | 1 falha | Retorno seguro ao detalhe; teclado testado |
| 403 seguido de retry 503 | 2 falhas | Dados protegidos descartados antes do retry |
| Sincronização do detalhe após 409 | 1 falha: nome antigo | Estado e versão atualizados após GET bem sucedido |
| 409 na criação e parent carregado com detalhe pendente | 2 falhas | Draft editável e controles bloqueados até sincronização |
| Validade HTML dos códigos com hífen | 3 falhas | Campo compatível com código validado pelo servidor |

Uma falha no teste de auditoria usava uma rota antiga inexistente; foi corrigida no
próprio teste e não é contada como defeito do produto. Import grouping do Ruff foi
corrigido; não houve alteração de dependências.

Onze testes de corrida usam conexões PostgreSQL independentes: duas reparentagens que
formariam ciclo; mesma versão de nó; inserção inicial e mesma versão de módulo; contexto
expirando após locks de parent/nó/módulo/membership; contrato inativado enquanto nó,
módulo e escopo aguardam lock. Efeito não autorizado e auditoria não persistem.
Matriz completa de 64 combinações parent/child e limites de escopo também são testados.

## Execuções

- Backend completo do implementador: 397 passaram, zero skips, 270,60 s, antes do último ajuste isolado da pesquisa.
- Backend focado após esse ajuste: 63 passaram, zero skips, 48,21 s.
- Frontend completo do implementador: 185 passaram, 12 arquivos; 29 testes novos focados.
- Gate integrado final do controlador: PASS, exit 0; backend 398 passaram, zero skips, 254,84 s; frontend 185 passaram em 12 arquivos, 12,47 s; Ruff, oxlint sem avisos/erros, TypeScript/Vite build e diff checks aprovados.
- E2E real do controlador: PASS, exit 0; Administração, Suporte e A/A2/B.

Comando do gate: `scripts/check-platform-foundation.ps1`, ambiente controlado fornecido
sem imprimir valores. Executa pytest completo, Ruff, Vitest completo, oxlint,
TypeScript/Vite build e diff checks. PostgreSQL descartável real 18.6, owner/runtime
separados, sem SQLite. Nenhum skip obrigatório pode substituir execução.

E2E: `node e2e/phase07.mjs` a partir de frontend, fábrica FastAPI controlada,
React/Vite HTTPS e Chrome headless. FakeEmailTransport, sem destinatário real, mocks HTTP
ou conectores externos. A fábrica reutiliza somente identidades sintéticas e a fundação
aprovada; estrutura e módulos são criados via API/UI reais.

## Revisão independente

Backend e frontend foram revisados por agentes distintos dos implementadores, em
inspeção estática de fontes/testes/evidências. Os revisores não repetiram banco, E2E ou
suítes completas, e esses resultados não são atribuídos à revisão.

Frontend: três achados P2 reproduzidos e corrigidos (sincronização comentada do detalhe,
409 de criação preso no refresh e parent habilitado antes do detalhe). Reavaliação
fechou todos; correção de hífens também inspecionada. Backend: revisão e reavaliações de
módulo vazio e pesquisa200 sem achados remanescentes. Escopo: referências cruzadas,
ciclos, WORKSITE versus Project, module gating/Financeiro, grants, atomicidade e versões.

## Riscos e limites

- Não existem domínios operacionais de Compras/COMEX/Estoque/Financeiro/Obras/DataHub nesta fase; configurar módulo não simula disponibilidade.
- Escopos de unidade têm infraestrutura backend, sem gestão visual completa.
- Flags, parâmetros e integrações dependem de consumidor/catálogo concreto posterior.
- Locks por contrato priorizam integridade; não foi executado benchmark de carga.
- E2E executado em Chrome headless e teclado básico; não representa uma matriz completa de leitores de tela/navegadores.
- Warning herdado de Starlette/TestClient/httpx foi observado, sem alteração de dependências.
- Limpeza confirmada: FastAPI/Vite/PostgreSQL encerrados, portas controladas fechadas; banco/cluster descartável, credenciais/chaves/certificados/logs temporários e scratch removidos. Worktree preservada para revisão.

Veja também o [manual de organização e módulos](../../../operations/hiatlas-organization-modules.md).

## E2E e capturas inspecionadas

O fluxo Admin criou Empresa/Filial/CD/Loja/WORKSITE, editou e inativou o canteiro,
rejeitou ciclo e PROJECT, ativou módulo e constatou indisponibilidade operacional,
inativou com edição concorrente real e exibiu 409, e verificou auditoria persistida.
Suporte leu os módulos sem controles administrativos; POST de estrutura, GET de
estrutura e PATCH de módulo manuais receberam 403. A/A2/B: pesquisa vazia, detalhe,
edição, parent estrangeiro, module_id estrangeiro e auditoria de outro contrato
rejeitados/ocultos. Headers contextuais, ausência de requests externos/pageerrors e
storage restrito a tema/id opaco existente foram verificados.

O primeiro ensaio parou porque o harness tentou focar o botão durante loading;
click trial passou a aguardar sua disponibilidade antes de Enter. Isso foi um ajuste
de sincronização do teste, sem alteração do produto. O ensaio seguinte passou.
Capturas de auditoria foram filtradas por ação organizacional para não registrar ids
de AccessContext. A repetição final comprova esse ajuste de evidência.

Capturas reais inspecionadas: hierarquia com parent/nível explícitos, estados por texto,
labels comerciais, contraste claro/escuro, confirmação contextual, 409, Suporte somente
leitura e mobile 390×844 sem overflow. Teclado: foco em campo, Tab, Enter e Escape com
retorno ao trigger. Não foi executada auditoria completa de acessibilidade.

- [Estrutura Admin clara](phase-07-visual/admin-structure-light.png), [escura](phase-07-visual/admin-structure-dark.png), [mobile](phase-07-visual/admin-structure-mobile.png).
- [Módulos Admin](phase-07-visual/admin-modules-light.png), [mobile](phase-07-visual/admin-modules-mobile.png).
- [Confirmação contextual](phase-07-visual/admin-inactivation-confirmation.png), [conflito 409](phase-07-visual/admin-module-conflict.png).
- [Suporte claro](phase-07-visual/support-modules-light.png), [escuro](phase-07-visual/support-modules-dark.png), [mobile](phase-07-visual/support-modules-mobile.png).
- [Auditoria contextual clara](phase-07-visual/admin-audit-light.png), [escura](phase-07-visual/admin-audit-dark.png).

## Rastreabilidade da revisão

- [Revisão independente backend e reavaliações](phase-07-review-backend.md).
- [Revisão independente frontend e reavaliação](phase-07-review-frontend.md).

Arquivos de produto, testes, migração, harness e capturas integram o commit de
implementação acima. O commit seguinte contém esta evidência e o fechamento do plano;
seu hash final é identificável por git log da branch, sem autorreferência impossível.
O gate completo foi executado no mesmo conteúdo de produto. Após o gate, somente o
harness recebeu esperas/filtro de captura, comprovados pelo E2E repetido com exit 0,
node --check e oxlint final. Nenhuma mudança funcional posterior exige nova suíte.

## Encerramento

- PostgreSQL recebeu shutdown fast por pg_ctl e confirmou server stopped.
- Verificações posteriores confirmaram ausência dos processos/portas controlados.
- Raízes absolutas foram verificadas antes da remoção recursiva; somente temporários desta fase foram removidos.
- Relatórios de revisão foram preservados acima antes de remover scratch.
- Produto e evidência commitados nesta branch; git status --porcelain deve estar vazio no encerramento.
- Sem deploy, push, merge automático ou início da Fase 8. Parada obrigatória para revisão do usuário.
