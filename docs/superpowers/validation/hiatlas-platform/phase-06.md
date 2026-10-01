# HiAtlas — Evidências da Fase 6

Data: 2026-10-01. Escopo: Gestão contextual de Usuários, Perfis e Auditoria.
Fases 1–5 aprovadas pelo usuário. Somente a Fase 6 foi executada nesta rodada.

## Branch, base e commits

- Branch: `feat/hiatlas-platform-phase-6`.
- Base aprovada: `6600b96` (Fase 5).
- Worktree preservada: `D:\Atlas\.worktrees\hiatlas-platform-phase-1`.
- Implementação, testes, harness, manual e capturas: `80dfbb8d44d8252424e9bb4f9de9c3323fbb4bba`.
- Ajuste final de leitura mobile e capturas atualizado no commit `a357af5.
- O commit documental que contém este relatório fecha a fase; seu identificador pode ser consultado por `git log -1 -- docs/superpowers/validation/hiatlas-platform/phase-06.md`.
- Os dois commits de implementação previstos no plano foram consolidados em um commit revisável. A execução consolidou regressões backend em `test_phase6_access.py` e frontend em `AccessPages.test.tsx`, reutilizando também os testes anteriores e `AuthenticatedApp.test.tsx`.

## Entrega e políticas

Administração: Usuários, Perfis e Permissões, Auditoria. Suporte: Usuários e Histórico.
Empresa, contrato e ambiente aparecem no cabeçalho sticky e nas confirmações.
As listas são reais, filtradas/paginadas no servidor, sem usar dados demo.
Detalhe distingue identidade global mínima de flags/perfil/convite do vínculo atual.

Criar vínculo, reemitir convite e iniciar reset reutilizam tokens/outbox da Fase 5.
A UI apresenta solicitação registrada e situação persistida de entrega; não declara
SMTP enviado ao receber apenas accepted. Não há senha temporária, token ou URL secreta
na resposta de gestão. Nenhuma lista, capability ou auditoria é persistida no navegador.
O sessionStorage continua reservado ao identificador opaco do AccessContext.

Membership mantém active e blocked independentes. Mudanças têm expected_version,
revalidação após locks e auditoria na mesma transação. Bloqueio/inativação cancelam
os tokens e mensagens pendentes vinculados ao membership, sem afetar outros contratos.
Reset contextual entrega/consumo revalida o vínculo e sua elegibilidade vigente.

TenantRole recebe descrição e quantidade comprovada de vínculos. support_assignable
começa false. Atribuição pelo Suporte reavalia classificação, capacidades, estado e
sensitivity_locked; remover uma capacidade ou renomear um perfil não limpa seu histórico
sensível. PLATFORM_ADMIN/PLATFORM_SUPPORT continuam papéis internos separados.

Capacidades reutilizadas: memberships.read, users.create, users.invite, users.status,
users.password_reset, roles.read, roles.assign, roles.manage,
roles.support_assignable.manage, audit.read e logs.access.read. Os grants internos
foram cobertos por regressão; não foram criados códigos quase duplicados.
Ver [manual contextual](../../../operations/hiatlas-contextual-access.md).

Auditoria filtra tenant e contrato antes de paginação/projeção. Cursor valida seu
contexto e tem ordenação estável por data/id. Suporte recebe allowlist própria do
backend, sem snapshots ou motivo livre. Admin recebe somente snapshots tipados e
permitidos; dados Financeiro/Fiscal/sensíveis permanecem redigidos. Referência e motivo
livres retornam null conservadoramente. Ator sensível não é identificado ao Suporte.
Histórico é do vínculo atual. last_access_at usa somente SUCCESS context.selected com
ator, tenant, contrato e entidade access_context exatos; nunca infere login global.

## Migração e PostgreSQL real

Migração incremental `0005` em `0005_role_description.py`, parent `0004`:
coluna description não nula, com default vazio; sem registros fictícios de produção.
Guardas de owner/runtime distintos, runtime informado e ausência de superuser são
verificadas antes do DDL. Regressões provam que a coluna não é criada quando a guarda falha.

Foi utilizado PostgreSQL **18.6**, distribuição portátil oficial EDB, descartável,
loopback na porta 55486. Banco de teste atestado por marker; owner e runtime distintos,
sem superuser. pytest usou URLs de owner/runtime reais, com reset explicitamente
habilitado apenas para esse banco. Nenhum SQLite ou banco de produção foi utilizado.
Não houve skip obrigatório. Credenciais e material de teste ficaram fora do Git.

Fixture E2E: `scripts/phase06_browser_fixture.py`, reaproveitando a fábrica controlada
da Fase 5 e **FakeEmailTransport**. Nenhum destinatário real ou SMTP externo recebeu
mensagens. A leitura da mensagem fake ocorre somente em pipe para o navegador; o
harness suprime diagnósticos sensíveis e não imprime links, payloads ou credenciais.
O banco foi reconstruído entre o gate e os E2Es para manter exclusividade dos testes.

## RED / correção / GREEN

| Comportamento | RED observado | GREEN observado |
|---|---|---|
| Grants existentes para gestão contextual | 1 teste falhou por grants ausentes | 1 passou |
| APIs/projeções/listas/isolamento e locks iniciais | 10 falhas / 8 passes; duas falhas de binding da fixture foram corrigidas antes de confirmar 404 de rotas ausentes | checkpoint 104 testes, 71,52 s |
| Cancelar reset contextual após bloqueio | 1 falha: token seguia válido | regressão incluída na suíte completa |
| Evidência contextual, conclusão de reset, entrega vigente e ator sensível | 4 falhas esperadas | 49 testes token/outbox/Fase 6, 35,32 s |
| Expiração durante locks dependentes | 2 falhas: convite/edição ainda confirmavam após expiração | 28 testes Fase 6, 19,88 s |
| Guardas da migração incremental | 3 falhas: owner/runtime inseguro era aceito | 7 testes de migração, 2,17 s |
| Fluxos e projeções iniciais React | 12 falhas esperadas | 12 focados; suíte depois ampliada |
| Recuperação de conflito 409 | 1 regressão falhou | checkpoint 25 focados |
| Revisão independente: refresh 503 reabilitava versão antiga; flag histórica true não podia ser removida | 2 reproduções independentes falharam | 51 testes independentes em 3 arquivos, 9,07 s |
| Classificação de perfil em português | 1 falha por enum técnico visível | suíte completa ampliada |
| Nome acessível do select nativo Perfil | E2E não encontrava rótulo exato; 1 teste novo falhou | 156 frontend e E2E reais |
| Leitura mobile do histórico e da lista carregada | capturas mostraram colunas comprimidas; duas regressões E2E de largura mínima falharam no estágio mobile | E2E completo passou com tabelas legíveis/rolagem interna; teclado ArrowRight moveu o histórico |

As regressões permanentes estão nos testes versionados. Fontes transitórias dos
revisores foram removidas após consolidar os achados. Uma colisão de descoberta com
teste transitório removido durante uma execução frontend não foi considerada PASS;
a suíte estável foi executada novamente. Um acionamento E2E com cwd incorreto falhou
no startup e também não foi considerado validação; a execução correta ocorreu em frontend.

## Concorrência, atomicidade e isolamento

Testes reais em conexões PostgreSQL distintas cobrem:

- Dois admins alterando o mesmo membership: somente uma alteração aceita, outra 409.
- Perfil tornando-se sensível e support_assignable removido antes da atribuição:
  Suporte recebe negação; somente o efeito autorizado gera auditoria.
- Membership bloqueado antes de convite/reset: nenhuma nova mensagem elegível.
- Contexto expirando ao aguardar membership, perfil e locks dependentes:
  rollback de mutação, auditoria e outbox.
- Falha na auditoria impede commit; regras de atribuição e ciclo de vida anteriores
  continuam cobertas pelo pytest completo.
- Concorrência de consumo de token e worker da Fase 5 foi mantida na regressão completa.

Fixtures explícitas: Tenant A com Contract A e A2; Tenant B com Contract B; mesma
identidade global com vínculos distintos. Lista, busca por nome/e-mail, contagens,
role assignment, detalhe, cursor, auditoria e histórico permanecem contextuais.
Ids válidos externos não revelam registros. Bloquear/inativar A preserva B.
As combinações active/blocked e sensibilidade histórica foram verificadas nas suítes.

## Quality gate executado

Comando integrado: `scripts/check-platform-foundation.ps1`, após preparar o banco
descartável atestado. Execução final integrada retornou **exit 0**:

| Verificação | Resultado executado |
|---|---|
| Backend pytest completo | **335 passed**, zero skips, 165,85 s |
| Ruff backend app/tests/alembic | PASS, All checks passed |
| Frontend Vitest completo | **156 passed**, 10 arquivos, 11,77 s |
| oxlint | PASS |
| TypeScript + Vite build | PASS |
| git diff --check / staged diff | PASS |

Após a correção visual mobile, backend não sofreu novas alterações. O gate integrado foi repetido na árvore final com os resultados acima. Frontend completo
foi repetido: **156 passed**, 10 arquivos, 12,55 s; oxlint e TypeScript/Vite repetidos
com exit 0. O E2E completo foi repetido com a nova regressão mobile e teclado.
Ao adicionar arquivos novos ao índice, diff --cached --check detectou linhas vazias
extras no EOF; foram removidas, e o check passou antes do commit. Nenhuma alteração
funcional ocorreu nessa normalização. Um warning preexistente Starlette/httpx permanece.

## E2E real — Admin e Suporte

Comando: `node e2e/phase06.mjs`, executado dentro de frontend com ambiente controlado.
Chrome headless real, HTTPS local, React/Vite real, FastAPI real e PostgreSQL real.
Sem mocks HTTP. Todas as execuções finais abaixo passaram (exit 0):

- Admin: login → selecionar CTR-A → usuários reais; paginação com 23 memberships
  sintéticos; filtro; Novo usuário → revisão → vínculo pendente → entrega fake →
  aceite público real → ativo; trocar perfil → bloquear → desbloquear → auditoria.
- Perfis: criação; edição; conflito real entre edição aberta e PATCH concorrente
  via API → 409 visível; recarregar versão vigente; alterar support_assignable;
  remover flag true histórica de Financeiro sem torná-lo elegível nem limpar lock.
- Suporte: login → CTR-A → localizar usuário → criar pendente → reenviar convite →
  iniciar reset → atribuir perfil elegível. Financeiro/Diretoria ausentes nas opções;
  chamada manual de atribuição sensível e criação de TenantRole recebem 403.
- Histórico Suporte: projeção não contém before/after, reason ou ciphertext.
- A/A2/B: trocar contrato, pesquisar identidade de A retorna vazio; consultar
  membership/audit de A fora de A dá 404; atribuir role A a vínculo A2/B dá 404.
- Temas light/dark em Admin/Suporte; desktop e mobile 390×844; página sem overflow
  horizontal externo, tabelas mobile de histórico e usuários com colunas legíveis e rolagem interna.
- Teclado: abrir modal, Tab para e-mail, Escape e restauração de foco; navegação de
  menu; foco visível na região de eventos e ArrowRight efetivamente rola a tabela.
- Contexto visível nos diálogos e header; chamadas de gestão levam contexto;
  nenhum recurso externo, pageerror ou dado de negócio em storage foi detectado.

## Revisão independente

Backend: revisão independente estática dos serviços/policies/projeções/migração e
testes. Achado P2: consumo de reset contextual perdia associação com o membership
na auditoria. Corrigido com origem explícita do token e regressão RED/GREEN; reset
público permanece global. Rerevisão cobriu evidência contextual, cancellation,
revalidação após locks, ator sensível e guardas de migração. **Sem achados acionáveis
pendentes**. Revisor não executou banco/suíte; esses resultados são do gate root.

Frontend: revisão independente gerou duas reproduções RED para conflito/refresh e
flag histórica. Correções e reproduções originais passaram na execução independente
**51/51**, incluindo providers reais de sessão/contexto com HTTP mockado. Rerevisões
estáticas de nomes acessíveis e tabelas mobile: sem novos achados. Testes de sessão
401/contexto 403 removem dados, diálogo e contexto, retornando ao fluxo autorizado.
A revisão não substitui o E2E root nem afirma execução própria de PostgreSQL/browser.

## Capturas sanitizadas

Capturas contêm somente fixtures sintéticas e ids de referência não secretos.
Nenhuma captura de página com token antes do consumo foi versionada. Inspeção visual
root: confirmação desktop clara, auditoria desktop escura, histórico mobile escuro
após correção; lista mobile e cabeçalho. O E2E verificou ambos os temas por execução.

- [Admin usuários](phase-06-visual/admin-users-light.png)
- [Convite pendente](phase-06-visual/admin-pending-invite.png)
- [Confirmação contextual de bloqueio](phase-06-visual/admin-block-confirmation.png)
- [Perfis](phase-06-visual/admin-roles-light.png)
- [Conflito de versão](phase-06-visual/admin-version-conflict.png)
- [Auditoria clara](phase-06-visual/admin-audit-light.png) / [escura](phase-06-visual/admin-audit-dark.png)
- [Convite aceito, sem token](phase-06-visual/invite-accepted.png)
- [Suporte histórico claro](phase-06-visual/support-history-light.png) / [escuro](phase-06-visual/support-history-dark.png)
- [Suporte histórico mobile](phase-06-visual/support-mobile.png)
- [Suporte usuários mobile](phase-06-visual/support-users-mobile.png)

## Riscos e limites

- O lock global de ciclo de vida herdado da Fase 5 serializa operações de acesso.
  A recuperação neutra inclui atraso de 250 ms; SMTP lento pode ampliar espera.
  Não foi executado benchmark de carga ou infraestrutura distribuída nesta fase.
- Último acesso significa seleção contextual comprovada; tentativas/login globais
  sem vínculo de contrato não são expostos nem inferidos como histórico local.
- Motivo/referência livres são null conservadores, e snapshots sensíveis permanecem
  redigidos. Concessão Financeiro/Fiscal e diagnóstico completo não foram antecipados.
- SMTP de produção não foi acionado. O E2E prova entrega fake e fluxo real da aplicação;
  indisponibilidade/retry/transporte são cobertos pela regressão completa da Fase 5.
- Navegador utilizado: Chrome headless. Não foi executada matriz multibrowser ou
  validação integral com leitores de tela. Teclado, foco, nomes e mobile básicos foram executados.

## Encerramento

Implementação e documentação commitadas; worktree preservada limpa para revisão.
Serviços temporários FastAPI/Vite/PostgreSQL encerrados; diretório de teste, banco,
credenciais, chaves e logs temporários removidos após as verificações.
Sem deploy, push ou merge automático. Nenhum hard delete de negócio, TenantAdmin,
MFA, impersonação ou funcionalidade das Fases 7–11 foi introduzido.
**Parada obrigatória para revisão do usuário; Fase 7 não iniciada.**
