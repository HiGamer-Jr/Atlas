# Fase 3 — Contextos e permissões

Data: 23/09/2026. Base aprovada: `8e30fcd`.
Branch: `feat/hiatlas-platform-phase-3`.
Worktree: `D:\Atlas\.worktrees\hiatlas-platform-phase-1` (isolado, reaproveitado).

## Entrega e fronteiras

- Tenant/Contract persistentes integrados à API; Membership vincula usuário,
  tenant, contrato e TenantRole por chaves compostas.
- TenantRole/Permission separados dos papéis internos, catálogo fechado,
  require_context e require_capability com negação por padrão no servidor.
- AccessContext opaco, vinculado ao ator e à sessão, seleção/encerramento explícitos,
  expiração/revogação e múltiplos contextos sem contrato global na sessão.
- Header exclusivo X-HiAtlas-Context. IDs de tenant/contrato são apresentação ou
  alvo da seleção, nunca fonte de autorização.
- Revalidação do estado atual de identidade, sessão, tenant, contrato, membership,
  perfil e permissões; mudanças de perfil/atribuição revogam contextos afetados.
- support_assignable começa false; alteração exclusiva do PLATFORM_ADMIN,
  auditoria atômica e validação de classificação, capabilities e histórico sensível.
- Financeiro/Fiscal permanece negado para todos os atores nesta fase.
- Negócio/auditoria continuam protegidos de DELETE/TRUNCATE por categoria.
  AccessContext recebe DELETE técnico, sem TRUNCATE.
- Nenhum frontend, convite, recuperação de senha, sessão de suporte, manutenção,
  concessão financeira, módulo operacional ou Administração do Cliente foi criado.

## Commits

- `c8d4cdb` — seleção explícita, modelos/migração e isolamento.
- `6e452b1` — capabilities, elegibilidade e atribuição segura de perfil.
- Correções da revisão, documentação e evidências no commit final desta fase.

## TDD e execução

Baseline: 145 testes backend passaram em PostgreSQL descartável novo, somente
loopback, owner/runtime distintos e sem superusuário. Nenhum banco real foi usado.
Os testes usam HTTP TestClient, autenticação real, PostgreSQL e conexões independentes;
não há rota secreta, mock de autorização ou fallback para a base da aplicação.

| Comportamento | RED observado | GREEN |
|---|---|---|
| Seleção explícita/isolamento | rotas de contexto retornavam 404 | 27 testes iniciais, depois 181 backend com FKs/grants |
| Criação e atribuição de perfis | cinco casos retornavam 404 em vez do contrato esperado | 47 testes iniciais de política/API |
| Limpeza concorrente do contexto | leitura/encerramento retornavam 500 | 403/404 sem revelar contexto |
| Expiração esperando lock do perfil | atribuição retornava 200 | 401 sem alteração |
| Expiração esperando lock do tenant | seleção 500, criação de contrato 201, encerramento 204 | três casos retornam 401; sem novo audit_event nem alteração |
| Gate de preview | exigia marca antiga Atlas Supply, já ausente na baseline | verificação usa HiAtlas e mantém demais proteções |

A suíte usa relógio injetável para expiração e observa wait_event_type=Lock para
sincronizar corridas reais. Não depende de um sleep arbitrário para assumir que
a requisição aguardou o banco.

## Matriz de segurança verificada

