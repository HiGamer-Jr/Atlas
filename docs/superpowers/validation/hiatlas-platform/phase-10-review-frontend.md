# Fase 10 — revisão independente do frontend

Data: 2026-10-03. Worktree: D:/Atlas/.worktrees/hiatlas-platform-phase-1. Branch verificada: feat/hiatlas-platform-phase-10. Base indicada: 1b01fa9.

## Re-revisão final dos fixes — 2026-10-03

Resultado: **F10-FE-01 e F10-FE-02 fechados na revisão estática; nenhum novo bloqueador de frontend identificado neste escopo.** A aprovação independente do frontend não substitui os gates de PostgreSQL/E2E e limpeza pertencentes ao coordenador.

### F10-FE-01 fechado

- PrivilegedShell monta ReprocessingIntentProvider dentro de PrivilegedProvider e fora do trecho que Shell desmonta durante restoring. A key é grant.context_id (normal quando não há grant). Revalidar o mesmo contexto preserva a tentativa em memória; encerrar/perder/trocar o contexto desmonta seu provider e descarta os dados.
- ProcessingPage restaura source e command da tentativa existente. Antes de enviar, marca submitted=true; preserva tentativa em 503, projeção incompatível, interrupção e resposta pendente. Fechar o modal de uma tentativa submetida mantém a intenção e oferece apenas sua revisão. Não há nova chave automática, autosubmit ou botão para iniciar outro reprocessamento enquanto existe tentativa.
- Durante restoring o workspace sai da árvore e suas requisições abortam. A nova montagem só ocorre depois de validar o acesso; eligible também verifica !privileged.restoring. Respostas tardias não atravessam AbortSignal/geração. Os dados continuam apenas em useState/context, sem storage novo.
- Verifiquei estaticamente a integração backend: can_retry exige lineage_available; o registro original não é alterado artificialmente e can_reprocess fica falso quando há linhagem impeditiva. request_reprocess consulta replay existente autorizado antes de negar uma chave nova pela elegibilidade/linhagem. Esta é proteção complementar para reload, que perde legitimamente memória; a prova transacional real é do coordenador/backend.
- Li testes novos de 503 seguido de foco com validação atrasada, resposta de mutação atrasada durante restore, fechar/reabrir tentativa e revogação com resposta tardia. As asserções comparam comandos/chaves e negam sucesso tardio. Revogação também verifica aborto e descarte do id opaco.

### F10-FE-02 fechado

- validateReprocessing roda antes de consumir a tentativa ou exibir sucesso e exige id de execução novo em formato UUID, request_id UUID, ação/entidade iguais às revisadas, source_run_id igual ao source escolhido, versão positiva, status/códigos fechados, formato de datas e booleano de elegibilidade.
- SUCCEEDED requer também result_code/message_code COMPLETED. Projeção incoerente produz ApiError(503) e preserva o comando/chave para recuperação explícita. PENDING/RUNNING mantêm a mesma tentativa.
- O backend incluiu source_run_id em ProcessingView; a projeção Support o reduz a null. Assim a correlação de origem é verificável, em vez de inferida de um novo id.
- Li a matriz parametrizada que rejeita ação, entidade, source divergente/ausente, id inválido, versão zero, request_id ausente e status/códigos inválidos, sem sucesso e preservando o mesmo comando no replay válido.

### Evidência lida, não executada pelo revisor

- .phase10/frontend-review-red.log: 12 falhas / 14 aprovados, total 26, antes dos fixes.
- .phase10/frontend-review-green.log: 26/26 aprovados depois dos fixes iniciais.
- Dois testes adicionais de encerramento do modal e revogação constam no código final. .phase10/frontend-review-final-vitest.log registra 282/282 em 16 arquivos, sem skips reportados.
- .phase10/frontend-review-final-lint.log registra a execução de oxlint; .phase10/frontend-review-final-build.log registra build concluído com 75 módulos. Estes gates pertencem ao implementador; não os executei.
- Executei somente leituras e git diff --check -- frontend/src na re-revisão: limpo. Não fiz alterações de produto, testes, build, browser, comandos de banco ou commits.

Os achados originais abaixo ficam preservados como histórico da revisão e propostas RED. Seu estado final é fechado conforme esta seção.


## Escopo e evidência

