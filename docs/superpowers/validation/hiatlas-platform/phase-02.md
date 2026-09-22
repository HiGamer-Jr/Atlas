# Fase 2 — Identidade, sessão, bootstrap e operadores internos

Data: 22/09/2026. Base aprovada: `549cdd5`.
Branch: `feat/hiatlas-platform-phase-2`.
Worktree: `D:\Atlas\.worktrees\hiatlas-platform-phase-1` (checkout isolado reaproveitado).

## Entrega e fronteiras

- PLATFORM_ADMIN e PLATFORM_SUPPORT são atribuições internas persistidas em
  platform_role_assignments; login não aceita selecionar privilégio.
- Autenticação HTTP, Argon2id, sessões opacas persistidas, CSRF pré-login e por
  sessão, cookies __Host-/Secure/HttpOnly/SameSite=Strict e origem HTTPS explícita.
- Logout, expiração por inatividade/absoluta, revogação e reautenticação.
- Limites de falhas persistidos com locks no PostgreSQL, compartilhados entre
  processos, login, reautenticação e confirmação de operador.
- Bootstrap local do primeiro administrador com entrada protegida, auditoria
  atômica e exclusão mútua. Sem endpoint, senha padrão ou argumento de senha.
- Alteração de papel com confirmação vinculada ao alvo/senha; alteração de status
  com reautenticação recente. Proteção do último administrador, snapshots e
  revogação de todas as sessões do alvo.
- Migração incremental 0002; privilégios técnicos explícitos, sem relaxar os
  grants de dados de negócio/auditoria da Fase 1.

Não foram implementados TenantRole, RBAC completo, AccessContext, seleção de
tenant/contrato, portais, convites, MFA ou break-glass. Nenhum frontend foi alterado;
o frontend existente continua demonstração e não autentica APIs reais.

## Commits de implementação

- `7f3b168` — sessões persistidas, CSRF, revogação e limites.
- `3016aff` — bootstrap e gestão segura de operadores.
- Correção de revisão e evidências incluídas no commit final de encerramento desta fase.

## Execução e testes

Baseline da Fase 1: 76 testes backend passaram em um cluster PostgreSQL 18.6
descartável novo, loopback e porta temporária. Owner/runtime distintos e sem
superusuário. Credenciais aleatórias não fazem parte do Git. Nenhum banco real
foi alterado; nenhum serviço ou deploy foi instalado.

Tarefa 2.1: testes HTTP escritos antes das rotas. RED: /auth/csrf e /auth/me
retornavam 404 (16 falhas e 11 falhas de fixture por ausência do CSRF).
GREEN: 27 testes iniciais; com casos de concorrência/replay/grants e regressões,
112 testes backend passaram.

Tarefa 2.2: RED de bootstrap/operadores (25 falhas, 4 verificações já satisfeitas
por ausência de endpoints/argumentos). GREEN: 29 casos iniciais.
Dois RED adicionais detectaram ator ausente em negação autenticada e aceitação de
runtime superusuário na aplicação incremental da migração 0002. Ambos corrigidos
e verificados, com 144 testes backend passando antes da revisão independente.

## Revisão independente

A revisão do intervalo 549cdd5..3016aff não encontrou problemas críticos ou
importantes nos cinco focos do plano. Reportou um caso menor: e-mail válido acima
de 200 caracteres excedia display_name durante o bootstrap.

O executor reclassificou como correção necessária porque impedia criar o primeiro
administrador com uma entrada aceita. O teste
test_bootstrap_accepts_long_email_without_truncating_identity falhou com
StringDataRightTruncation antes da correção e passou após limitar apenas o nome
inicial a 200 caracteres. O e-mail completo permanece persistido e faz login.
Custo da decisão: rótulo inicial abreviado em endereços longos, sem alterar identidade.
Não houve segunda revisão; regressão RED/GREEN e gate final verificam a correção.
Não há observações menores adiadas.

