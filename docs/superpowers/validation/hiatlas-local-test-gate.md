# HiAtlas — gate local Windows com PostgreSQL portátil

## Escopo e isolamento

- Branch: `chore/hiatlas-local-test-gate`.
- Worktree exclusiva: `D:\Atlas\.worktrees\hiatlas-local-test-gate`.
- Base solicitada: `release/hiatlas-demo-v1`, `1277afae61e349d01d04f551d505e5e491de9e29`.
- `main` não foi usada como base nem investigada/alterada nesta tarefa.
- Referência release usada somente como fonte; nenhuma operação na worktree,
  banco, serviço ou VPS da Demo. Sem push, merge, tag ou deploy.
- As pastas não rastreadas `.tmp/` e `.tools/` do checkout original foram
  preservadas. A distribuição portátil já existente foi usada somente para
  executar binários, nunca instalada/modificada ou baixada pelo helper.
- Commit da entrega: o commit local que contém este relatório.

## Implementação

- `scripts/testdb.psm1`: estado privado em memória, distribuição mínima/versionada,
  senhas aleatórias, ACL, paths seguros, bind/porta, bootstrap, conexões reais,
  marcador, environment/process/native exit codes e cleanup restrito.
- `scripts/testdb-start.ps1`, `testdb-stop.ps1`: ciclo manual na mesma janela.
- `scripts/check-local.ps1`: agregador fail-closed, gate canônico e finally.
- `scripts/check-platform-foundation.ps1`: atestação adicional quando o helper
  possui o cluster; execução explícita dos testes/lint Windows sem alterar os
  comandos canônicos existentes.
- `scripts/tests/test_local_testdb_scripts.py`: testes sem PostgreSQL instalado,
  usando processos Windows reais e doubles apenas da fronteira de recursos
  para verificar o finally do agregador.
- `scripts/tests/testdb-lifecycle.ps1`: teste opcional real, sempre com outro
  cluster novo descartável, inclusive marcador/ambiente adulterados.
- `backend/tests/test_local_gate_collection.py`: regressão de coleta sem dependência
  de `SystemRoot` depois de inicializar as bibliotecas necessárias do Windows.
- `database/README.md`: fluxo, pré-requisitos, segurança e recusas.

`backend/tests/database_harness.py` e `database/test-bootstrap.sql` permanecem
inalterados. Sem SQLite, novos skips, migrations, domínio funcional, Data Hub,
Workspace, contexto de cliente, DeploymentBanner ou BUG-03 nesta entrega.

## RED / correção / GREEN

1. Infraestrutura ausente: 21 testes novos falharam antes da implementação.
2. Probes nativos iniciais com `cmd.exe` expuseram sua sintaxe especial; foram
   substituídos por processos executáveis controlados, sem mock de exit code.
3. O ciclo real evidenciou pipe herdado do daemon Windows e cast `inet::text`
   retornando máscara `/32`. O lançador tem descarte limitado da saída sem
   leitor assíncrono pendente; consultas usam `host(inet_server_addr())`.
   Probe nativo rápido confirma que um filho segurando pipe não retém o helper.
4. Revisão independente reproduziu coleta backend com `KeyError: SystemRoot`.
   Os testes Windows foram movidos para `scripts/tests` e integrados explicitamente
   ao gate; regressão de coleta GREEN sem introduzir skip.
5. Arquivo de senha bloqueado reproduziu a necessidade de remoção terminante;
   `Remove-InitPassword` recusa continuar se a remoção/ausência não for provada.
6. Cenários STARTING/BOOTSTRAP sem PID reproduziram remoção indevida de diretório.
   Lifecycle agora distingue INITIALIZING/INITIALIZED e recusa ausência de PID
   depois de qualquer tentativa sem prova suficiente; regressões GREEN.
7. Nova revisão estática independente: sem achados relevantes pendentes. O
   revisor não executou testes nem modificou arquivos/processos/bancos. RED/GREEN
   e validações reais foram executados pelo implementador.

## Verificações já executadas

- PowerShell: parser dos seis arquivos PS sem erros.
- PostgreSQL portátil 18.6: ciclos reais completos em Windows PowerShell 5.1 e
  PowerShell 7, com pg_isready, owner/runtime/recovery autenticados, marcador,
  flags e ownership conferidos e cluster removido.
- Teste lifecycle real após correções: PASS para ambiente adulterado, start
  duplicado específico, marcador ausente negando testes/cleanup, restauração
  apenas no próprio banco de fixture, cleanup e environment restore.
- Regressão focada final: 40 testes PASS (35 scripts, quatro gate legado,
  uma coleta backend); sem banco permanente e sem skips.
- Primeira regressão integrada: 796 backend PASS (antes da separação física dos
  testes Windows), 284 frontend PASS, Ruff e oxlint PASS, TypeScript/Vite PASS,
  diff da árvore e índice PASS. O agregador dessa primeira execução retornou erro no cleanup; não foi considerado PASS integrado.
- Uma chamada diagnóstica de Ruff a partir da raiz encontrou diferenças na
  classificação de imports; os comandos canônicos executados no diretório
  backend passaram. Nenhum import de produto foi alterado para contornar isso.
- Warning herdado Starlette/httpx é depreciação; não houve atualização de
  dependências nem alteração da arquitetura por esse warning.

## Gate final

VALIDATED — segunda execução completa do agregador com exit code 0:

- Backend: 768 testes passaram, zero skips.
- Testes dos scripts nessa execução: 34 passaram; o teste adicional de stop foi
  executado depois, totalizando 35 testes dos scripts e 40 na regressão focada final.
- Frontend: 284 testes passaram, 17 arquivos, zero skips.
- Ruff backend/scripts, oxlint, TypeScript/Vite build e git diff --check passaram.
- PostgreSQL portátil 18.6, Windows PowerShell 5.1, roles distintas e conexões
  reais, gate canônico e cleanup automático concluíram com sucesso.
- Após a última correção de stop: regressão focada de 40 testes, Ruff e novo
  lifecycle real passaram; não foi repetida a suíte inteira de domínio por essa
  alteração isolada do controle de processo.

A primeira execução teve os checks individuais GREEN, mas cleanup recusado.
O cluster já estava parado; seu diretório residual foi removido somente após
validar caminho/seal, ausência de PID/processo e leitura offline positiva do
marcador no diretório exato criado pela execução. Isso não introduz recuperação
ou descoberta automática no produto.

Um probe controlado reproduziu falso erro de stop com exit code 0 e pipe herdado
por processo filho (RED). O stop passou a descartar saída como o start; teste
GREEN e lifecycle real confirmam o comportamento. Diagnósticos de cleanup
informam somente etapa e categoria sanitizadas, sem imprimir a exceção bruta.

## Riscos e limites

- Windows PowerShell 5.1/PowerShell 7 e PostgreSQL portátil 18.6 são o escopo
  inicial; novos releases/distribuições precisam de validação explícita.
- A corrida entre reserva de porta e bind existe: conflito aborta com fail-closed,
  sem tentativa de reutilizar outro servidor.
- Encerramento forçado da janela/processo ou falha de energia pode impedir
  finally; não há rediscovery automático ou serviço de supervisão.
- Falta de marcador, processo não comprovável ou reparse point impede cleanup;
  artifacts próprios podem ficar para investigação. Segurança prevalece sobre
  remoção automática em condição incerta.
- Credenciais são restritas ao processo/cluster temporário; memória e arquivos
  de infraestrutura devem ser tratados como privados pelo operador Windows.
- Distribuição incompleta/falta de dependências aborta; não há download/fallback.
- Nenhum deploy ou banco real foi usado para validar a entrega.
