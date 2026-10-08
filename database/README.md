# HiAtlas — Banco, auditoria e persistência de identidade (Fases 1–2)

O backend usa PostgreSQL e **uv já é o gerenciador canônico** (uv.lock, README e
scripts/check.ps1). A Fase 2 preserva esse gerenciador e acrescenta apenas argon2-cffi e suas dependências ao lockfile.

## Limites desta entrega

Migração 0001: users, platform_role_assignments, tenants, contracts, audit_events
e access_events. A migração 0002 acrescenta auth_sessions, auth_preauth e
auth_rate_limits. A Fase 2 implementa autenticação, bootstrap local e operadores
internos; consulte [o guia operacional](../docs/operations/hiatlas-identity.md).
A separação referencial tenant/contrato não substitui o contexto/autorização que
serão implementados na Fase 3.

## Identidades e privilégios

A aplicação e as migrações usam identidades distintas em banco exclusivo do HiAtlas.
O owner de migração possui o banco e seus objetos, mas não é superusuário.
O runtime não possui objetos, não herda roles e não tem SUPERUSER, CREATEDB,
CREATEROLE, BYPASSRLS ou CREATE em public/banco.

| Categoria | Tabelas desta fase | Runtime |
|---|---|---|
| Identidade/configuração de negócio | users, platform_role_assignments, tenants, contracts | SELECT, INSERT, UPDATE |
| Trilha append-only | audit_events, access_events | SELECT, INSERT |
| Controle técnico de migração | alembic_version | nenhum |
| Identidade técnica (0002) | auth_sessions, auth_preauth, auth_rate_limits | SELECT, INSERT, UPDATE, DELETE; sem TRUNCATE |
| Técnica futura | tokens de convite/redefinição e filas — ainda não criadas | grants explícitos conforme ciclo de vida |

DELETE/TRUNCATE permanecem negados para negócio; UPDATE/DELETE/TRUNCATE para
eventos. Tabelas técnicas não recebem uma proibição universal nem grants
automáticos: sua migração define o mínimo necessário. Não há GRANT ALL/default
para novas tabelas. O teste de categoria técnica prova DELETE explícito em tabela
temporária de teste sem liberar TRUNCATE nem permissões na auditoria.

O runtime tem USAGE em public e CONNECT no banco. Migração remove CREATE de
public e CREATE/TEMPORARY herdados de PUBLIC nesse banco dedicado.
Grants não usam SECURITY DEFINER. A aplicação também recusa conexões de owner
ou identidade administrativa na dependência get_db.

## Configuração de execução

- DATABASE_URL: URL postgresql+psycopg do runtime.
- MIGRATION_DATABASE_URL: URL do owner, **somente no processo de migração**.
- DATABASE_RUNTIME_ROLE: nome do runtime já provisionado, usado pela migração.
- Não compartilhar esses acessos com outros projetos nem gravar senhas no Git.
- Settings do servidor não carrega a credencial do owner; MigrationSettings é
  usado apenas pelo Alembic. Alembic não faz fallback para DATABASE_URL.
- As variáveis são fornecidas ao processo; este código não carrega .env
  automaticamente. .env.example é apenas documentação sem credenciais reais.

Após provisionar owner/runtime por administração de infraestrutura autorizada,
no diretório backend com as variáveis de migração presentes:

```powershell
uv sync --frozen
uv run --frozen alembic upgrade head
uv run --frozen alembic current
```

Os grants dependem de introspecção real de roles, por isso o modo Alembic --sql
offline é recusado. Rollback de schema é ferramenta de infraestrutura; os testes
fazem downgrade/upgrade apenas em banco descartável. Não executar downgrade em
banco real como procedimento de correção de dados.

## Testes com PostgreSQL real

Não há fallback SQLite nem skips quando falta banco. Use uma instância isolada
e um banco descartável, nunca atlas ou outro banco com dados de aplicação.