Revisão estática independente do frontend congelado, do adendo executável do plano 10 e de .phase10/frontend-report.md. Li contratos/backend de processamento e correção para avaliar consequências. Não alterei produto, não executei testes, build, browser, banco ou commits; a concessão exclusiva de banco permaneceu com o coordenador.

Comandos executados: leitura dos arquivos, git branch --show-current, git diff do ajuste em AccessPages.test.tsx, git diff --check -- frontend/src (limpo) e busca no dist existente por FIXTURE_NODE_RENAME, Novo nome e preview_receipt (sem correspondências). A busca prova apenas o artefato existente, não um build realizado pelo revisor.

Os 268 testes/16 arquivos, lint/build GREEN e RED anteriores são evidência atribuída ao implementador em .phase10/frontend-report.md; não os reproduzi. Os RED abaixo são propostas não executadas.

## Achados originais — fechados após re-revisão

### F10-FE-01 — P1: revalidação por foco perde a identidade da tentativa

Locais: frontend/src/maintenance/ProcessingPage.tsx:15,23,24; frontend/src/privileged/PrivilegedProvider.tsx:96-103,118; frontend/src/platform/ContractShell.tsx:34.

Motivo, referência, versão e idempotency_key vivem apenas em ProcessingPage. Ao voltar o foco à janela, restore() define restoring=true; Shell substitui MaintenancePage pela validação e desmonta ProcessingPage. A chave é descartada mesmo quando o mesmo grant é revalidado como ACTIVE. O lock de PrivilegedProvider controla criação/encerramento do grant, não a mutação de ProcessingPage.

Cenário: a execução pode ter sido commitada, mas a resposta se perde/retorna 503, ou o foco muda durante o request. A revalidação monta nova ProcessingPage; o source original continua FAILED na mesma versão no backend revisado, e a revisão usa crypto.randomUUID() novamente. O backend pode executar novamente com outra chave. Cancelar fetch não desfaz commit. O teste atual cobre dois cliques no mesmo modal, sem desmontagem.

Correção: conservar a identidade da tentativa ambígua em memória por aba/contexto/grant/source fora do componente desmontado, ou manter o componente suspenso de maneira segura. Bloquear novo comando equivalente enquanto houver tentativa não reconciliada. Descartar dados em encerramento/revogação/expiração/troca de contexto. Não persistir dados de negócio/chave em storage nem reexecutar automaticamente. A proteção persistente de linhagem no backend é necessária para reload completo, que legitimamente perde memória.

RED proposto: submeter run FAILED, capturar chave, responder 503; disparar window.focus mantendo grant ACTIVE e atrasar validação até observar a tela de validação; concluir validação e repetir explicitamente. As submissões devem conservar chave e comando. Variante: resposta de mutação atrasada depois do unmount, simulando commit com resposta perdida; não aceitar sucesso tardio nem gerar chave nova/execução automática. Expiração/revogação devem continuar descartando tudo.

Coordenador recebeu e aceitou encaminhar RED/fix; informou proteção backend de linhagem para novas chaves após filho SUCCEEDED/PENDING/RUNNING/UNKNOWN e replay da mesma chave antes da elegibilidade. Essas alterações ainda não foram re-revisadas neste documento.

### F10-FE-02 — P2: SUCCEEDED sozinho confirma uma execução incompatível

Local: frontend/src/maintenance/ProcessingPage.tsx:23.

A resposta é somente um cast TypeScript; a condição de sucesso é value.status === 'SUCCEEDED'. HTTP200 com action_code/entity_id de outra operação, ou somente {status:'SUCCEEDED'}, encerra revisão, elimina chave e anuncia “Reprocessamento concluído e auditado.” Não há vínculo validado com a ação/entidade revisadas nem validação mínima do registro, ao contrário dos checks explícitos da correção.

Correção: validar a projeção e identidade disponível (ação/entidade iguais às revisadas, campos mínimos válidos segundo contrato) antes de declarar sucesso ou consumir tentativa. Se for exigida correlação explícita com source, ProcessingView não expõe source_run_id; alinhar contrato sem inferir vínculo a partir de id novo. Projeção incompatível deve produzir falha neutra e recuperação segura da mesma tentativa.

RED proposto: respostas HTTP200 SUCCEEDED com ação divergente, entidade divergente e projeção incompleta. Nenhuma anuncia sucesso ou cria nova chave. Resposta real válida permanece GREEN.

## Verificações favoráveis

