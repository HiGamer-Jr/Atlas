# Fase 9 — revisão independente backend

Data: 2026-10-03. Revisor independente da implementação backend; participação anterior limitada à preparação do PostgreSQL descartável.

Escopo: revisão estática de `snapshot backend preliminar (temporário)`, fontes atuais de grants/gate/services/schemas/registry, migração 0008, políticas RBAC, observer/get_db, autenticação e plano 09/adendo aprovado. As fontes estavam sendo modificadas pelo implementador; esta revisão não representa aprovação final do diff. Nenhum teste ou alteração de banco foi executado pelo revisor.

## Achados importantes

### B09-01 — P2 — concessão expirada bloqueia novo pedido no contexto pai

Referências do snapshot: `backend/app/grants/gate.py`, seleção inicial apenas por `context_id`; `backend/app/grants/services.py`, `start`, consulta ACTIVE por parent.

Reprodução proposta: criar concessão com duração curta, avançar além da expiração, reautenticar novamente e pedir nova concessão utilizando somente o contexto pai, sem consultar o contexto derivado antigo. Esperado: terminalização auditada da antiga e criação de nova concessão autorizada. Código inicial revisado: a gate não observa a antiga no parent e `start` encontra ACTIVE, respondendo 409 indefinidamente até observação/encerramento explícito do child. O root informou ter encontrado o mesmo caso e encaminhado reprodução RED ao implementador.

Estado: pendente confirmação RED/correção/GREEN pelo implementador; revisão estática final deve conferir diff atualizado.

### B09-02 — P2 — falta revalidação depois do resolver de entidade na leitura privilegiada

Referência: `backend/app/grants/gate.py:63` a `:71` no snapshot revisado.

`require_capability` revalida o grant antes de `entity_scope`. O resolver pode esperar lock e ultrapassar o prazo; após retornar true, a gate permite a requisição sem nova validação temporal. Reprodução proposta somente em fixture: módulo FINANCE operacional controlado, leitura explicitamente declarada, resolver de entidade bloqueando/avançando relógio além do prazo e retornando true. Esperado 403 após espera; ramo revisado permite continuar para endpoint sem get_db (sem segunda guard transacional). Revalidar a concessão depois do resolver e antes de liberar a leitura, mantendo observação terminal e auditoria atômica.

Estado: comunicado ao root; não houve execução de teste pelo revisor.

### B09-03 — P2 — schema de escopo aceita entrada que viola a unicidade física

Referências: `backend/app/grants/schemas.py:40` no snapshot; `backend/alembic/versions/0008_temporary_privileged_grants.py:80`.

O schema rejeita duplicidade da tripla action/entity_type/entity_id, aceitando duas entidades distintas para a mesma action. A constraint física permite somente uma action por grant. Com ação registrada controlada e duas entidades válidas do mesmo contrato, a validação passa e o segundo INSERT falha com IntegrityError/500. Alinhar schema e constraint: rejeitar ações repetidas previamente com 422 se esse for o contrato, ou permitir múltiplos escopos de entidade com constraint coerente. Registry vazio em produção limita exposição atual, mas a infraestrutura de autorização permanece inconsistente.

Estado: comunicado ao root; não houve execução de teste pelo revisor.

## Observações positivas verificadas estaticamente

- Principal permanece operador real; vínculo composto exato entre operador, AuthSession, contexto pai/derivado e contrato.
- Tipos e status fechados; lifecycle/versionamento com auditoria na mesma transação.
- Runtime das tabelas novas sem DELETE/TRUNCATE; migração separada do runtime.
- Financeiro não altera disponibilidade operacional; registry produtivo vazio; nenhuma rota genérica SQL ou handler operacional fictício encontrado no escopo revisado.
- Contexto pai/aba independente não herda a capacidade financeira do child.
- SupportSession conserva a gate READ_ONLY e é verificada antes da gate privilegiada.

Essas observações são leitura de fonte, não resultados de testes. Gate final, concorrência, isolamento, upgrade/downgrade/upgrade e E2E são responsabilidade da validação executada e ainda precisam de evidências. Aprovação final somente após diff atualizado e tratamento RED/GREEN de todos os achados relevantes.
## Revisão final do backend congelado

Revisado o snapshot o diff backend final contra a base aprovada, os arquivos atuais de grants/gate/services/schemas e migração 0008 e o relatório o relatório consolidado `phase-09.md`. A seção preliminar acima preserva os achados originais; seus estados pendentes foram superados pelas conclusões seguintes.

- **B09-01 resolvido:** `start` obtém/revalida a concessão anterior e persiste seu estado terminal com auditoria antes de permitir um novo grant; há regressão para pedido somente no parent após expiração e nova reautenticação. RED 409 e GREEN 201 atribuídos à execução do implementador, conforme relatório.
- **B09-02 resolvido:** a gate chama `lock_bound` novamente depois do resolver da entidade, terminaliza atomicamente se necessário e nega leitura. Regressão controlada sem Database verifica expiração durante resolver e auditoria. RED 200 e GREEN 403 atribuídos à execução do implementador.
- **B09-03 resolvido:** schema passou a permitir somente uma `action_code` por concessão, coerente com a constraint física. `entity_type` inicial é fechado em `organization_node`, e a FK composta protege entidade/tenant/contrato. RED executado em cópia isolada do schema legado aceitou duas entidades para a mesma ação (DID NOT RAISE ValidationError); GREEN no schema atual e resposta API 422 atribuídos ao implementador. **O antigo 500 potencial não foi executado** e não deve ser descrito como resultado observado.

Também conferida a correção adicional: uma leitura financeira explicitamente declarada falha sem grant/contexto derivado mesmo que a rota não tenha dependency Database. Não foram encontrados novos achados relevantes no escopo do diff final revisado.

Conclusão: **revisão estática backend sem achados relevantes pendentes**, após as correções acima. Não é declaração de quality gate completo. Este revisor não executou testes, não operou o banco durante a revisão e não alterou código de produto.

Evidência focada atribuída ao implementador: 70 casos de matriz integrada, três testes de contrato, 14 corridas e 22 casos PostgreSQL/schema preparados para integração final; execuções exatas e RED/GREEN descritas em o relatório consolidado `phase-09.md`. O relatório registra 70 passes na matriz inicial, dois casos adicionais de política de manutenção, três passes de contrato e 36 passes de races/schema, todos sem skips, além de Ruff. A soma final de cobertura e o pytest completo devem ser confirmados pelo root no gate integral. Full pytest, E2E e gate final ainda estavam sob execução/coordenacão do root no momento desta revisão.

Limitações preservadas: registry de manutenção vazio em produção, ausência de handlers operacionais e módulos ainda indisponíveis. Expiração/revogação são negadas imediatamente pelo estado vigente na autorização; persistência do estado terminal e auditoria ocorre na observação segura/controle, sem worker automático de expiração.
