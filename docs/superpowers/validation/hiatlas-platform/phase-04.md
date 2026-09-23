# Fase 4 — Interface autenticada real e seleção de contrato

Data: 23/09/2026. Base aprovada: `c8cb6d9`.
Branch preservada: `feat/hiatlas-platform-phase-3`.
Commit da implementação validada: `3df1a4861c334998acf225cded3e635834833377`.
Este relatório e a atualização de status constituem o commit documental seguinte.
Worktree: `D:\Atlas\.worktrees\hiatlas-platform-phase-1`.

## Entrega

- ApiClient central com cookies, CSRF pré-login/por mutação, AbortSignal,
  header opaco de contexto, cancelamento e rejeição de respostas antigas.
- Login real por e-mail/senha, `/auth/me`, restauração, AuthProvider e logout
  revogado no servidor. Papel vem da identidade; nunca do seletor demonstrativo.
- Seleção autorizada de empresa/contrato, pesquisa/paginação, vazio, erro,
  carregamento e contexto obrigatório antes dos shells internos.
- Contexto por aba, somente id em `hiatlas.access-context.v1` no sessionStorage;
  revalidação antes de restaurar e encerramento explícito ao trocar contrato.
- Empresa, código e ambiente sempre visíveis em cabeçalho sticky; entradas
  distintas para Administração e Suporte, sem simular ferramentas futuras.
- Demo preservado em entrada separada de desenvolvimento, flag desligada por
  padrão, banner permanente e zero chamadas à API real.
- Tema claro/escuro, logo oficial, slogan, responsividade, labels e foco visível.

Ajuste mínimo no backend: POST `/api/contexts` projeta somente `{id}`;
GET `/api/context` acrescenta código e ambiente atuais. Nenhum controle de
sessão, CSRF, autorização, ownership ou isolamento foi relaxado.

**Migrações:** nenhuma nova. A suíte continua cobrindo upgrade/downgrade/upgrade
com as migrações das Fases 1–3. Dependências/lockfiles do produto preservados.

## RED / GREEN observado

| Caso | RED | GREEN |
|---|---|---|
| Login real | LoginForm ausente; fluxo ainda encontrava login/seletor demo | Campos reais, erro neutro, CSRF, `/me`, logout e restauração |
| Transporte | ApiClient ausente | Cookies/header/CSRF, aborto e rejeição mesmo quando fetch ignora aborto |
| Contrato backend | Criação expunha campos extras; leitura sem contract_code | Apenas id na criação; código/ambiente atuais na leitura |
| Falha de CSRF ao encerrar | Contexto era apagado apesar do DELETE negado | Mantém contexto e informa erro, sem troca aparente |
| Contexto persistido malformado | CONTEXT_REQUIRED prendia a recuperação | Limpa id após rejeição do servidor e volta ao seletor |
| Logout falho durante validação | Cancelamento deixava portal vazio | Retoma validação quando logout falha |
| Retry da listagem | Erro antigo sobrevivia ao sucesso | Limpa erro e mostra estado vazio/resultados |
| Validação 422 | Campos sem identificação acessível da falha | Mensagem e aria-invalid associados a e-mail/senha |
| Loading da seleção | Intervalo sem conteúdo durante GET /context | Estado de validação visível |
| StrictMode/restauração | Finally de consulta cancelada mostrava login antes da consulta ativa | Geração invalidada no cleanup; loading termina somente na consulta vigente |

Os REDs foram executados antes das respectivas correções. As invocações focadas
selecionam casos por arquivo/nome; o gate final executou as suítes completas,
sem skips. O último caso foi encontrado ao repetir o E2E real e também recebeu
regressão unitária e revisão independente.

## Comandos e resultados

PostgreSQL 18.6 real, cluster novo em diretório temporário, apenas loopback,
banco marcado `hiatlas-disposable-test-db`, owner/runtime distintos e sem
superusuário nesses dois papéis. Nenhum banco de aplicação foi utilizado.

| Comando | Resultado |
|---|---|
| `scripts/check-platform-foundation.ps1` | PASS, incluindo backend/frontend/diffs |
| `uv run --frozen pytest` | **236 passed, 0 skips**, 133,81 s |
| `uv run --frozen ruff check app tests alembic` | aprovado |
| `uv run --frozen ruff check ../scripts/phase04-browser-fixture.py` | aprovado |
| `npm test` (execução final após correção StrictMode) | **100 passed, 8 arquivos, 0 skips**, 11,41 s |
| `npm run lint` | aprovado, sem avisos |
| `npm run build` | TypeScript + Vite aprovados |
| Build com `VITE_ENABLE_DEMO=true` + inspeção dos JS emitidos | sem entrada, seletor ou dados do demo |
| `node e2e/phase04.mjs` | aprovado com HTTPS/API/PostgreSQL reais; zero pageerrors |
| `node e2e/demo.mjs` | demo habilitado funcional; zero requisições `/api` |
| `git diff --check` e `git diff --cached --check` | aprovados |

O gate consolidado tinha 99 testes frontend; a regressão StrictMode elevou para
100. Após essa correção, navegador, suíte frontend completa, lint, build e diff
foram novamente executados. Não houve mudança backend depois dos 236 testes.
Permanece o aviso de depreciação Starlette/httpx já existente nas fases anteriores.

