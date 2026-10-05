# Atlas

Atlas é uma plataforma corporativa de Supply Chain, Compras, Estoque, Comércio Exterior e Financeiro, evoluída a partir do protótipo Cargo.Ops.

## Status

Fundação técnica consolidada:

- Frontend: React + TypeScript + Vite.
- Backend: FastAPI.
- Banco alvo: PostgreSQL.
- Arquitetura: Monólito Modular.
- Protótipo Cargo.Ops preservado em `legacy/cargo-ops-prototype/`.

## Fundação da plataforma HiAtlas

HiAtlas Platform Foundation v1: STATUS VALIDATED. A Fase 11 está concluída tecnicamente e parada para revisão. O estado funcional e as limitações da fundação estão no [documento de release](docs/releases/hiatlas-platform-foundation-v1.md); catálogo de módulos não significa módulos operacionais entregues.

- [Operação segura, implantação, backup/restore e recuperação administrativa](docs/operations/hiatlas-platform-foundation.md).
- [Sanity pós-deploy](docs/operations/hiatlas-post-deploy-sanity.md).
- [Pré-requisitos de demo isolado](docs/operations/hiatlas-demo-readiness.md).
- [Evidências da Fase 11](docs/superpowers/validation/hiatlas-platform/phase-11.md).

Os comandos locais abaixo são exemplos de desenvolvimento. O login autenticado exige HTTPS e configuração própria conforme o runbook; o preview estático não substitui o frontend autenticado e seu backend. Nenhum deploy ou ambiente demo é iniciado por estes documentos.

## Documentos principais

- Requisitos v1.0: `docs/requirements/atlas-requisitos-v1.md`.
- Arquitetura da fundação: `docs/superpowers/specs/2026-08-26-atlas-foundation-design.md`.
- Plano de fundação: `docs/superpowers/plans/2026-08-26-atlas-foundation-implementation.md`.
- Blueprint de produto: `docs/product-blueprint.md`.

## Portas locais

| Serviço | Porta |
|---|---:|
| Frontend | 5174 |
| Backend | 8001 |
| PostgreSQL | 5433 |

## Frontend

```powershell
Set-Location .\frontend
npm install
npm run dev -- --port 5174
```

Aplicação:

`http://localhost:5174`

## Preview estático em web/

Para gerar uma versão visualizável em `web/`:

```powershell
.\scripts\publish-web-preview.ps1
```

Depois abra:

`web/index.html`

## PostgreSQL

```powershell
Copy-Item .\.env.example .\.env
docker compose up -d postgres
```

O `.env` local deve receber uma senha real de desenvolvimento e não deve ser versionado.

## Backend

```powershell
Set-Location .\backend
Copy-Item .\.env.example .\.env
uv run fastapi dev app/main.py --port 8001
```

API:

`http://localhost:8001/api/health`

OpenAPI:

`http://localhost:8001/docs`

## Verificações

```powershell
.\scripts\check.ps1
```

Também é possível executar separadamente:

```powershell
Set-Location .\frontend
npm test
npm run lint
npm run build
```

```powershell
Set-Location .\backend
uv run pytest
uv run ruff check app tests
```

## Segurança

Nunca versionar:

- `.env`;
- credenciais;
- tokens;
- senhas;
- chaves JWT;
- certificados digitais.

Use arquivos `.env.example` apenas como modelo.
