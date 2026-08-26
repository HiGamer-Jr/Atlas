# Atlas Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o repositório atual do Cargo.Ops em uma fundação executável, isolada e testável para o Atlas, preservando o protótipo legado e inicializando frontend React/TypeScript, backend FastAPI e PostgreSQL sem implementar ainda os módulos de negócio.

**Architecture:** O Cargo.Ops atual será preservado em `legacy/cargo-ops-prototype/`. A nova aplicação utilizará monólito modular, com frontend e backend independentes e PostgreSQL isolado para desenvolvimento. Esta fase entrega apenas a fundação técnica e um fluxo mínimo de saúde (`frontend -> API -> health`) para provar que os componentes conseguem executar sem acoplamento com o Site HiGamer.

**Tech Stack:** Node.js 24 LTS, React + TypeScript + Vite, Python 3.13 via `uv`, FastAPI, Pydantic Settings, SQLAlchemy 2, Psycopg 3, Alembic, PostgreSQL 18, Pytest, Ruff, Vitest e Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-26-atlas-foundation-design.md`

## Global Constraints

- O Atlas utilizará inicialmente um **Monólito Modular**.
- Não serão utilizados microserviços na primeira fase.
- Frontend e backend serão independentes.
- O banco transacional principal será PostgreSQL.
- O protótipo Cargo.Ops será preservado como referência funcional e visual.
- Usuários, perfis e unidades serão conceitos separados.
- Compras Nacional e Internacional serão diferenciadas em fases posteriores.
- O estoque será corporativo e organizado por unidade em fases posteriores.
- Integrações serão isoladas das regras de negócio.
- Operações críticas serão auditáveis em fases posteriores.
- Atlas e Site HiGamer permanecerão tecnicamente isolados.
- Nenhum arquivo contendo segredo poderá ser versionado.
- Portas locais reservadas para o Atlas nesta fundação:
  - Frontend: `5174`
  - Backend: `8001`
  - PostgreSQL: `5433`
- Ambiente de desenvolvimento:
  - Node.js `24.19.0` LTS
  - Python `3.13.15`
  - PostgreSQL `18.6`
- Gerenciamento Python: `uv`; não utilizar o Python global quebrado do Windows para instalar dependências do Atlas.
- Gerenciamento JavaScript: `npm` local ao projeto; evitar dependências globais desnecessárias.
- Cada tarefa deve terminar com validação e commit próprio.
- Não implementar nesta fase autenticação, RBAC, estoque, compras, COMEX, financeiro, Data Hub ou dashboards funcionais.

---

## File Structure Locked by This Plan

```text
Atlas---Cargo.Ops/
├── .gitignore
├── .nvmrc
├── .python-version
├── README.md
├── compose.yaml
├── .env.example
│
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── .env.example
│   └── src/
│       ├── app/
│       │   ├── App.tsx
│       │   └── App.test.tsx
│       ├── modules/
│       │   └── dashboard/
│       │       └── DashboardPage.tsx
│       ├── services/
│       │   └── api.ts
│       ├── test/
│       │   └── setup.ts
│       └── main.tsx
│
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .env.example
│   ├── alembic.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       └── health.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       └── session.py
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   └── tests/
│       ├── __init__.py
│       ├── test_health.py
│       └── test_settings.py
│
├── database/
│   └── README.md
│
├── docs/
│   ├── requirements/
│   ├── architecture/
│   ├── adr/
│   └── superpowers/
│       ├── specs/
│       └── plans/
│
├── legacy/
│   └── cargo-ops-prototype/
│       ├── README.md
│       ├── index.html
│       ├── app.js
│       └── styles.css
│
└── scripts/
    └── check.ps1
