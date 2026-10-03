# Phase 10 — revisão independente do backend

## Conclusão

Revisão estática final da versão congelada: os seis achados iniciais foram tratados no código e possuem testes de regressão correspondentes. Não identifiquei bloqueador de código remanescente dentro do escopo da Fase 10. A conclusão autoriza prosseguir com o gate completo e o E2E; não declara esses gates aprovados, nem substitui a evidência de execução do coordenador.

Base: `1b01fa9ee3d0a826b5346ffc28745d590453aa67`. Branch: `feat/hiatlas-platform-phase-10`. Objeto da revisão: working tree congelada entregue pelo implementador, após correções dos achados e inclusão das regras de linhagem e falha persistida.

## Limites e origem da evidência

- Este revisor leu os requisitos vinculantes de `10-manutencao-controlada.md`, o código, a migração e as fontes dos testes. Não executou pytest, não acessou o banco, não alterou produto/testes e não realizou commits.
- Verificação própria somente de leitura: `git diff --check`, exit 0; houve apenas aviso de conversão CRLF no plano existente.
- O coordenador informou execução nova dos seis arquivos de teste focados: **92 passed, zero skips, 102.38s**, sessão de ferramenta `12447`; somente warning de depreciação Starlette/httpx. Esta é evidência executada pelo coordenador, não por este revisor.
- Resultados anteriores **91 GREEN** e **109 GREEN de regressões da Fase 9** foram relatados pelo implementador ao coordenador. Não foram executados ou observados diretamente por este revisor.
- REDs anteriores foram relatados pelo implementador. A leitura atual confirma que os casos de regressão existem e exercitam as falhas descritas, mas não permite alegar que este revisor observou suas execuções RED.
- Gate completo, novos testes eventualmente adicionados pelo coordenador, E2E, capturas e limpeza continuam sendo consolidados em `phase-10.md`. Nenhum deles é marcado PASS por este relatório.

## Achados iniciais e resolução

| Achado | Resolução observada | Teste de regressão lido | Estado |
| --- | --- | --- | --- |
| P1: preview com alteração seguida de flush podia persistir estado | `corrections.py:94` executa o callback em savepoint e faz rollback incondicional em finally; a mesma fronteira isola a recomputação durante apply. Alteração da projeção da entidade provoca rejeição. Escritas ORM e SQL dentro do savepoint não sobrevivem. | `test_preview_flush_cannot_persist_any_domain_mutation` | Tratado estaticamente; incluído no GREEN92 relatado pelo coordenador. |
| P1: receipt não vinculava after e efeitos exibidos | `corrections.py:71` assina comando, before, after, effects, contexto, grant, operador, sessão, tenant, contrato e prazo. Apply recompõe o preview sob lock, confere a assinatura e compara o after efetivo com a projeção confirmada, exigindo avanço unitário de versão. | `test_changed_displayed_after_same_version_requires_new_preview`; conflito/receipt ausente ou alterado também coberto | Tratado estaticamente; incluído no GREEN92 relatado pelo coordenador. |
| P2: Any/list[Any] abriam o schema concreto | `registry.py:9` exige tipos JSON concretos, objetos fechados, itens tipados, alternativas fechadas e referências locais verificáveis. | `test_registered_handler_rejects_open_nested_payload`, parametrizado; `test_registered_handler_accepts_concrete_closed_nested_model` | Tratado estaticamente; incluído no GREEN92 relatado pelo coordenador. |
| P2: CHECK permitia chave ou fingerprint nulos | `models.py:156` e migração `0009:108` exigem explicitamente `idempotency_key IS NOT NULL` e `command_fingerprint IS NOT NULL` para retries. | `test_physical_retry_constraint_requires_non_null_key_and_fingerprint`, inserções PostgreSQL parametrizadas | Tratado estaticamente; incluído no GREEN92 relatado pelo coordenador. |
| P1: Support confiava apenas na classificação persistida | `processing.py:43` exige ação conhecida, handler tipado e opt-in `diagnostics_safe`; exclui FINANCE e capabilities de domínio finance/fiscal. A consulta também exige STANDARD. Ações desconhecidas/desabilitadas não entram no conjunto permitido; entidade e origem são omitidas da projeção Support. | `test_support_unknown_and_financial_handler_hidden_even_when_stored_standard`; `test_read_only_support_workspace_can_only_read_reduced_diagnostics` | Tratado estaticamente; incluído no GREEN92 relatado pelo coordenador. |
| P2: handler escolhido antes do lock podia divergir do source atualizado | `processing.py:208` refresca a execução com FOR UPDATE e resolve novamente a ação na linha 214 antes de autorizar e carregar a entidade. | `test_locked_source_re_resolves_registered_handler`, duas conexões e duas ações registradas | Tratado estaticamente; incluído no GREEN92 relatado pelo coordenador. |

