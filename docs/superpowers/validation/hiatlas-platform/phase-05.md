# Fase 5 — Convites, recuperação e ciclo de vida seguro

Status: implementada e validada; parada obrigatória para revisão do usuário.
Data do gate e E2E final: 2026-09-28. Fase 6 não iniciada.

## Identificação

- Branch: `feat/hiatlas-platform-phase-5`.
- Base aprovada da Fase 4: `93bc34b`.
- Commit de implementação testado: `ef6b7c50a3fafdc8be324d1e7fddd8ca0130f136`.
- Este relatório e a atualização do plano são registrados em commit documental posterior.
- Worktree preservada: `D:\Atlas\.worktrees\hiatlas-platform-phase-1`.
- Nenhum merge, push ou deploy realizado.

## Entrega

SecurityToken persistente para INVITE e PASSWORD_RESET, segredo aleatório de 32 bytes,
hash SHA-256, finalidade/destinatário explícitos, expiração, consumo único e invalidação.
Prazos configuráveis: convite 24 horas e reset 30 minutos. Reemissão invalida tokens
anteriores da mesma finalidade e destinatário. Nenhum token ou link secreto é devolvido
pela API. Senha própria com Argon2id e política central configurável de 12 a 1024 caracteres.

Token, outbox cifrada e auditoria são persistidos na mesma transação. SMTP fica no
worker posterior ao commit HTTP. Fernet protege o conteúdo necessário à entrega com
chave externa ao banco. Worker com claim persistente, SKIP LOCKED, lease, tentativas
limitadas e backoff; revalidação antes do envio; erro sanitizado e remoção de ciphertext
nos estados finais. Transportes SMTP e FakeEmailTransport separados.

Reset revoga todas as sessões e AccessContexts do usuário na mesma transação.
Convite para identidade existente exige autenticação recente do próprio destinatário,
preserva senha e não revela outros contratos. Vínculo pendente não concede acesso.
Flags active/blocked independentes e revogação restrita ao contrato afetado.
Suporte opera somente no contexto autorizado, sem alterar e-mail global ou criar
papéis internos. Convite interno exclusivo de administrador exige reautenticação
e confirmação; administrador pendente não substitui o último administrador utilizável.

Frontend real: link de recuperação no login e rotas públicas `/password/forgot`,
`/password/reset` e `/invite/accept`. Token de fragmento capturado somente em memória,
removido da URL antes das requisições e limpo após consumo. Sem armazenamento de token
em localStorage/sessionStorage, analytics ou recursos externos. Política no-referrer,
estados acessíveis, confirmação de senha, retorno ao login, temas e logo oficial.
Apenas API mínima de vínculos; nenhuma tela completa de gestão da Fase 6.

## RED / GREEN

Registros dos implementadores e revisores, consolidados antes de remover os arquivos
transitórios de trabalho:

| Comportamento | RED observado | GREEN / confirmação |
|---|---|---|
| Política central de senha | 1 falha: função ausente | teste passou |
| Tokens/rotas persistentes | 2 falhas: modelos/rota ausentes | integrações passaram |
| Convite e vínculo pendente | rota ausente; contrato pendente visível | suíte ampliada passou |
| Revisão backend | 4 falhas: listagem contextual, cancelamento reversível, último admin e reenvio interno | 15 testes passaram |
| Destinatário único SMTP | 2 falhas: lista/display name aceitos | validação estrita e envelope único |
| Migração incremental | 2 falhas: papéis inseguros | rejeição antes de DDL |
| Auditoria automática de cancelamento | 3 falhas | evento tipado e rollback |
| Exceção ValueError da auditoria | 1 falha | 5 testes focados passaram |
| Frontend inicial | 12 falhas: rotas/link/comportamentos ausentes | 12 testes passaram |
| React StrictMode | 1 falha de cancelamento prematuro | suíte ampliada passou |
| Correções da revisão frontend | regressões de sessão, retry e cancelamento | 23 testes de ciclo de acesso confirmados pelo revisor |

Antes do gate, os cinco arquivos backend da Fase 5 passaram com 66 testes, sem skips.
O gate final abaixo inclui também as regressões posteriores; os resultados anteriores
não substituem a execução completa final.

## Quality gate final

Comando: `scripts/check-platform-foundation.ps1`, com variáveis do PostgreSQL descartável.
Resultado final: exit 0, `[PASS] HiAtlas Phase Quality Gate`.

| Verificação | Resultado |
|---|---|
| Backend `uv run --frozen pytest` | **304 passed**, zero skips, 160,52 s |
| Ruff `ruff check app tests alembic` | passou |
| Frontend `npm test` | **123 passed**, 9 arquivos, zero skips, 37,83 s |
| oxlint `npm run lint` | passou |
| TypeScript/Vite `npm run build` | passou |
| `git diff --check` e `git diff --cached --check` | passaram |
| Ruff do harness Python e sintaxe do harness Node | passaram |

Um warning preexistente: depreciação do uso de httpx pelo TestClient Starlette.
Avisos Git de normalização LF/CRLF não são falhas do gate.

## PostgreSQL, migração e concorrência

PostgreSQL **18.6 real**, distribuição portátil EDB, cluster temporário exclusivo em
loopback, porta 55485. Banco `hiatlas_phase05_test` com marcador explícito de banco
descartável. Papéis owner/runtime distintos e não superusuários; URLs e credenciais
somente no ambiente temporário, nunca neste relatório. Sem SQLite ou testes obrigatórios
pulados. Testes backend e E2E usaram o banco sequencialmente, sem disputar fixtures.

Migração `0004_access_tokens_outbox` adiciona tokens, outbox e flags de convite ao vínculo.
Testes cobrem upgrade/downgrade, upgrade incremental e rejeição de runtime igual ao owner
ou superusuário antes de qualquer DDL. Nenhuma migração executada em banco de produção.

