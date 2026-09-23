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