- Menu requer PLATFORM_ADMIN e maintenance.authorize; Support não recebe navegação ou formulários de manutenção.
- Registry padrão Object.freeze([]); main.tsx não importa controlled-entry/FixtureRenameForm. Entry controlada registra adapter explícito de teste. Catálogo vazio usa texto aprovado, sem operação fictícia.
- Diagnósticos usam códigos/labels permitidos; não renderizam raw JSON/logs. request_id tem apresentação específica e filtro de formato.
- Grant exige referência/reautenticação e retorno com tipo/scopes solicitados. Financeiro/Fiscal separado. Banner contém empresa/contrato/ambiente/operador/motivo/referência/ação/entidade/prazo.
- AccessDialog fornece contexto às confirmações. Correção mostra antes/depois/efeitos, motivo/referência/versão; receipt apenas em memória.
- Prévia verifica ação, entidade, expected_version, before.version e formatos básicos. 409 remove prévia e exige atualização/revisão explícitas sem autosubmit. Apply valida ação/entidade e audit_event_id antes do sucesso.
- Revogação/expiração invalidam contexto; ApiClient rejeita gerações canceladas. Formulários abortam no unmount. Testes do implementador cobrem preview tardio após revogação, expiração e 403; falta a variante de reprocessamento do F10-FE-01.
- Reprocessar exige Admin, MAINTENANCE, elegibilidade do servidor, adapter conhecido, ação/entidade exatas do grant e status diferente de UNKNOWN. Mesma chave em retries dentro do mesmo modal.
- Storage contextual contém ids opacos por sessionStorage. Não encontrei nova persistência de payload/snapshots/motivo/receipt.
- AccessPages.test.tsx preserva exatamente a asserção contextual de access-history; apenas a envolve em waitFor. Sem remoção/enfraquecimento lógico.

## Limites e próximos gates

Responsividade 390x844, temas, teclado real e duas abas não foram executados por este revisor; são provas do coordenador.

Snapshot da fixture valida formatos, mas não todas as relações do adapter (after.version == expected_version + 1, after.name igual ao comando e campos não editáveis preservados). Backend atual recalcula e exige igualdade com preview no apply; não classifico como terceiro bug demonstrado. Recomendo respostas incoerentes na matriz de testes quando aplicável.

Os RED/fixes/GREEN e a re-revisão foram registrados na seção final acima; ambos os achados estão fechados.



## Adendo final — mensagem contextual de conflito 409

Re-revisado estaticamente o ajuste posterior em FixtureRenameForm.tsx:23 e sua asserção em Controlled.test.tsx:24. A UI substitui ErrorNotice genérico apenas enquanto conflict=true por um parágrafo role="alert" com “Os dados foram alterados desde a sua revisão.”, mantendo “Atualizar e revisar novamente”. O handleError continua descartando preview, confirmação e entidade no 409. A atualização permanece explícita, seguida de nova prévia; nenhuma submissão automática ou mudança de autorização foi introduzida. Nenhum novo bloqueador identificado; FE01 e FE02 permanecem fechados.

Li .phase10/frontend-conflict-red.log: a asserção do texto específico falhou antes do ajuste (1 falha; 27 casos fora da seleção focal). Li .phase10/frontend-conflict-green.log: os 32 testes de manutenção passaram em 2 arquivos após o ajuste, sem skips. O coordenador informou também novo gate completo posterior de 282/282 em 16 arquivos, zero skips, 19,16s, oxlint e TS/Vite com 75 módulos (sessão 97707); essa última execução é evidência atribuída ao coordenador, não executada por este revisor. O E2E controlado final e o gate backend ainda estavam sob responsabilidade do coordenador no momento deste adendo.

Executei somente leituras e git diff --check dos dois arquivos alterados, limpo. Nenhum teste, build, browser, acesso ao banco ou alteração de produto nesta re-revisão.

## Consolidação do coordenador após o gate final

O coordenador confirmou pytest completo 700/700, zero skips, 614.20s (sessão16590), Vitest282/282, oxlint/TypeScriptVite/Ruff, E2E real normal/controlado e inspeção das capturas. A migração recebeu somente limpeza de whitespace final; ciclo físico/grants repetidos4/4GREEN. Nenhuma alteração funcional de produto após a revisão final. Serviços, PostgreSQL descartável e segredos temporários foram removidos. Esta consolidação não atribui execução ao revisor independente; phase-10.md reúne a evidência final.