1. Um administrador da instância de teste executa database/test-bootstrap.sql
   com psql. Ele cria hiatlas_test_owner, hiatlas_test_runtime e o banco
   hiatlas_foundation_test. psql solicita senhas de forma protegida.
   O script recusa nomes já existentes; não redefine roles/senhas existentes.
2. Injete no processo as variáveis abaixo, sem imprimir seu conteúdo:
   - TEST_DATABASE_OWNER_URL;
   - TEST_DATABASE_RUNTIME_URL;
   - HIATLAS_TEST_DATABASE_RESET=1.
3. As duas URLs devem ser postgresql+psycopg, apontar ao mesmo host/porta/banco
   terminado em _test (identificador simples) e usar usuários diferentes. Host é
   obrigatório e query parameters são recusados. Ambas as conexões verificam
   banco/usuário reais, marcador descartável e mesmo endpoint do servidor.
4. A base deve ter o comentário hiatlas-disposable-test-db definido pelo bootstrap.
   Sem marcador, identidade segura e consentimento de reset, a fixture recusa DDL/cleanup.
5. Rode o gate a partir da raiz:

```powershell
.\scripts\check-platform-foundation.ps1
```

Para uma execução focada em backend:

```powershell
uv run --frozen pytest tests/test_foundation_schema.py -v
uv run --frozen pytest tests/test_audit_integrity.py tests/test_runtime_privileges.py -v
uv run --frozen pytest tests/test_migration_lifecycle.py -v
```

O owner aplica migrações e limpa apenas as tabelas explicitamente listadas no banco
marcado de teste. Requests e asserções de negócio usam runtime. Não executar
pytest paralelo no mesmo banco; cada execução concorrente requer sua própria base.
As fixtures nunca reutilizam DATABASE_URL como URL de teste.