Concorrência real com clientes/conexões independentes:

- Dois consumos simultâneos de reset: exatamente um sucesso.
- Dois consumos simultâneos de convite: exatamente um sucesso.
- Emissão concorrente com consumo: resultado consistente com a ordem serializada.
- Workers concorrentes: uma entrega; mensagem concluída não é reenviada.
- Worker versus reemissão: serialização impede envio após invalidação confirmada.
- Claim abandonado: UNKNOWN, sem reenvio automático.

Cobertura adicional: token expirado/consumido/invalidado/finalidade errada/destinatário
incompatível, reset anterior invalidado, senha nova revoga duas sessões e contextos de
dois contratos, rate limit persistente após recriar aplicação, respostas neutras para
existente/inexistente/bloqueado/inativo, proteção de outras memberships, combinações de
active/blocked, auditoria sem credenciais e rollback quando auditoria falha, inclusive
ValueError em cancelamento automático.

Fontes principais: `test_access_tokens.py`, `test_email_outbox.py`,
`test_membership_invitations.py`, `test_membership_lifecycle.py`,
`test_access_lifecycle.py` e os testes anteriores de identidade/contextos.

## E2E real

Comando: `node e2e/phase05.mjs`. Resultado: **PASS**, exit 0.
Chrome headless via Playwright, frontend HTTPS real, FastAPI real e PostgreSQL real.
Sem mocks de rotas HTTP. SMTP substituído por FakeEmailTransport controlado no harness;
nenhum e-mail enviado para destinatário real. Conteúdo de entrega circulou somente por
pipe e memória do teste; sem traces, vídeos ou logs de URLs/payloads secretos.

Confirmado no navegador:

- Solicitação pelo link de recuperação; resposta idêntica para e-mail conhecido e ausente.
- Consumo do reset, login com nova senha, sessão antiga 401 e contexto antigo negado.
- Emissão autorizada, aceite do convite com senha própria, retorno e login real.
- Reutilização do convite rejeitada e token expirado apresentado corretamente.
- Transporte indisponível: mensagem real de indisponibilidade e 503 uniforme.
- Token ausente de URL visível, storage e texto da página; no-referrer e nenhuma
  requisição externa ou com token em query string; nenhum pageerror.
- Light/dark, viewport mobile 390 × 844 sem overflow horizontal, foco por teclado.

Capturas sanitizadas em [phase-05-visual](phase-05-visual/):
[convite claro](phase-05-visual/invite-light.png),
[convite escuro](phase-05-visual/invite-dark.png),
[convite mobile](phase-05-visual/invite-mobile.png),
[recuperação clara](phase-05-visual/recovery-requested-light.png),
[recuperação escura](phase-05-visual/recovery-requested-dark.png),
[recuperação mobile](phase-05-visual/recovery-mobile.png),
[reset mobile](phase-05-visual/reset-mobile-dark.png),
[reset concluído](phase-05-visual/reset-complete.png),
[convite aceito](phase-05-visual/invite-complete.png),
[replay](phase-05-visual/invite-reused.png),
[expiração](phase-05-visual/token-expired.png) e
[indisponibilidade](phase-05-visual/email-unavailable.png).
Inspeção visual direta confirmou logo, campos e contraste nas capturas clara desktop
 e escura mobile do convite.

## Revisão independente

Revisores distintos dos implementadores examinaram backend e frontend.

Backend: corrigidos um P1 (administrador pendente contava para proteção do último admin)
e três P2 (descoberta contextual de convites, reenvio interno e cancelamento que podia
ser revertido pela restauração da elegibilidade). Reinspeção confirmou as correções,
validação de destinatário único, proteção da migração incremental e auditoria de
cancelamento com proveniência de sistema. Exceções de auditoria não são absorvidas pelo
tratamento de ciphertext. Nenhum bloqueio restante no escopo revisto. O revisor não
executou banco em paralelo; o gate completo foi executado pelo integrador.

Frontend: corrigidos dois P2 (sessão anterior de outra identidade permanecia após sucesso;
falha transitória destruía o token válido). Também corrigidos abort ao desmontar e limpeza
da sessão de autenticação de aceite que falhou. Revisor executou os 23 testes focados;
nenhuma nova questão acionável na reinspeção. Gate completo e navegador pelo integrador.

## Riscos e limites

- Lock global do ciclo de acesso serializa operações inclusive entre destinatários.
  Com piso padrão de recuperação de 250 ms, cerca de quatro solicitações por segundo
  antes de outras operações; SMTP lento amplia a espera. Login normal não usa esse lock.
  É uma limitação explícita do worker simples; não foi feito teste de carga de produção.
- SMTP não permite garantir exatamente uma entrega após falha incerta. UNKNOWN não
  reenvia automaticamente; nova solicitação autorizada cria outro token e invalida o
  anterior. Não há promessa de entrega real baseada no adaptador falso.
- SMTP de produção e ambiente publicado não foram exercitados. Chave de outbox, origem
  HTTPS confiável, SMTP e headers/fallback do servidor publicado exigem configuração
  operacional. Ver [manual operacional](../../../operations/hiatlas-access-lifecycle.md).
- E2E executado em Chrome; não há alegação de matriz completa de navegadores, avaliação
  de acessibilidade por leitor de tela ou teste de carga.
- Usuário de contrato autentica de verdade, mas os módulos/telas posteriores permanecem
  fora desta fase; o portal existente informa acesso indisponível quando não há ambiente
  interno aplicável. Gestão visual completa permanece na Fase 6.

Encerramento: preservar branch e worktree para revisão; encerrar serviços de teste e
remover cluster, credenciais e arquivos transitórios. Não iniciar a próxima fase.