Itens que o revisor não julgou e decisão do executor:
- RBAC contextual, convites/recuperação e frontend autenticado: fases posteriores,
  explicitamente excluídas. Nenhuma capacidade dessas é alegada.
- TLS/proxy reais e carga/retenção: dependem de implantação; política HTTP e
  documentação verificadas aqui, sem alegar validação de infraestrutura real.
- Gate PostgreSQL concorrente: executado pelo agente principal; revisor não rodou
  testes no cluster compartilhado para não interferir nas fixtures.
- Documentação posterior ao intervalo: revisada pelo executor e incluída no commit final.

## Quality gate final

Comando: ./scripts/check-platform-foundation.ps1, exit code 0.
[Log completo do gate final](phase-02-quality-gate.log).

| Verificação | Resultado |
|---|---|
| Backend pytest/PostgreSQL | 145 passed, zero skips |
| Ruff app/tests/alembic | passou |
| Frontend Vitest | 68 passed |
| Frontend lint (oxlint) | passou |
| TypeScript + Vite build | passou |
| git diff --check e --cached | passou |

A correção do e-mail longo está incluída neste gate. Não houve alteração de
frontend. A instância temporária é encerrada ao finalizar e as credenciais locais
são removidas. Fase 2 concluída; Fase 3 não iniciada.

Os testes exercitam HTTP real via TestClient, hash Argon2id real, PostgreSQL e
conexões independentes nas corridas. Não há auth mock ou rota secreta de teste.
Relógio injetável verifica limites sem sleeps. Ausência de banco continua falha,
sem fallback para DATABASE_URL e sem skips.

## Decisões de execução

1. Reaproveitar worktree isolado com nome phase-1 e criar branch phase-2.
   Benefício: preservar setup validado; custo: nome físico não acompanha a fase.
2. Usar cluster de teste novo; o da Fase 1 estava encerrado e sem credenciais.
   Custo: provisão temporária adicional; nenhum acesso à base da aplicação.
3. Exigir uma origem HTTPS explícita e cookies Secure inclusive em desenvolvimento.
   Custo: frontend HTTP antigo não pode usar autenticação real.
4. Conceder SELECT/INSERT/UPDATE/DELETE às três tabelas técnicas, sem TRUNCATE.
   Auditoria e negócio mantêm suas restrições; limpeza futura deve filtrar expiração.
5. Retornar erro sanitizado em falha de credencial para persistir contadores e
   AccessEvent; exceções revertidas registram negação em transação separada.
   Não há mutação operacional parcial nesses retornos.
6. A senha no endpoint de papel vale como reautenticação fresca da própria
   operação; status exige confirmação há menos de cinco minutos.
7. Bootstrap verifica evento histórico e atribuição administrativa, além de
   recusar identidade existente. Perder acesso não reabre o bootstrap; recuperação
   break-glass continua na Fase 11.
8. capabilities de /auth/me permanece vazio; rotas internas aplicam a regra
   PLATFORM_ADMIN diretamente. Catálogo e autorização contextual ficam na Fase 3.
9. Acompanhamento das duas tarefas feito no ledger; os cabeçalhos Tarefa do plano
   em português foram mantidos. Commits e resultados preservam a rastreabilidade.

## Operação e limitações

Consulte [guia de identidade](../../../operations/hiatlas-identity.md) e
[configuração do banco](../../../../database/README.md).
uv foi preservado; somente argon2-cffi e dependências transitivas foram adicionados.

Um aviso de depreciação Starlette/httpx já presente na baseline permanece.
TLS real, proxy, dimensionamento do Argon2 e retenção técnica exigem configuração
de implantação. TestClient verifica cookies/contrato HTTP, não o terminador TLS.
O processo ASGI deve preservar o peer; guia usa --no-proxy-headers e lista explícita
de proxies para evitar confiar em X-Forwarded-For de origem arbitrária.

Ao encerrar: preservar branch/worktree, encerrar cluster descartável, remover
arquivos temporários de credenciais. Sem merge, push ou deploy.
Parada obrigatória para revisão antes da Fase 3.