O harness de navegador aguarda a prontidão da API HTTPS e a decodificação dos
logos antes de capturar. Uma recaptura inicial encontrou a API ainda iniciando;
o procedimento foi corrigido, sem enfraquecer a aplicação.

## Cobertura de segurança e comportamento

- Login sem seletor, credenciais inválidas neutras, `/me` após login e no reload.
- 401 durante uso limpa identidade, UI e contexto; logout chama servidor com
  CSRF. Falha no logout não é apresentada como sessão revogada.
- Admin e suporte passam pelo seletor e entram nos seus respectivos shells.
- POST cria contexto real; somente id opaco é persistido e enviado no header.
- Duas páginas Chrome compartilham o cookie e mantêm contextos diferentes;
  encerrar A preserva o id e a validade de B no servidor.
- Contexto revogado, inválido/malformado e sessão expirada foram exercitados
  no navegador. Expiração/ownership/isolamento também permanecem na suíte backend.
- Resposta atrasada de A, após selecionar B, não altera a UI de B; o sinal
  anterior é abortado e o cliente rejeita respostas de geração antiga.
- Nenhum contexto/sessão em localStorage; preferência de tema é independente.
- Tentativa de elevar suporte via localStorage/header permanece **403 na API**.
- 403/404/409/422/429/503 têm mensagens sanitizadas e request_id seguro; nenhum
  texto bruto, senha, token ou stack trace é usado como mensagem de interface.
- Todas as regressões herdadas seguem verdes: propriedade de contexto,
  isolamento tenant/contract, expiração/revogação, suporte elegível, financeiro
  negado, auditoria, sessões, CSRF, bootstrap e último administrador.

## Revisão independente

Revisor em contexto separado, somente leitura, sem executar pytest concorrente
no banco. Encontrou três P2: id persistido malformado, logout falho durante
validação e retry que preservava erro. Todos reproduzidos em RED e corrigidos.
A segunda revisão confirmou as correções, sem regressão importante.

Depois do achado StrictMode no E2E, houve revisão adicional dessa correção.
O revisor confirmou a invalidação da geração antes de cancelar e a cobertura
para não mostrar login prematuramente. Não restaram achados importantes abertos.

## Evidência visual

Inspeção de capturas Chrome em 1440×1000 e 390×844, teste adicional de scroll
em 390×400. Sem overflow horizontal; contexto permanece visível ao rolar.
Navegação por teclado entre campos e foco foram verificados.

| Tela | Claro | Escuro | Celular |
|---|---|---|---|
| Login | [captura](phase-04-visual/login-light.png) | [captura](phase-04-visual/login-dark.png) | [captura](phase-04-visual/login-mobile.png) |
| Seleção | [captura](phase-04-visual/selection-light.png) | [captura](phase-04-visual/selection-dark.png) | [captura](phase-04-visual/selection-mobile.png) |
| Administração | [captura](phase-04-visual/admin-light.png) | [captura](phase-04-visual/admin-dark.png) | [captura](phase-04-visual/admin-mobile.png) |
| Suporte | [captura](phase-04-visual/support-light.png) | [captura](phase-04-visual/support-dark.png) | mesma estrutura responsiva |

Também: [segunda aba](phase-04-visual/second-tab.png),
[contexto inválido](phase-04-visual/invalid-context.png) e
[sessão expirada](phase-04-visual/expired-session.png).
As identidades e empresas nas capturas são fixtures exclusivas do banco descartável.

## Riscos, limites e dependências operacionais

1. Os portais são shells. Nenhuma funcionalidade da Fase 5 ou posterior foi criada.
2. A API atual lista somente contratos ativos e não fornece módulos contratados.
   Não há módulos/permissões fictícios como fallback.
3. Certificado HTTPS confiável, origem pública, proxy e banco/identidades de
   produção continuam dependendo da operação. Nada foi implantado/configurado
   em produção. Certificado autoassinado só foi aceito pelo navegador de teste.
4. A suíte de navegador usa Chrome/Playwright do ambiente de ferramentas;
   não houve matriz multibrowser ou auditoria assistiva completa.
5. Revalidação ocorre no foco, reload e operações; não há polling que mantenha
   sessão ociosa artificialmente viva. Outra aba percebe logout no próximo foco
   ou 401; o servidor já negará qualquer operação.
6. Sem sessionStorage disponível, o contexto funciona em memória e precisa de
   nova seleção no reload. Sessão continua sendo cookie seguro.
7. O cadastro desta tarefa no Codex ainda aponta para `D:\Cargo.Ops`, inexistente.
   A execução usou explicitamente a worktree real em `D:\Atlas`.
8. Procedimento de reprodução e variáveis: [operação do frontend](../../../operations/hiatlas-frontend.md).

Processos de preview/API encerrados; cluster PostgreSQL descartável parado e
removido; credenciais e chave TLS temporárias removidas. Worktree preservada.
Sem push, merge ou deploy. **Fase 4 encerrada para revisão; Fase 5 não iniciada.**
