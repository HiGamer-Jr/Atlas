# HiAtlas — operação da fundação da plataforma (Fase11)

Este guia cobre a aplicação real das fases1–11. Não houve deploy, acesso a banco de produção ou cadastro de handler de domínio de produção. A aplicação normal conserva registry de manutenção vazio; handlers controlados pertencem somente às fixtures. O frontend antigo demonstrativo não autentica nem concede privilégios.

## Dependências e identidades

Python>=3.13.15 com uv/backend/uv.lock, PostgreSQL18.6 com psql/pg_dump/pg_restore/pg_ctl, Node22.12+ ou24LTS e npm/frontend/package-lock.json. A prova local usou binários Windows indicados por https://www.postgresql.org/download/windows/ e distribuídos por EDB: https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64-binaries.zip . SHA256 ZIP observado FBE23DA234EE31547BF8A36D29DFD81E82B849DF2D2B78D2EECB43D360252F8C (integridade local; não assinatura independente).

Provisionar owner/runtime/recovery separados. Owner possui banco/objetos mas não é superuser. Runtime/recovery são logins distintos sem SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS, associação ao owner ou objetos próprios. Runtime não tem CREATE no banco/public, SELECT em alembic_version ou DELETE em negócio; eventos são SELECT/INSERT sem UPDATE/DELETE/TRUNCATE. Tabelas técnicas recebem grants explícitos por migração. Migration0010 instala no recovery SELECT das tabelas necessárias e UPDATE somente das colunas de recuperação; auditoria recebe INSERT e SELECT(id,occurred_at,action,entity_id,reference) para RETURNING e verificação de uso prévio do incidente, sem acesso a snapshots/payloads. Definir RECOVERY_DATABASE_ROLE durante migração. Owner/recovery nunca entram no ambiente da API.

Segredos vêm de cofre ou arquivo externo ao Git com ACL restrita. Não imprimir ambiente/URLs/senhas/cookies/tokens/ciphertext/dumps. pgtools usam PGPASSFILE protegido; PGPASSWORD somente em processo controlado, nunca senha em argv. Dumps são sensíveis: cifrar armazenamento, limitar ACL, retenção e ensaio regular conforme RPO/RTO definidos na implantação.

## Preparação e configuração

Na raiz:

```powershell
Set-Location backend
uv sync --frozen
# Processo de migração: MIGRATION_DATABASE_URL, DATABASE_RUNTIME_ROLE, RECOVERY_DATABASE_ROLE.
uv run --frozen alembic upgrade head
uv run --frozen alembic current
Set-Location ../frontend
npm.cmd ci
npm.cmd run build
```

API recebe somente DATABASE_URL do runtime, ENVIRONMENT=production e PUBLIC_ORIGIN HTTPS exata sem caminho/barra final. OUTBOX_KEY Fernet válida deve ser persistente; guardar a chave correspondente ao backup separadamente. EMAIL_DELIVERY_ENABLED deve ser explícito: true exige SMTP_HOST/PORT/SENDER e par USERNAME/PASSWORD coerente; false desativa entrega real sem simular sucesso. Configurar timeout/limites. Produção recusa outbox ausente e SMTP incompleto quando entrega habilitada. Worker recebe runtime. Sem registrar bodies/cookies/links de convite no proxy/APM.

Frontend e /api usam a mesma origem HTTPS; cookies __Host- são Secure/HttpOnly/SameSite=Strict. Proxy termina HTTPS e encaminha para loopback. TRUSTED_PROXY_IPS é lista JSON explícita de peers autorizados; vazia por padrão. Proxy sobrescreve origem de rede. Não confiar indiscriminadamente em X-Forwarded-For nem reescrever request.client no ASGI.

## Inicialização, saúde e parada

No backend, com ambiente da API:

