# Fase 1 — Banco e Auditoria

Data: 22/09/2026. Status: implementada e validada; parada para revisão antes da Fase 2.
Branch: `feat/hiatlas-platform-phase-1`. Base: `621668d`.
Worktree: `D:\Atlas\.worktrees\hiatlas-platform-phase-1`.

## Entrega

- Migração Alembic 0001 e modelos de usuários, papéis internos, tenants, contratos,
  eventos de auditoria e acesso. UUID, timestamps com timezone, unicidade e FKs.
- Owner de migração separado do runtime; grants por categoria.
  Negócio sem DELETE/TRUNCATE; eventos sem UPDATE/DELETE/TRUNCATE.
  Controle Alembic exclusivo do owner; tabelas técnicas futuras sem grants automáticos.
- Auditoria interna tipada, snapshots restritos, ambiente derivado do contrato,
  flush sem commit e rollback conjunto com a mutação de negócio.
- Fixtures de PostgreSQL real e gate fail-fast, documentação de provisionamento.
- Cinco ajustes finais incorporados aos planos. Header, armazenamento por aba e
  break-glass são compromissos das respectivas fases, não funcionalidades entregues aqui.

Não há login, bootstrap de operador, API administrativa, UI autenticada ou
autorização entre tenants nesta fase. As FKs não substituem o RBAC futuro.
Imutabilidade é garantida contra a identidade runtime; o owner é credencial
privilegiada de infraestrutura e deve permanecer fora do processo da aplicação.

## Ambiente e reprodução

Windows, Python 3.13.15, PostgreSQL 18.6 portátil em loopback com porta temporária,
banco descartável marcado e identidades owner/runtime sem superusuário.
Nenhum serviço instalado, banco real alterado ou destinatário externo acionado.
uv já era canônico; dependências instaladas com lock congelado. Lockfiles intactos.

Siga [database/README.md](../../../../database/README.md) para provisionar um
banco descartável, injetar TEST_DATABASE_OWNER_URL, TEST_DATABASE_RUNTIME_URL e
HIATLAS_TEST_DATABASE_RESET=1. Execute da raiz:

```powershell
.\scripts\check-platform-foundation.ps1
```

As URLs de teste exigem host explícito, nome simples terminado em _test e nenhuma
query string. Ambas as conexões atestam banco, usuário, marcador descartável e
mesmo endpoint real antes de qualquer migração ou cleanup. Sem banco configurado,
a execução falha; não pula testes nem reutiliza DATABASE_URL.

## Evidências

[Log completo do gate final](phase-01-quality-gate.log), exit code 0:

| Verificação | Resultado |
|---|---|
| pytest, PostgreSQL real | 76 passed; zero skips |
| Ruff (app, tests, alembic) | passou |
| Frontend Vitest | 68 passed |
| Frontend ESLint | passou |
| TypeScript + Vite build | passou |
| git diff --check / --cached | passou |

Um aviso preexistente de depreciação Starlette/httpx permanece; sem alteração de
dependências nesta fase. Avisos Git de conversão LF/CRLF não representam falhas.

Cobertura: FK de tenant, par tenant/contrato, e-mail normalizado único,
enum fechado de papéis internos, grants reais via SQL e SQLSTATE 42501,
negação de ownership/DDL/SET ROLE, tabela técnica com DELETE explicitamente
concedido sem TRUNCATE, upgrade/downgrade/upgrade, rollback de request e auditoria,
snapshots sem credenciais, ambiente derivado e fail-fast do gate.

Execução negativa sem variáveis de teste: exit code 1 no setup, mensagem
redigida de configuração ausente/insegura, sem fallback e sem skip.

## TDD e revisão

Baseline: 6 testes backend e 68 frontend passaram.
RED inicial de schema: as seis tabelas esperadas estavam ausentes.
RED de serviço: append_event ainda não existia. Implementação seguida pelos testes
de integridade, grants e atomicidade.

Desvio registrado: o primeiro RED de schema detectou ausência das tabelas, em vez
da ausência isolada da FK sugerida pelo plano. Para validar a sensibilidade do
teste de comportamento, executou-se em banco descartável a remoção transacional
da FK de contracts para tenants: o teste falhou por ausência da IntegrityError
esperada. Rollback restaurou a constraint. Também se concedeu UPDATE temporário
na auditoria: o teste de negação falhou. O grant foi revogado em finally.
Ambos os testes voltaram a GREEN após restauração.

Revisão independente somente leitura encontrou dois problemas:
1. Query parameters de conexão podiam sobrescrever o destino declarado dos testes.
2. Processo novo da aplicação não registrava os modelos de identidade necessários
   para resolver as FKs da auditoria.

Sete regressões falharam antes da correção e passaram depois. Corrigidos:
URLs de teste sem parâmetros/conninfo/host implícito, atestação das duas conexões,
e registro completo dos modelos na inicialização. Acrescentados três testes reais
de identidade/marcador. O gate completo acima foi executado após essas correções.
Nenhum outro achado foi reportado; as correções foram verificadas pelo executor,
sem alegar uma segunda revisão independente.

## Decisões e parada

- Um único commit de entrega da fase reúne schema, auditoria e evidências,
  preservando a migração inicial coesa; o plano sugeria dois commits por tarefa.
- Nenhuma dependência adicionada, gerenciador migrado ou arquivo de frontend alterado.
- Sessões/tokens técnicos não foram antecipados; seus grants serão definidos na fase correspondente.
- A instância temporária de PostgreSQL é encerrada após a validação.
- Branch e worktree preservados para revisão; sem merge, push ou deploy.
- Fase 2 não iniciada. Break-glass continua reservado à Fase 11.