```

---

### Task 1: Preserve Cargo.Ops Legacy and Establish Repository Boundaries

**Files:**
- Move: `web/index.html` -> `legacy/cargo-ops-prototype/index.html`
- Move: `web/app.js` -> `legacy/cargo-ops-prototype/app.js`
- Move: `web/styles.css` -> `legacy/cargo-ops-prototype/styles.css`
- Create: `legacy/cargo-ops-prototype/README.md`
- Create: `.nvmrc`
- Create: `.python-version`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: existing static Cargo.Ops prototype under `web/`.
- Produces: immutable reference location `legacy/cargo-ops-prototype/` used by later UI work as visual/functional reference.

- [ ] **Step 1: Verify the legacy JavaScript is valid before moving it**

Run:

```powershell
node --check .\web\app.js
```

Expected: exit code `0` and no syntax error.

- [ ] **Step 2: Create the target legacy directory**

Run:

```powershell
New-Item -ItemType Directory -Force .\legacy\cargo-ops-prototype | Out-Null
```

- [ ] **Step 3: Move tracked prototype files with Git**

Run:

```powershell
git mv .\web\index.html .\legacy\cargo-ops-prototype\index.html
git mv .\web\app.js .\legacy\cargo-ops-prototype\app.js
git mv .\web\styles.css .\legacy\cargo-ops-prototype\styles.css
```

If `web/` becomes empty, remove the directory:

```powershell
Remove-Item .\web -Force -ErrorAction SilentlyContinue
```

- [ ] **Step 4: Create the legacy README**

Create `legacy/cargo-ops-prototype/README.md` with exactly:

```markdown
# Cargo.Ops Legacy Prototype

Este diretório preserva o protótipo funcional que originou o Projeto Atlas.

## Regras

- Não utilizar este código como fundação técnica da aplicação de produção.
- Não adicionar novas funcionalidades de negócio neste diretório.
- Utilizar o protótipo apenas como referência funcional, visual e histórica.
- Toda nova implementação deve ocorrer em `frontend/` e `backend/`.

## Conteúdo

- `index.html`: entrada do protótipo.
- `app.js`: regras e interações do protótipo baseado em JavaScript/localStorage.
- `styles.css`: identidade visual e estilos originais.
```

- [ ] **Step 5: Pin the development runtime files**

Create `.nvmrc`:

```text
24.19.0
```

Create `.python-version`:

```text
3.13.15
```

- [ ] **Step 6: Extend `.gitignore` for the new architecture**

Ensure `.gitignore` contains these entries in addition to the existing security rules:

```gitignore
# Atlas frontend
frontend/node_modules/
frontend/dist/
frontend/.env
frontend/.env.*

# Atlas backend
backend/.venv/
backend/.env
backend/.env.*
backend/.pytest_cache/
backend/.ruff_cache/
backend/__pycache__/
backend/**/*.pyc

# Root environment / Docker
.env
.env.*

# IDE / temporary
.vscode/
.idea/
*.log
```

Do not remove the existing rules that protect `backend/.env`.

- [ ] **Step 7: Verify the prototype still parses at the new location**

Run:

```powershell
node --check .\legacy\cargo-ops-prototype\app.js
```

Expected: exit code `0`.

- [ ] **Step 8: Verify Git recognized moves instead of delete/add noise**

Run:

```powershell
git status
git diff --summary
```

Expected: the three prototype files are shown as renamed/moved, plus the new README/runtime files and `.gitignore` modification.

- [ ] **Step 9: Commit**

Run:

```powershell
git add .gitignore .nvmrc .python-version .\legacy
git commit -m "chore: preserve Cargo.Ops prototype as legacy"
```

---

### Task 2: Create a Testable FastAPI Backend Foundation

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/uv.lock`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/router.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`
- Create: `backend/tests/test_settings.py`

**Interfaces:**
- Consumes: Python `3.13.15` managed by `uv`.
- Produces:
  - `app.main:app` FastAPI application.
  - `GET /api/health` -> `{"status": "ok", "service": "atlas-api"}`.
  - `get_settings() -> Settings`.
  - API local port `8001`.

- [ ] **Step 1: Verify/install `uv` without using the broken Python installation**

Run:

```powershell
uv --version
```

If PowerShell reports that `uv` is not recognized, install with the official standalone installer:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen the terminal, then run:

```powershell
uv --version
```

Expected: a version string and exit code `0`.

- [ ] **Step 2: Install the isolated Python version**

Run:

```powershell
uv python install 3.13.15
uv python list | Select-String "3.13"
```

Expected: Python `3.13.15` appears in the `uv` managed list.

- [ ] **Step 3: Initialize the backend project**

Run:

```powershell
Set-Location .\backend
uv init --bare --python 3.13.15
uv add "fastapi[standard]" pydantic-settings sqlalchemy "psycopg[binary]" alembic
uv add --dev pytest ruff
```

Expected: `pyproject.toml` and `uv.lock` are created.

- [ ] **Step 4: Create package directories**

Run from `backend/`:

```powershell
New-Item -ItemType Directory -Force .\app\api\routes | Out-Null
New-Item -ItemType Directory -Force .\app\core | Out-Null
New-Item -ItemType Directory -Force .\tests | Out-Null