A validação desta fase utilizou PostgreSQL 18.6 portátil, com senha aleatória,
loopback e porta livre; sem instalar serviço ou acessar o banco da aplicação.
Binários Windows podem ser obtidos pela [página oficial do PostgreSQL](https://www.postgresql.org/download/windows/).
As credenciais dessa execução são temporárias e não fazem parte do repositório.

## Auditoria transacional

append_event recebe AuditInput interno e faz flush, **nunca commit**. O chamador
usa uma transação única para negócio e evento. Se a auditoria falhar, a alteração
também é revertida. Timestamp vem do banco; ambiente vem do contrato consultado
no servidor. Não existe endpoint para gravar, editar ou apagar eventos.

Os primeiros eventos tipados são identity.bootstrap e platform.role.changed,
implementados pela Fase 2, junto de platform.operator.status.changed. IdentitySnapshot
aceita apenas user_id, active, blocked e platform_role. Campos extras como senha,
hash, token e secret são recusados sem revelar seus valores no erro.
Novos eventos exigem schemas explícitos do serviço de domínio; não aceitar
payload arbitrário do navegador.

AccessEvent preserva histórico append-only; a Fase 2 registra login, logout,
reautenticação e negações. A aplicação usa hide_parameters para evitar expor
parâmetros em erros SQLAlchemy, mas não deve devolver mensagens de banco ao cliente.

## Contratos das próximas fases

A Fase 3 implementa X-HiAtlas-Context; consulte [operação dos contextos](../docs/operations/hiatlas-contexts.md). Contexto autenticado por aba em
memória/sessionStorage, nunca localStorage compartilhado. Recuperação administrativa
break-glass terá documentação e testes na Fase 11, sem endpoint público ou bypass
de auditoria; não está implementada na Fase 1.

A migração 0003 adiciona tenant_roles, tenant_role_permissions e memberships como
dados de negócio (SELECT/INSERT/UPDATE), e access_contexts como tabela técnica
(SELECT/INSERT/UPDATE/DELETE, sem TRUNCATE). FKs compostas preservam vínculo ao
contrato e à sessão/ator. Permissões de perfil são inativadas, não removidas.

## Gate local oficial no Windows (PostgreSQL portátil descartável)

O fluxo recomendado usa Windows PowerShell 5.1 ou PowerShell 7, sem Docker e sem
instalar/registrar serviço Windows. Não usa a instância da aplicação ou Demo,
não procura clusters existentes e não baixa PostgreSQL automaticamente.

Pré-requisitos: Git, uv/Python conforme o lockfile, Node/npm conforme o projeto
e **distribuição Windows completa do PostgreSQL 18.6** já extraída. Prepare as
dependências na worktree de desenvolvimento antes do gate:

```powershell
Push-Location backend
uv sync --frozen
Pop-Location
Push-Location frontend
npm.cmd ci
Pop-Location
```

Na raiz dessa mesma worktree, informe a raiz da distribuição (que contém `bin`
e `share`). O caminho abaixo é apenas exemplo, não um requisito:

```powershell
.\scripts\check-local.ps1 -PostgresRoot 'D:\Ferramentas\pgsql18'
```

Ou configure **somente o processo atual** e execute:

```powershell
$env:HIATLAS_TEST_POSTGRES_ROOT = 'D:\Ferramentas\pgsql18'
.\scripts\check-local.ps1
```

Sem distribuição válida o comando recusa a execução com instrução explícita.
Exige `bin\postgres.exe`, `initdb.exe`, `pg_ctl.exe`, `pg_isready.exe`, `psql.exe`
e `share\postgres.bki`; confere também a versão 18.6. A presença desses arquivos
não substitui extração completa (DLLs, bibliotecas e demais arquivos); falhas de
executáveis abortam sem fallback, download, SQLite ou acesso a outro servidor.

O agregador:

1. Cria um novo `%TEMP%\hiatlas-testdb-<id aleatório>`, com ACL privada para o
   usuário Windows atual e selo de ownership vinculado ao estado em memória.
2. Inicializa um cluster exclusivo, SCRAM-SHA-256, bind **127.0.0.1** e porta
   disponível escolhida dinamicamente; não instala serviço. Se a porta for
   tomada entre seleção e bind, aborta em vez de usar o servidor dessa porta.
3. Cria somente `hiatlas_foundation_test`, com comentário obrigatório
   `hiatlas-disposable-test-db`, e os logins `hiatlas_test_owner` e
   `hiatlas_test_runtime`: NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOINHERIT,
   NOBYPASSRLS, sem associações a outras roles. Owner possui o banco; runtime
   não possui objetos e recebe os grants mínimos definidos nas migrations.
4. Provisiona também `hiatlas_test_recovery`, igualmente restrita e separada,
   porque a suíte canônica da Fase 11 exige testes de recuperação offline.
   A migration existente 0010 concede somente seus privilégios específicos.
   O login técnico de bootstrap é administrativo apenas dentro desse novo
   cluster; não é owner/runtime/recovery nem credencial de aplicação/testes.
5. Gera senhas criptograficamente aleatórias por execução. Segredos ficam em
   memória/ambiente do processo; o arquivo privado exigido por `initdb` é
   removido imediatamente após sua execução. Não imprime senhas, SQL de
   provisionamento ou URLs completas. O cluster armazena seus hashes SCRAM
   normalmente e é removido no cleanup. Diagnósticos nativos são retidos para
   evitar vazamento; não publique seu conteúdo bruto.
6. Verifica PID, executável, horário de início, diretório, endpoint,
   `pg_isready`, conexões autenticadas reais e marcador/flags de cada role.
   Desconsidera `PG*` herdadas e `.psqlrc` nos subprocessos PostgreSQL para
   impedir redirecionamento por service/options/configuração de outro banco.
7. Define apenas no processo `TEST_DATABASE_OWNER_URL`,
   `TEST_DATABASE_RUNTIME_URL`, `HIATLAS_TEST_DATABASE_RESET=1` e as variáveis
   de teste `HIATLAS_TEST_RECOVERY_DATABASE_URL`/`RECOVERY_DATABASE_ROLE`.
   Os valores anteriores são restaurados ao encerrar. Não grava `.env` e não
   altera `DATABASE_URL`, `MIGRATION_DATABASE_URL` ou configurações da aplicação.
8. Revalida o cluster/ambiente antes de chamar
   `scripts/check-platform-foundation.ps1`, que continua executando
   `uv run --frozen pytest`, Ruff, `npm.cmd test`, lint, build e checks de diff
   tanto da árvore quanto do índice. O mesmo gate executa os testes/lint Windows
   de `scripts/tests`, sem inseri-los na coleta backend multiplataforma. O harness permanece autoridade adicional
   antes de DDL/cleanup dos testes; nenhuma proteção existente foi removida.
9. Em `finally`, revalida ownership, caminhos sem junction/symlink, processo,
   conexões e marcador; para **apenas esse cluster** e remove **apenas seu
   diretório temporário exato**. Falha do gate retorna código não zero mesmo
   com cleanup concluído; falha de cleanup também impede PASS.

Para execução focada, mantenha tudo **na mesma janela/processo PowerShell**:

```powershell
.\scripts\testdb-start.ps1 -PostgresRoot 'D:\Ferramentas\pgsql18'
try {
    .\scripts\check-platform-foundation.ps1
    # Alternativa: Push-Location backend; uv run --frozen pytest <teste>; Pop-Location
} finally {
    .\scripts\testdb-stop.ps1
}
```

Não execute o start em `powershell.exe -File` separado esperando que suas
credenciais/ownership apareçam no shell pai. Não use `Import-Module -Force`
nem descarregue o módulo enquanto o cluster estiver ativo: perderia o estado
privado que autoriza o cleanup. Stop sem estado próprio é no-op; nunca tenta
localizar ou parar clusters de outra execução. Start duplicado é recusado e o
agregador não encerra um workflow manual anterior.

### Recusas, interrupções e verificações

Marcador ausente/adulterado, identidade divergente, processo já parado ou
junction/symlink impedem cleanup de um banco provisionado. O helper preserva
seu estado para investigação e restaura as variáveis anteriores; não tenta
reiniciar, resetar, dropar ou encontrar outro banco para contornar a recusa.
Após tentativa de inicialização/startup, PID ausente não prova que o processo
encerrou: a recusa de cleanup prevalece. Uma falha anterior ao startup pode
limpar somente os artefatos novos
comprovadamente próprios. Se a criação/marcação do banco não puder ser provada,
a recusa prevalece.

Fechar/terminar à força o PowerShell ou desligar o computador pode impedir
`finally`. O diretório exato é informado no início para investigação manual;
não há varredura automática de `%TEMP%`, cleanup por wildcard, serviço ou daemon
persistente de supervisão. Não remova diretórios nem pare processos por nome
para contornar uma recusa. Verifique o cluster específico criado na execução.

Testes de funções/recusas e do agregador usam processos Windows controlados e
não exigem instalação permanente de PostgreSQL:

```powershell
Push-Location backend
uv run --frozen pytest ../scripts/tests/test_local_testdb_scripts.py tests/test_quality_gate.py -q
Pop-Location
```

O gate completo exige PostgreSQL real descartável, sem skips novos. O fluxo
manual anterior com `database/test-bootstrap.sql` permanece disponível apenas
para instância de teste autorizada; suas proteções e o harness não foram
relaxados. Nunca execute aquele bootstrap contra a aplicação, Demo ou banco real.

Teste adicional opcional do ciclo **real**, com outra base nova descartável:

```powershell
.\scripts\tests\testdb-lifecycle.ps1 -PostgresRoot 'D:\Ferramentas\pgsql18'
```

Ele prova start/stop, ausência do arquivo temporário de senha após `initdb`,
recusa de variáveis adulteradas/start duplicado, recusa de testes e cleanup
sem marcador, restauração controlada do marcador do próprio banco e remoção
final com restauração do ambiente. Não usa nem altera banco existente.