Os números de linha acima se referem à versão congelada relida, anterior a eventuais ajustes de formatação do gate final. Caminhos de código relativos a `backend/app/maintenance`, salvo a migração em `backend/alembic/versions/0009_processing_runs.py`. Testes em `backend/tests`.

## Reprocessamento e novas proteções revisadas

- `request_reprocess` exige fonte contextual, handler registrado, concessão MAINTENANCE exata e autorização vigente, inclusive após os locks e no replay. O fingerprint usa fonte, ação, entidade e comando; não usa request_id ou sessão de infraestrutura.
- Mesma chave consulta o registro persistido sob lock, compara fingerprint e retorna a execução existente antes das regras para uma nova execução. Comando diferente para a mesma chave retorna conflito.
- `lineage_available` percorre a cadeia contextual persistida e bloqueia nova chave quando outra execução da linhagem está PENDING, RUNNING, SUCCEEDED ou UNKNOWN. Detecta ciclos. O caminho de mutação faz essa verificação após os locks da fonte e da entidade; os FKs compostos mantêm a mesma ação/entidade na cadeia. UNKNOWN permanece inelegível por padrão e exige decisão explícita de policy específica para a própria execução.
- Fontes dos testes cobrem mesma chave concorrente com um efeito/evento, chaves distintas concorrentes com um sucesso e um conflito, nova chave após sucesso e nova chave com filho PENDING/RUNNING/UNKNOWN.
- Falha de handler, inclusive após flush, reverte o savepoint do domínio. Em seguida, nova validação de autorização precede a persistência de FAILED com códigos allowlisted e auditoria tipada. A exceção original não integra projeção nem snapshot auditado. Falha da auditoria reverte também a reserva/registro de falha pelo rollback da transação externa.
- Sucesso de domínio, estado SUCCEEDED e auditoria permanecem na mesma transação externa. A dependência de banco com escopo function encerra a transação antes da resposta de sucesso.
- Foram lidos os testes de rollback de domínio/reserva, falha sanitizada com sentinel, falha de auditoria após falha do handler e espera real por lock seguida de expiração, conflito de versão ou mudança de domínio.

## Outros controles observados

- Registry normal continua vazio e não há import de fixture no startup normal de `backend/app`. Fixture e adapter controlados não representam módulos operacionais entregues.
- Schemas de input/snapshot são definidos por handler; envelopes rejeitam extras. Não há seleção arbitrária de tabela/coluna, execução de SQL do cliente ou fallback de payload aberto.
- Snapshot before vem do servidor. Comprovantes são assinados por chave efêmera do processo e não são incluídos nos snapshots de auditoria. Replay de correção após mudança de versão exige novo preview.
- Política mantém operador real, sessão, contexto, tenant, contrato, ação e entidade exatos. Grant/role/session/context/contrato são revalidados sob locks. Support não ganha mutação; READ_ONLY mantém somente o diagnóstico reduzido autorizado.
- Migração 0009 sucede 0008, mantém modelo e SQL alinhados, adiciona FKs compostos de origem/escopo/concessão/operador e índice único contextual de idempotência. O guard exige owner/runtime distintos e restritos. Runtime recebe somente SELECT/INSERT/UPDATE na nova tabela, sem DELETE/TRUNCATE/DDL.
- O acesso normal a metadados de módulo passou a usar `require_registered_module`, eliminando a dependência indevida de grant existente mencionada como limitação na primeira leitura.
- Diagnóstico usa projeção explícita com códigos fechados; snapshots de manutenção são omitidos na projeção reduzida de auditoria Support.

## Pendências e comportamentos fora da avaliação

Nenhum achado de código pendente nesta revisão estática. Permanecem os limites de evidência acima.

- Execução de gate completo, E2E, validação visual e limpeza: responsabilidade do coordenador; não executadas por este revisor. A matriz adicional de dois administradores/revogação foi revisada no adendo abaixo.
- Domínios de negócio futuros, novos tipos de entidade e respectivas projeções de auditoria: fora do escopo atual; exigirão seus próprios schemas, policy e revisão antes do registro em produção.
- Worker, fila e efeitos externos: não existem neste recorte síncrono e não foram avaliados. A revisão de savepoint cobre a transação de banco fornecida ao handler, não promete isolamento de código arbitrário malicioso ou efeitos externos.
- Frontend: possui revisão independente separada e não recebe aprovação por este documento.

Avaliação final: **seis achados encerrados na revisão estática; nenhum bloqueador de backend encontrado no escopo congelado. Integração depende dos gates finais registrados pelo coordenador.**


## Adendo — testes de aceitação de concorrência e revogação

Revisão estática adicional de `backend/tests/test_maintenance_acceptance_races.py` e dos helpers utilizados, sem acesso ao banco ou execução de testes por este revisor. Nenhuma alteração de produto foi objeto deste adendo.