New-Item -ItemType File -Force .\app\__init__.py | Out-Null
New-Item -ItemType File -Force .\app\api\__init__.py | Out-Null
New-Item -ItemType File -Force .\app\api\routes\__init__.py | Out-Null
New-Item -ItemType File -Force .\app\core\__init__.py | Out-Null
New-Item -ItemType File -Force .\tests\__init__.py | Out-Null
```

- [ ] **Step 5: Write the failing health endpoint test**

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_service_status() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "atlas-api",
    }
```

- [ ] **Step 6: Run the test and verify it fails**

Run from `backend/`:

```powershell
uv run pytest .\tests\test_health.py -v
```

Expected: FAIL because `app.main` does not exist yet.

- [ ] **Step 7: Implement the health route**

Create `backend/app/api/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "atlas-api",
    }
```

Create `backend/app/api/router.py`:

```python
from fastapi import APIRouter

from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
```

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="Atlas API",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api")
```

- [ ] **Step 8: Run the health test and verify it passes**

Run:

```powershell
uv run pytest .\tests\test_health.py -v
```

Expected: `1 passed`.

- [ ] **Step 9: Write the failing settings test**

Create `backend/tests/test_settings.py`:

```python
from app.core.config import Settings


def test_settings_default_local_ports() -> None:
    settings = Settings()

    assert settings.app_name == "Atlas API"
    assert settings.api_port == 8001
    assert settings.frontend_origin == "http://localhost:5174"