```powershell
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Publicar frontend/dist no servidor HTTPS autorizado; vite preview é verificação local. GET /api/health e /api/health/live são liveness. /api/health/ready verifica conexão runtime e acesso às tabelas, retorna503 em falha; startup de produção recusa pré-requisitos físicos inválidos. Readiness não garante SMTP nem todas as regras de negócio; verifica também as colunas mapeadas da fundação. Antes de liberar tráfego verificar revisão Alembic, grants, HTTPS/CSRF, login real e transporte/outbox.

```powershell
uv run --frozen python -m app.identity.delivery --once --limit 20
```

Agendador chama lotes limitados. Retry usa limites/backoff; UNKNOWN não tem replay automático. Monitorar estados/códigos sanitizados/request_id, sem token/ciphertext. Nunca limpar auditoria. Para parar retirar tráfego, impedir lotes novos, aguardar requests/transações e encerrar API/worker graciosamente. Cluster portátil descartável: pg_ctl stop -D <diretorio-validado> -m fast -W, aguardar processo explicitamente. Não usar immediate normalmente. Helpers Windows usam Start-Process -WindowStyle Hidden. A instância de teste fica ativa até os gates finais; cleanup somente mediante pedido do coordenador, caminhos absolutos resolvidos/contidos e sem ReparsePoint.

## Backup e restore

Como ponto de partida operacional, realizar backup lógico diário e antes de cada atualização relevante; ajustar frequência ao RPO e volume efetivamente aprovados. Retenção não é SLA desta fundação: o responsável deve decidir janelas diárias/semanais, armazenamento separado, cifragem, acesso e descarte. Conferir cada backup e ensaiar restore periodicamente, por exemplo mensalmente e após mudanças de PostgreSQL/migração. Essas são recomendações de procedimento; nenhum agendador foi criado nesta fase.

1. Registrar commit/revisão Alembic/PostgreSQL, roles, referência do incidente/prova e hash do backup. Preservar OUTBOX_KEY correspondente em cofre separado.
2. Com PGHOST/PGPORT/PGUSER/PGDATABASE explícitos e PGPASSFILE do owner: pg_dump -Fc --file <arquivo-protegido.dump> . Conferir exit code e pg_restore --list <arquivo-protegido.dump>. Nunca URI com senha em argv.
3. Criar banco NOVO isolado com owner não superuser e roles esperadas; pg_dump não cria logins. Restaurar como owner: pg_restore --exit-on-error --dbname <novo-banco> <arquivo-protegido.dump>. Preservar ACLs; não usar --no-acl sem reaplicar/verificar todos os grants. Não sobrescrever banco original nem usar --clean no alvo de produção.
4. Manter API/SMTP/worker desconectados do banco novo. Verificar revisão, FK/referências/contagens, organização, auditoria histórica e grants físicos runtime/recovery. Revisar estados UNKNOWN e efeitos externos sem replay automático. Rotacionar credenciais comprometidas.
5. Backup pode ressuscitar sessões/contextos/grants/tokens revogados posteriormente. Executar política fixa antes do tráfego, como owner somente no processo offline:

```powershell
# PGDATABASE/PGUSER identificam o banco NOVO e owner; senha em PGPASSFILE.
psql -v ON_ERROR_STOP=1 -v expected_database=<novo-banco> -v technical_operator=<operador-tecnico> -v incident_reference=<incidente> -f database/post-restore-invalidate.sql
```

O SQL valida banco esperado/owner não superuser e evidência mínima. Revoga auth_sessions/access_contexts/support_sessions/temporary_privileged_grants, apaga preauth, invalida convites/reset não consumidos e cancela outbox pendente apagando ciphertext. Preserva negócio, auditoria histórica e contadores de rate limit; SENT/FAILED/UNKNOWN e ProcessingRun não são reexecutados. Grava identity.restore.invalidated com operador técnico/role reais na mesma transação. Falha reverte todas as mudanças e o banco novo permanece fechado. É procedimento offline de infraestrutura autorizado, sem endpoint de aplicação ou ferramenta genérica de correção. Históricos hasheados revogados não autorizam sessão. Novos convites/reset devem ser emitidos pelo fluxo normal após reabertura.

6. Validar login novo, negação das sessões restauradas, revogações, contexto por aba e auditoria; responsável operacional libera tráfego/worker. Em host distinto também provisionar extensões, TLS, armazenamento e versão compatível. A prova valida dump/restore lógico PostgreSQL18.6; não valida PITR/failover ou recuperação física.

## Atualização e rollback

Backup ensaiado, compatibilidade aplicação/schema, janela de manutenção e plano de retorno antecedem atualização. Aplicar migrações com owner, validar revisão/grants e instalar backend/frontend da mesma versão. Smoke HTTPS antes de tráfego. Falha exige retirar tráfego; retornar binário anterior somente se compatível com schema atual. Para retorno de dados/schema restaurar backup em banco novo, aplicar invalidação técnica e trocar conexão controladamente. Não executar downgrade cego em produção. Fullbase/head e0010down/up foram ensaiados exclusivamente em banco descartável; downgrade0010 revoga também privilégios por coluna do recovery.

Recuperação administrativa de identidade existente é distinta de restore/rollback: consultar guia de recuperação offline da Fase11. Bootstrap nunca reabre quando existe histórico do primeiro administrador. Administrador ativo/desbloqueado com senha esquecida usa primeiro o reset normal. Somente o caso excepcional de único administrador, canal normal indisponível e atestado protegido pode usar --credential-loss, conforme procedimento abaixo. Recovery exige referência/evidência concreta, alvo existente verificado/confirmado e senha getpass; sem senha em argv/pipe.

## Ensaio local e evidência

backend/tests/database_harness.py exige banco _test marcado hiatlas-disposable-test-db, identidade real/endpoint igual e roles seguras. HIATLAS_TEST_DATABASE_RESET=1 é obrigatório; não há SQLite/fallback/skip. Nunca executar suítes concorrentes no mesmo banco.

```powershell
# Ambiente protegido externo: TEST_DATABASE_OWNER_URL, TEST_DATABASE_RUNTIME_URL,
# HIATLAS_TEST_RECOVERY_DATABASE_URL, RECOVERY_DATABASE_ROLE, HIATLAS_TEST_DATABASE_RESET=1.
# Também PGHOST/PGPORT/PGUSER/PGPASSWORD (admin exclusivo de teste), PATH dos pgtools,
# PHASE11_TEMP em diretório temporário protegido. Nunca imprimir ambiente.
Set-Location backend
uv run --frozen python ../scripts/phase11_operations.py
uv run --frozen pytest
```

Proof recusa quaisquer dados preexistentes e executa full0001–0009, incremental0008–0009/0009–0010,0010down/up e fullbase/head. Verifica grants reais e negações SQLSTATE42501. Semeia somente identidades/tenant/contrato/OrganizationNode COMPANY/evento/sessão sintéticos, cria dump e restaura em banco novo. Cria fixtures técnicas adicionais somente no restore e prova invalidação de sessões/contextos/suporte/grants/preauth/tokens/outbox. CHECK descartável força falha de auditoria e prova rollback atômico de todos os estados antes do sucesso. Senha Argon2id aleatória fica somente em memória: sessão antiga401, login novo200/logout204. Não elimina bancos automaticamente; administrador remove só alvos atestados após coleta.

Ensaio final2026-10-05 PASS em PostgreSQL18.6 loopback55491: fonte final hiatlas_phase11_opsproof2_test, restore novo hiatlas_phase11_restore_653bb2ce_test. COMPANY anterior ao dump manteve id/tenant+contract FK/code/version7. Hash dump final57a19f48e3c675dde43c8795a10e7ef2cae56bf699ea531420f8e1105f42c69b. Primeiro ensaio hiatlas_phase11_test -> hiatlas_phase11_restore_test também PASS; fixtures fonte removidas antes do gate completo. Relatório sem segredos TEMP/operations-result.json; dump protegido fora do Git.

Access logs ASGI ficam desativados. No reverse proxy, registrar somente path (ex.: $uri), status e request_id da resposta; excluir $args/$request/$request_uri, bodies, cookies e Authorization. Evitar qualquer URL/query bruto. Erro interno registra somente request_id sanitizado. Recovery --credential-loss exige atestado UUID protegido adicional, prova de SMTP indisponível pela Settings real, nenhum OUTRO administrador utilizável e uso único do mesmo incidente/alvo/referência. Banco não demonstra conhecimento da senha; o operador de infraestrutura é fronteira de confiança.

A comparação determinística de catálogo incremental0009–0010 versus freshbase–head também PASS: tipos/null/defaults de todas as colunas, constraints, índices, ACLs de tabela e coluna iguais, sem OIDs. Ensaio final usa a migration0010 com projeção estreita da auditoria para RETURNING/verificação de incidente; fonte sintética limpa automaticamente após a prova.


## Cabeçalhos do HTML e assets de produção

Servidor HTTPS/reverse proxy deve aplicar também a frontend/dist e seus assets: Referrer-Policy: no-referrer; X-Content-Type-Options: nosniff; X-Frame-Options: DENY; e Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'. HTTPS de produção usa Strict-Transport-Security: max-age=31536000. A política não admite unsafe-eval/unsafe-inline para scripts; o build inclui scripts externos da mesma origem. Esses cabeçalhos devem proteger respostas HTML/estáticas, não somente /api. Desabilitar access log ASGI e, no proxy, registrar path sanitizado ($uri), status e request_id; excluir query ($args/$request_uri/$request), cookies, Authorization e bodies.

A verificação reproduzível usa scripts/phase11_browser_checks.ps1 -EnvironmentFile <arquivo-protegido> -Phase 10 -Mode normal -Build. O factory exclusivamente de teste serve frontend/dist por HTTPS sob os mesmos middlewares, sem instalar servidor de produção nem cadastrar rota em app.main. frontend/e2e/phase11-build.mjs verifica Chrome real, bundle /assets, cabeçalhos exatos e zero violações CSP/pageerror; o harness normal executa login/Admin/Suporte na aplicação real. Rodar também fases05–10 normal e10 controlled no runner, uma de cada vez em slot exclusivo do banco atestado. As cópias TEMP do harness alteram somente caminho de evidência para phase-11-visual, preservando capturas aprovadas anteriores. Helper de senha aleatória é restrito ao seed atestado com HIATLAS_PHASE11_E2E=1; não usa sitecustomize nem altera código de produção. O runner registra PID próprio e encerra somente API/Vite criados; PostgreSQL permanece para gates do coordenador.


O runner rejeita o banco de integração fonte mesmo quando marcado descartável: antes de clean valida URLs por SQLAlchemy sem imprimir credenciais, exige banco hiatlas_phase11_e2e_test, logins phase11_e2e_owner/phase11_e2e_runtime e endpoint127.0.0.1:55491, PUBLIC_ORIGIN/HIATLAS_E2E_ORIGIN https://localhost:5181, API_TARGET http://127.0.0.1:8011 e reset explícito. Depois a fixture confirma marcador/identidades no PostgreSQL real. Manifest deriva banco/roles somente dessa configuração validada. RED puro mostrou fonte aceita antes do guard (exit0); GREEN mostrou fonte recusada exit1 e E2E dedicada aceita exit0, sem chamar clean no ensaio de configuração. E2E usa banco/roles distintos do pytest, permitindo execução concorrente com o gate fonte sem compartilhar runtime.

## Bootstrap e recuperação administrativa offline

Para a instalação inicial, depois das migrações e com somente a configuração runtime no processo local autorizado, executar em terminal protegido:

```powershell
Set-Location backend
uv run --frozen python -m app.identity.bootstrap --email <email-do-primeiro-administrador>
```

A senha é solicitada interativamente; não a passar em argumentos, pipes, logs ou arquivos. Bootstrap fecha definitivamente após o evento inicial e não é mecanismo de recuperação.

Para break-glass, abrir incidente autorizado, verificar a identidade alvo e a aprovação da organização fora de banda, registrar operador técnico/motivo/evidência e confirmar que o fluxo normal não resolve. Usar ambiente offline isolado com RECOVERY_DATABASE_URL/RECOVERY_DATABASE_ROLE da identidade de recuperação provisionada e grants da migration0010; nunca disponibilizar essa identidade à API/worker. Settings do mesmo ambiente devem refletir a configuração real e ENVIRONMENT explícito. O comando compara o login de recuperação com o runtime e recusa identidades privilegiadas indevidas.

```powershell
Set-Location backend
uv run --frozen python -m app.identity.recover_admin `
  --environment PRODUCTION `
  --user-id <uuid-administrador-existente> `
  --technical-operator <identificacao-do-operador-tecnico> `
  --reason "<motivo-verificado>" `
  --reference "<incidente>" `
  --incident-evidence "<referencia-da-evidencia-verificada>" `
  --verified-email <email-verificado-fora-de-banda> `
  --confirm-user-id <mesmo-uuid>