- `test_two_admins_correct_same_version_only_one_commit` cria um segundo usuário PLATFORM_ADMIN real, usa outro cliente autenticado e inicia outra concessão/contexto MAINTENANCE para a mesma entidade. Cada operador obtém seu próprio receipt antes da barreira. As duas requisições concorrentes usam a mesma versão esperada. As asserções exigem respostas 200/409, entidade final na versão 2 e exatamente um evento `maintenance.correction.applied` persistido. Isto exercita a concorrência entre operadores distintos, sem reutilizar a identidade ou concessão do primeiro administrador.
- `test_correction_wait_rechecks_revocation` tem seis casos: auth session, contexto pai, contrato, tenant, role e grant. Uma conexão independente mantém o lock, o request inicia em outro thread, `wait_for_lock` observa espera real do PostgreSQL, e a alteração de autoridade é confirmada antes de liberar o request. As asserções exigem rejeição, entidade Original/version1 e zero eventos de correção aplicada.
- Precisão do escopo: estes seis casos bloqueiam em linhas da fronteira de autorização (no caso role, o lock é do contrato enquanto a atribuição de role é alterada). Eles verificam a recusa após a espera nessa fronteira; não afirmam que a requisição já tenha ultrapassado todos os gates ou adquirido o lock da entidade. Complementam os testes anteriores de espera pelo lock da entidade/fonte e de expiração/conflito.
- O campo `ended_at` acompanha a revogação explícita da grant no teste, respeitando a constraint de estado terminal. As mutações diretas usadas para preparar a corrida são fixture de teste e não são rotas genéricas do produto.

Evidência de execução atribuída: o coordenador informou execução nova **7 passed em 8.88s** deste arquivo, após corrigir os dados residuais da fixture e o estado terminal da concessão. Este revisor não observou diretamente a execução. O full pytest estava em andamento na sessão `10197` quando o adendo foi solicitado; seu resultado não é presumido aqui.

Conclusão do adendo: **nenhum achado pendente no arquivo adicional; a matriz cobre as condições declaradas com asserções persistidas de domínio e auditoria.** A conclusão estática anterior permanece válida, sujeita ao resultado dos gates finais do coordenador.

## Adendo final — negação de herança de manutenção

Revisão estática da extensão `test_direct_apply_and_reprocess_cannot_inherit_maintenance` em `backend/tests/test_maintenance_acceptance_races.py:141`, sem execução de testes ou acesso ao banco por este revisor. Nenhuma alteração de produto foi objeto deste adendo.

Os cinco casos exercitam Admin em READ_ONLY, contexto FINANCIAL_FISCAL, Support usando o contexto de manutenção de outro operador, nova sessão do mesmo Admin e segunda ação registrada fora do escopo da concessão. O receipt é obtido no contexto originalmente válido antes da troca. Cada caso chama preview, apply com esse receipt e reprocess de fonte conhecida, exigindo 401/403/404, domínio Original/version1, nenhum ProcessingRun filho e nenhum evento de correção/reprocessamento bem-sucedido.

No caso fora do escopo, `FIXTURE_NODE_OTHER` está efetivamente registrada e a fonte persistida usa esse código. Portanto a negação não pode ser atribuída a handler desconhecido. A expectativa de 401/403/404 no apply também evita aceitar apenas um conflito do comprovante como prova de autorização correta.

Conclusão estática: **nenhum achado pendente na extensão; os testes verificam as cinco fronteiras declaradas e a ausência de efeitos persistidos.** Mantém-se a conclusão de backend sem bloqueadores estáticos identificados no escopo revisado.

Atualização de evidência exclusivamente atribuída ao coordenador:

- Arquivo adicional completo: **12 passed em 13.78s**, sessão `91160`.
- Full backend anterior: **695 passed em 624.20s**, sessão `10197`; este resultado substitui a condição em andamento mencionada no adendo anterior.
- Repetição do full backend incluindo os cinco novos casos: **700 testes em execução**, sessão `16590`, resultado ainda não informado neste momento e não presumido.
- E2E controlado e normal informados aprovados nas sessões `82779` e `80556`; inspeção visual de 409/foco/mobile relatada pelo coordenador. Este revisor não executou nem inspecionou essas evidências de navegador.

O resultado definitivo da repetição do gate e a limpeza devem ser registrados pelo coordenador em `phase-10.md`.

## Consolidação do coordenador após o gate final

O coordenador confirmou pytest completo 700/700, zero skips, 614.20s (sessão16590), Vitest282/282, oxlint/TypeScriptVite/Ruff, E2E real normal/controlado e inspeção das capturas. A migração recebeu somente limpeza de whitespace final; ciclo físico/grants repetidos4/4GREEN. Nenhuma alteração funcional de produto após a revisão final. Serviços, PostgreSQL descartável e segredos temporários foram removidos. Esta consolidação não atribui execução ao revisor independente; phase-10.md reúne a evidência final.