```

- [ ] **Step 10: Run the settings test and verify it fails**

Run:

```powershell
uv run pytest .\tests\test_settings.py -v
```

Expected: FAIL because `app.core.config.Settings` does not exist yet.

- [ ] **Step 11: Implement backend settings**

Create `backend/app/core/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Atlas API"
    api_port: int = 8001
    frontend_origin: str = "http://localhost:5174"
    database_url: str = (
        "postgresql+psycopg://atlas:atlas@localhost:5433/atlas"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create `backend/.env.example`:

```dotenv
APP_NAME=Atlas API
API_PORT=8001
FRONTEND_ORIGIN=http://localhost:5174
DATABASE_URL=postgresql+psycopg://atlas:CHANGE_ME@localhost:5433/atlas
```

- [ ] **Step 12: Run all backend tests and lint**

Run:

```powershell
uv run pytest -v
uv run ruff check .
```

Expected:
- all tests pass;
- Ruff exits with code `0`.

- [ ] **Step 13: Run the backend manually**

Run:

```powershell
uv run fastapi dev app/main.py --port 8001
```

In another PowerShell:

```powershell
Invoke-RestMethod http://localhost:8001/api/health
```

Expected:

```text
status service
------ -------
ok     atlas-api
```

Stop the server with `Ctrl+C`.

- [ ] **Step 14: Commit**

From repository root:

```powershell
git add .\backend
git commit -m "feat: establish FastAPI backend foundation"
```

---

### Task 3: Create a Tested React/TypeScript Frontend Foundation

**Files:**
- Create: `frontend/` through Vite React TypeScript scaffold
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/.env.example`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/App.test.tsx`
- Create: `frontend/src/modules/dashboard/DashboardPage.tsx`
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/test/setup.ts`
- Modify: `frontend/src/main.tsx`

**Interfaces:**
- Consumes:
  - Backend health endpoint `GET http://localhost:8001/api/health`.
  - `VITE_API_URL`.
- Produces:
  - React application on `http://localhost:5174`.
  - `apiUrl: string` exported by `src/services/api.ts`.
  - Basic Atlas shell for subsequent modules.

- [ ] **Step 1: Verify Node runtime before scaffolding**

From repository root:

```powershell
node --version
npm --version
```

Expected Node: `v24.19.0`.

If Node is not `24.19.0`, do not replace another project's Node installation blindly. Use NVM for Windows to install/use the pinned version before continuing:

```powershell
nvm install 24.19.0
nvm use 24.19.0
node --version
```

- [ ] **Step 2: Scaffold Vite React TypeScript**

Run from repository root:

```powershell
npm create vite@latest frontend -- --template react-ts
Set-Location .\frontend
npm install
```

- [ ] **Step 3: Add frontend test dependencies**

Run:

```powershell
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom
```

- [ ] **Step 4: Configure Vitest and Atlas port**

Replace `frontend/vite.config.ts` with:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
```

Update `frontend/tsconfig.app.json` compiler options to include:

```json
"types": ["vitest/globals", "@testing-library/jest-dom"]
```

Do not remove the existing Vite TypeScript compiler options.

Add these scripts to `frontend/package.json`:

```json
"test": "vitest run",
"test:watch": "vitest",
"check": "npm run test && npm run build"
```

Keep the existing `dev`, `build`, `lint`, and `preview` scripts.

- [ ] **Step 5: Create the test setup**

Create `frontend/src/test/setup.ts`:

```typescript
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 6: Write the failing application shell test**

Create `frontend/src/app/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'

import { App } from './App'

describe('Atlas application shell', () => {
  it('identifies the Atlas product and dashboard', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: /atlas/i }),
    ).toBeInTheDocument()

    expect(
      screen.getByText(/supply chain operating system/i),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('heading', { name: /dashboard/i }),
    ).toBeInTheDocument()
  })
})
```

- [ ] **Step 7: Run the frontend test and verify it fails**

Run from `frontend/`:

```powershell
npm test
```

Expected: FAIL because `src/app/App.tsx` does not exist yet.

- [ ] **Step 8: Implement the minimal Atlas shell**

Create `frontend/src/modules/dashboard/DashboardPage.tsx`:

```tsx
export function DashboardPage() {
  return (
    <section>
      <h2>Dashboard</h2>
      <p>Fundação operacional do Atlas.</p>
    </section>
  )
}
```

Create `frontend/src/app/App.tsx`:

```tsx
import { DashboardPage } from '../modules/dashboard/DashboardPage'

export function App() {
  return (
    <main>
      <header>
        <h1>Atlas</h1>
        <p>Supply Chain Operating System</p>
      </header>

      <DashboardPage />
    </main>
  )
}
```

Replace `frontend/src/main.tsx` with:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

Create `frontend/src/services/api.ts`:

```typescript
export const apiUrl =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8001'
```

Create `frontend/.env.example`:

```dotenv
VITE_API_URL=http://localhost:8001
```

- [ ] **Step 9: Run frontend tests**

Run:

```powershell
npm test
```

Expected: all tests pass.

- [ ] **Step 10: Run frontend build and lint**

Run:

```powershell
npm run build
npm run lint
```

Expected: both commands exit with code `0`.

- [ ] **Step 11: Run the frontend manually**

Run:

```powershell
npm run dev -- --port 5174
```

Open:

```text
http://localhost:5174
```

Expected:
- heading `Atlas`;
- text `Supply Chain Operating System`;
- heading `Dashboard`.

Stop with `Ctrl+C`.

- [ ] **Step 12: Commit**

From repository root:

```powershell
git add .\frontend
git commit -m "feat: establish React frontend foundation"
```

---

### Task 4: Establish Isolated PostgreSQL and SQLAlchemy Foundation

**Files:**
- Create: `compose.yaml`
- Create: `.env.example`
- Create: `database/README.md`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create/modify: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/versions/.gitkeep`
- Create: `backend/tests/test_database_connection.py`

**Interfaces:**
- Consumes:
  - PostgreSQL local container exposed on `localhost:5433`.
  - `Settings.database_url`.
- Produces:
  - `Base` SQLAlchemy declarative base.
  - `engine` SQLAlchemy engine.
  - `SessionLocal` session factory.
  - Alembic migration environment.
  - Verified database connectivity.

- [ ] **Step 1: Verify Docker availability**

Run:

```powershell
docker --version
docker compose version
```

Expected: both commands return versions and exit with code `0`.

If Docker is not installed, pause this task and install Docker Desktop for Windows before proceeding. Do not replace or reconfigure databases used by the Site HiGamer.

- [ ] **Step 2: Create root environment template**

Create `.env.example`:

```dotenv
POSTGRES_DB=atlas
POSTGRES_USER=atlas
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_PORT=5433
```

Create a local `.env` from it:

```powershell
Copy-Item .\.env.example .\.env
```

Edit only the local `.env` and replace `CHANGE_ME` with a development password. The root `.env` must remain ignored by Git.

- [ ] **Step 3: Create isolated PostgreSQL Compose configuration**

Create `compose.yaml`:

```yaml
services:
  postgres:
    image: postgres:18.6
    container_name: atlas-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "${POSTGRES_PORT}:5432"
    volumes:
      - atlas_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  atlas_pgdata:
```

- [ ] **Step 4: Start PostgreSQL**

Run:

```powershell
docker compose up -d postgres
docker compose ps
```

Expected: `atlas-postgres` becomes `healthy`.

- [ ] **Step 5: Configure the local backend database URL**

From `backend/`:

```powershell
Copy-Item .\.env.example .\.env -Force
```

Edit local `backend/.env` so `DATABASE_URL` matches the root `.env` credentials and port `5433`.

Do not commit either `.env`.

- [ ] **Step 6: Write the failing database connectivity test**

Create `backend/tests/test_database_connection.py`:

```python
from sqlalchemy import text

from app.db.session import engine


def test_database_accepts_connection() -> None:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()

    assert result == 1
```

- [ ] **Step 7: Run the database test and verify it fails**

From `backend/`:

```powershell
uv run pytest .\tests\test_database_connection.py -v
```

Expected: FAIL because `app.db.session` does not exist yet.

- [ ] **Step 8: Implement SQLAlchemy base and session**

Create `backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `backend/app/db/session.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
```

Create `backend/app/db/__init__.py`:

```python
from app.db.base import Base
from app.db.session import SessionLocal, engine

__all__ = ["Base", "SessionLocal", "engine"]
```

- [ ] **Step 9: Run the database test**

Run:

```powershell
uv run pytest .\tests\test_database_connection.py -v
```

Expected: `1 passed`.

- [ ] **Step 10: Initialize Alembic**

Run from `backend/`:

```powershell
uv run alembic init migrations
```

Replace the generated `backend/migrations/env.py` with:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base

config = context.config
settings = get_settings()

config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

No business tables are created in this foundation task.

- [ ] **Step 11: Document database isolation**

Create `database/README.md`:

```markdown
# Atlas Database

O banco transacional principal do Atlas é PostgreSQL.

## Desenvolvimento local

- Container: `atlas-postgres`
- Porta do host: `5433`
- Porta interna: `5432`
- Banco padrão: `atlas`

Credenciais locais ficam em `.env` e nunca devem ser versionadas.

O Atlas não compartilha banco, schema, volume ou porta de aplicação com o Site HiGamer.
```

- [ ] **Step 12: Run all backend checks with PostgreSQL active**

Run from `backend/`:

```powershell
uv run pytest -v
uv run ruff check .
```

Expected: all tests pass and Ruff exits with code `0`.

- [ ] **Step 13: Commit**

From repository root:

```powershell
git add .\compose.yaml .\.env.example .\database .\backend\app\db .\backend\migrations .\backend\alembic.ini .\backend\tests\test_database_connection.py
git commit -m "feat: establish PostgreSQL persistence foundation"
```

---

### Task 5: Add a Single Foundation Verification Command and Developer Documentation

**Files:**
- Create: `scripts/check.ps1`
- Modify: `README.md`

**Interfaces:**
- Consumes:
  - Legacy JS file.
  - Backend test/lint commands.
  - Frontend test/build/lint commands.
- Produces:
  - `scripts/check.ps1` as the canonical local verification gate.
  - Root README describing isolated startup.

- [ ] **Step 1: Create the verification script**

Create `scripts/check.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

Write-Host "== Legacy Cargo.Ops syntax =="
Push-Location $root
node --check .\legacy\cargo-ops-prototype\app.js
Pop-Location

Write-Host "== Atlas Backend =="
Push-Location "$root\backend"
uv run pytest -v
uv run ruff check .
Pop-Location

Write-Host "== Atlas Frontend =="
Push-Location "$root\frontend"
npm test
npm run lint
npm run build
Pop-Location

Write-Host "== Atlas foundation checks passed =="
```

- [ ] **Step 2: Run the verification script**

Run from repository root:

```powershell
.\scripts\check.ps1
```

Expected:
- legacy JavaScript syntax check exits `0`;
- all backend tests pass;
- backend Ruff check exits `0`;
- frontend tests pass;
- frontend lint exits `0`;
- frontend build exits `0`;
- final line is `== Atlas foundation checks passed ==`.

- [ ] **Step 3: Replace the root README with foundation startup documentation**

Update `README.md` to contain:

```markdown
# Atlas

Atlas é uma plataforma corporativa especializada em Supply Chain, Compras,
Estoque, Comércio Exterior e Financeiro, evoluída a partir do protótipo Cargo.Ops.

## Arquitetura

- Frontend: React + TypeScript + Vite
- Backend: FastAPI
- Banco: PostgreSQL
- Estilo: Monólito Modular

## Portas locais

| Serviço | Porta |
|---|---:|
| Frontend | 5174 |
| Backend | 8001 |
| PostgreSQL | 5433 |

## Estrutura

- `frontend/`: nova interface Atlas.
- `backend/`: API e regras de negócio.
- `database/`: documentação de persistência.
- `docs/`: requisitos, decisões, especificações e planos.
- `legacy/cargo-ops-prototype/`: protótipo Cargo.Ops preservado.
- `scripts/`: verificações locais.

## Subir PostgreSQL

```powershell
docker compose up -d postgres
```

## Backend

```powershell
Set-Location .\backend
uv run fastapi dev app/main.py --port 8001
```

API:

`http://localhost:8001/api/health`

Documentação OpenAPI:

`http://localhost:8001/docs`

## Frontend

```powershell
Set-Location .\frontend
npm run dev -- --port 5174
```

Aplicação:

`http://localhost:5174`

## Verificação completa

Na raiz:

```powershell
.\scripts\check.ps1
```

## Segurança

Nunca versionar:

- `.env`;
- credenciais;
- tokens;
- senhas;
- chaves JWT.

Utilize os arquivos `.env.example` apenas como modelo.
```

- [ ] **Step 4: Run final foundation verification**

Run:

```powershell
.\scripts\check.ps1
git diff --check
git status
```

Expected:
- verification script passes;
- `git diff --check` returns no output;
- only `README.md` and `scripts/check.ps1` are pending.

- [ ] **Step 5: Commit**

Run:

```powershell
git add .\README.md .\scripts\check.ps1
git commit -m "docs: add Atlas foundation developer workflow"
```

---

## Foundation Completion Gate

The foundation is complete only after all of the following commands pass in the implementation branch:

```powershell
node --check .\legacy\cargo-ops-prototype\app.js
```

```powershell
Set-Location .\backend
uv run pytest -v
uv run ruff check .
Set-Location ..
```

```powershell
Set-Location .\frontend
npm test
npm run lint
npm run build
Set-Location ..
```

```powershell
docker compose ps
```

Expected: PostgreSQL `atlas-postgres` is healthy.

```powershell
Invoke-RestMethod http://localhost:8001/api/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "atlas-api"
}
```

```powershell
git status
```

Expected:

```text
nothing to commit, working tree clean
```

After this gate, the next independent implementation plan will be:

**Atlas Identity, Roles and Organizational Access**

That plan will introduce:
- users;
- authentication;
- RBAC;
- DIRETORIA;
- COORDENACAO;
- SUPERVISAO;
- COMPRADOR;
- FINANCEIRO;
- LOJA;
- CENTRO_DISTRIBUICAO;
- ADMIN;
- purchase scope `NATIONAL | INTERNATIONAL | BOTH`;
- organizational unit access.

No business module should be implemented before the foundation gate above passes.