| Requisito | Evidência automatizada |
|---|---|
| A/A não acessa A/A2 nem B/B | test_other_contract_valid_membership_id_is_hidden; test_valid_foreign_role_id_is_hidden |
| IDs válidos estrangeiros são ocultados | test_valid_foreign_membership_id_is_hidden; consultas com id+tenant+contract |
| Sessão exata é proprietária | test_context_is_owned_by_exact_session, inclusive novo login do mesmo usuário |
| Expiração/revogação | test_context_expiration_before_session_expiry; test_revoked_context_rejected; test_session_revocation_invalidates_all_its_contexts |
| Contrato/tenant inativos | test_inactive_contract_or_tenant_revokes_context_immediately |
| Membership bloqueado/inativo | test_membership_status_revalidated_on_every_request |
| Perfil/permissão vigente | test_role_deactivation_revalidated; test_permission_change_is_effective_on_existing_context |
| Duas abas independentes | test_two_contexts_do_not_overwrite_each_other; test_assignment_revokes_only_target_contract_context |
| Sensível com flag=true continua negado | test_support_cannot_assign_ineligible_roles; test_support_eligibility_uses_classification_history_and_catalog |
| Renomear/reclassificar/remover permissão não lava sensibilidade | test_renaming_and_removing_sensitive_permissions_cannot_launder_role |
| Só admin altera flag, com auditoria | test_admin_can_enable_flag_with_audit; test_only_platform_admin_can_change_roles |
| Sem atribuição de papéis internos | test_internal_codes_are_never_tenant_roles; test_internal_identity_cannot_be_changed_via_tenant_membership |
| Estado concorrente relido | test_flag_is_reread_after_concurrent_commit; testes de expiração durante locks |
| Capabilities financeiras/desconhecidas negadas | test_financial_and_unknown_capabilities_are_denied_everywhere (admin/suporte/cliente) |
| Auditoria na transação | test_assignment_rolls_back_when_audit_fails; test_context_creation_rolls_back_if_audit_fails; snapshots de criação/edição/atribuição |
| Integridade física do escopo | test_database_rejects_cross_contract_role_reference; test_database_rejects_context_actor_from_another_session |
| Privilégios mínimos | test_new_business_tables_remain_protected e testes herdados de runtime/auditoria |

## Revisão independente

Revisão somente leitura de `8e30fcd..6e452b1`, em contexto independente,
sem executar testes concorrentes no banco compartilhado. O revisor confirmou
isolamento, propriedade de contexto, FKs, elegibilidade e atomicidade da auditoria.

Dois achados importantes: expiração durante espera por lock na seleção de
contexto e na criação de contrato. Ambos reproduzidos em RED. A mesma investigação
incluiu encerramento, que também aceitava sessão expirada após espera. A correção
reusa authenticate(touch=False) após locks e antes de mutar; os três testes
passaram, verificando também ausência de efeitos parciais. Não houve segunda revisão.

Nenhum achado crítico ou menor foi reportado. Itens não julgados pelo revisor:
frontend, convites/workflows de membership/sessão de suporte, concessões financeiras
e documentação ainda em elaboração. Decisão do executor: manter os três primeiros
fora de escopo por proibição explícita do usuário; concluir a documentação aqui.

## Quality gate final

Execução final: `scripts/check.ps1`, com variáveis do harness apontando apenas ao
cluster descartável. Exit code 0; marcador `ATLAS QUALITY GATE: PASS`.

| Verificação | Resultado |
|---|---|
| Sintaxe do legado + preview estático | passou |
| Vitest | 68 testes, 5 arquivos; passou |
| Oxlint | passou |
| TypeScript + Vite build | passou |
| pytest/PostgreSQL | 234 testes; passou em 148,56 s |
| Ruff app/tests | passou |
| git diff --check e --cached | passou |
| Credenciais temporárias no diff | nenhuma encontrada |

Os 234 testes incluem upgrade/downgrade/upgrade, controles de credenciais de
banco, regressões das fases anteriores e os casos novos desta fase.
Permanece um aviso de depreciação Starlette/httpx da baseline.

## Decisões e limites

1. Worktree físico mantém nome phase-1; branch própria phase-3 preserva isolamento.
2. Catálogo de leitura necessário ao contexto entrou na tarefa 3.1; mutações vieram
   na 3.2, mantendo a ordem de dependências do plano.
3. sensitivity_locked é histórico permanente controlado pelo servidor. Custo:
   uma função nova não sensível requer novo perfil, em vez de reaproveitar o sensível.
4. Serialização por contrato prioriza correção; mede-se concorrência antes de
   otimizar. Contextos independentes não significam ausência de locks.
5. Permissões de role são inativadas, sem DELETE de dados de negócio.
6. Isolamento no servidor + FKs compostas; PostgreSQL RLS não foi implementado.
7. Correção mínima da marca no script do gate; nenhum frontend alterado.
8. uv e lockfiles preservados. Aviso Starlette/httpx já existente permanece.
9. Membership é persistente e autorizador; criação/status via atendimento pertencem
   às fases seguintes. Testes provisionam vínculos no banco descartável.

Consulte [operação dos contextos](../../../operations/hiatlas-contexts.md).
Sem merge, push ou deploy. Encerrar cluster descartável e remover credenciais
temporárias ao finalizar. **Parar para revisão antes da Fase 4.**