```

O exemplo apenas documenta operação futura autorizada; não foi executado em produção. Para a única identidade administrativa com hash existente e credencial perdida, adicionar --credential-loss; o programa exige outro prompt protegido com UUID e atestado de perda, identidade/aprovação externas e indisponibilidade do canal normal. A flag sozinha não autoriza. SMTP configurado disponível ou qualquer outro administrador utilizável fazem o procedimento recusar. Não alterar configuração apenas para contornar a recusa: resolver o fluxo normal ou submeter o incidente à autoridade de infraestrutura. O banco não comprova perda da senha; a responsabilidade do atestado é dessa autoridade, com registro auditável.

Após confirmação protegida da nova senha, recuperação e auditoria são atômicas: identidade administrativa existente restaurada, sessões/contextos/atendimentos/grants e tokens pendentes revogados, outbox pendente cancelada. Não cria usuário, papel novo ou senha padrão. Mesmo alvo/incidente não pode ser reutilizado; chamadas concorrentes são serializadas. Falha de auditoria impede alteração. Validar novo login em HTTPS, negar sessões anteriores, revisar evento e retirar a credencial de recuperação do processo de operação. Não copiar senha ou segredo para o relatório do incidente.

## Ordem de implantação autorizada

1. Aprovar janela e versão; verificar configuração, compatibilidade e backup validado.
2. Aplicar migrações com owner em processo separado e verificar revision/grants.
3. Instalar/iniciar backend com runtime e frontend compilado da mesma versão, protegidos por HTTPS e headers do HTML/assets.
4. Iniciar worker/outbox controlado conforme configuração de delivery; não simular SMTP.
5. Verificar readiness, logs sanitizados e sanity não destrutivo antes de liberar tráfego.
6. Registrar resultado e plano de retorno. Para restart/shutdown usar a retirada de tráfego e encerramento gracioso descritos acima; comandos específicos de serviço dependem da infraestrutura escolhida, não de um gerenciador instalado por esta fase.

A Fase11 documenta esta sequência e ensaia somente infraestrutura descartável. Não realiza deploy, push, merge ou criação de ambiente demo.
