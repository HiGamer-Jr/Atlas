# HiAtlas — Identidade e operadores internos (Fase 2)

## Escopo entregue

A API autentica usuários reais no PostgreSQL. PLATFORM_ADMIN e PLATFORM_SUPPORT
são atribuições em platform_role_assignments; nunca são TenantRole. O papel é
lido do banco em cada request e não pode ser escolhido no login nem por header.

Não há RBAC completo, seleção de tenant/contrato, convites, redefinição de senha,
MFA ou portal administrativo nesta fase. /auth/me retorna capabilities vazio
até o catálogo contextual da Fase 3. O frontend antigo continua uma **demonstração**:
seu seletor de perfil não autentica e não concede acesso às APIs reais.

## Configuração e migrações

Pré-requisito: banco exclusivo, owner e runtime separados, conforme
[database/README.md](../../database/README.md). Faça backup e use o processo
de migração autorizado; testes nunca apontam para esse banco.

1. No processo de migração, configure MIGRATION_DATABASE_URL e DATABASE_RUNTIME_ROLE.
2. Em backend execute `uv sync --frozen` e `uv run --frozen alembic upgrade head`.
3. No processo da API configure somente DATABASE_URL do runtime, ENVIRONMENT e
   PUBLIC_ORIGIN (origem HTTPS exata, sem caminho ou barra final).
4. Produção recusa credenciais de banco vazias/padrão. Todos os cookies são Secure,
   HttpOnly, SameSite=Strict, prefixo __Host-, Path=/ e sem Domain.
5. Sirva frontend e /api na mesma origem HTTPS. Não há CORS permissivo.
   HTTP local não serve para o fluxo autenticado.

Exemplo de inicialização atrás de terminador HTTPS local, sem confiar
automaticamente em headers de proxy:

```powershell
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

TRUSTED_PROXY_IPS é uma lista JSON explícita de endereços dos proxies diretamente
conectados. Por padrão está vazia; X-Forwarded-For é ignorado. Se habilitado, o proxy
deve **sobrescrever** esse header com um único IP validado. Cadeias, valores inválidos
ou peers não autorizados usam o IP da conexão. Não habilite reescrita adicional
de request.client no servidor ASGI: ela apagaria a identidade do peer necessária
a esta verificação. A exposição/terminação HTTPS deve ser configurada na implantação;
nenhum deploy foi realizado nesta fase.

## Sessão e CSRF

| Rota | Comportamento |
|---|---|
| GET /api/auth/csrf | Emite CSRF pré-login com validade de 10 minutos; autenticado, entrega CSRF da própria sessão |
| POST /api/auth/login | email/password; rotaciona sessão e CSRF e invalida a sessão anterior |
| GET /api/auth/me | user_id, display_name, platform_role opcional, capabilities |
| POST /api/auth/logout | Revoga a sessão persistida e limpa cookies |
| POST /api/auth/reauthenticate | Confirma password sem emitir novo privilégio; validade de 5 minutos para ações sensíveis |

Todas as mutações exigem Origin exatamente igual a PUBLIC_ORIGIN e X-CSRF-Token.
O cliente obtém token CSRF em /auth/csrf; esse token antifalsificação é a única
exceção intencional à proibição de retornar tokens em JSON. Credencial de sessão,
hashes e senhas nunca são retornados no corpo. Sessão e CSRF persistem apenas
como hashes SHA-256 de valores aleatórios de 256 bits. Senhas usam Argon2id pelo
[argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/howto.html), inclusive
verificação fictícia para usuário inexistente.

A sessão expira após 30 minutos sem atividade ou 8 horas absolutas. Bloqueio,
inativação e revogação são observados na requisição seguinte. Reiniciar a API
não remove sessões, revogações ou contadores. Não há sessão autenticada em
localStorage. A integração por aba e AccessContext continuam nas Fases 3/4.

Limites iniciais: 10 falhas por identificador e 100 por origem de rede em 15 minutos.
Configuração: AUTH_IDENTIFIER_LIMIT, AUTH_SOURCE_LIMIT, AUTH_WINDOW_SECONDS.
Login, reautenticação e confirmação de senha de operador compartilham contadores
transacionais com lock no PostgreSQL. Identificador e origem são hasheados; senha
e body não são persistidos. O bloqueio é temporário e retorna 429/Retry-After;
não altera o status da conta. Sucessos/falhas/negações geram AccessEvent sanitizado.

As tabelas auth_sessions, auth_preauth e auth_rate_limits são técnicas e recebem
SELECT/INSERT/UPDATE/DELETE, sem TRUNCATE. Expirados de preauth são removidos ao
emitir CSRF. Retenção/limpeza periódica de sessões e contadores deve ser operada
com filtros explícitos de expiração pela infraestrutura; não há worker genérico
nem remoção de auditoria. O owner continua fora do processo da aplicação.

## Primeiro administrador

Com migrações aplicadas e DATABASE_URL do **runtime**, em um terminal interativo:

```powershell
uv run --frozen python -m app.identity.bootstrap --email operador@empresa.example
```

A senha é solicitada duas vezes por getpass; entre 12 e 1024 caracteres.
Não há senha padrão, argumento --password, leitura de senha por pipe nem
endpoint HTTP de bootstrap. O e-mail é normalizado; identidades existentes não
podem ser convertidas por esse comando.

O bootstrap cria usuário, atribuição PLATFORM_ADMIN e AuditEvent na mesma
transação. Um advisory lock serializa bootstraps e alterações de operadores.
A existência de administrador ou evento histórico de bootstrap impede execução
posterior, inclusive se o administrador tiver sido desativado. Falha ao auditar
reverte tudo. Operadores posteriores usam identidade existente; convites serão
entregues na Fase 5. Nenhuma conta demonstrativa é promovida automaticamente.

Este comando **não é recuperação de acesso**. O procedimento break-glass permanece
na Fase 11, sem reabertura de bootstrap ou bypass de auditoria nesta fase.

## Gestão dos operadores

Somente PLATFORM_ADMIN pode usar:

- POST /api/platform/operators/{user_id}/role com role (PLATFORM_ADMIN ou
  PLATFORM_SUPPORT), password e confirmation {target_user_id, target_role}.
  A confirmação deve coincidir com URL e papel. A senha verificada nessa request
  é a reautenticação explícita da operação; uma confirmação incorreta não aplica
  a mudança. Autopromoção é proibida.
- POST /api/platform/operators/{user_id}/status com active e/ou blocked, booleanos
  explícitos. Exige autenticação confirmada há menos de cinco minutos; se
  necessário, usar /auth/reauthenticate antes. Afeta apenas operador interno
  existente, não usuários de tenant sem atribuição interna.

Não existe endpoint de criação de identidades ou edição de TenantRole nesta fase.
Alterações de papel/status revogam todas as sessões do alvo e registram snapshots
permitidos de antes/depois com ator e request_id, sem senha/hash. A transação
revalida ator/alvo e protege o último administrador ativo e desbloqueado,
inclusive em concorrência. Não há “modo Deus” nem concessão Financeira/Fiscal.

Erros públicos usam code/message/request_id; validação não devolve o input,
e erros internos não expõem SQL, credenciais ou traceback. Em falha, correlacione
o request_id com a auditoria/observabilidade privada da infraestrutura; não
habilite captura de cookies, bodies ou parâmetros sensíveis no proxy/APM.

## Testes e limites operacionais

O quality gate exige PostgreSQL descartável e as variáveis documentadas para
testes. Clientes pytest obtêm CSRF e fazem login HTTP com hash real, sem bypass
de dependência ou rota secreta. Concorrência usa conexões independentes.

HTTPS real, proxy e recursos de produção (incluindo dimensionamento do Argon2 e
retenção técnica) ainda exigem configuração de implantação. TestClient verifica
a política HTTP/cookies; não substitui validação do terminador TLS real.
