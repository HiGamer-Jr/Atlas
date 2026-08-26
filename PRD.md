# PRD — Cargo.Ops ERP

## Problema Original
Sistema para atender demanda de estoque, compras, importações, com informação atualizada do valor do dólar. Estrutura hierárquica:
Login → Dashboard → Compras (Pedidos, Sugestão de Compra, Aprovações) | Importação (Processos, Containers, Portos, Navios, Proformas) | Estoque (Produtos, Depósitos, Movimentações) | Financeiro (Adiantamentos, Saldo, Numerário, Câmbio) | Agenda | Relatórios | Administração.

## Escolhas do Usuário
- Autenticação: JWT customizado (email/senha)
- Cotação USD/BRL: AwesomeAPI (economia.awesomeapi.com.br) com fallback gracioso
- Perfis: admin, gerente, supervisor, comprador, financeiro, logistica
- MVP: Todos os módulos com CRUD básico funcional
- Idioma: Português brasileiro

## Personas
- **Admin**: gerencia usuários e perfis; acesso total.
- **Gerente**: aprova pedidos, supervisiona operação.
- **Supervisor**: supervisão operacional em Compras/Estoque.
- **Comprador**: cria pedidos, gera sugestões.
- **Financeiro**: adiantamentos, saldo, numerário, câmbio.
- **Logística**: importação (processos, containers, portos, navios, proformas), movimentações.

## Arquitetura
- Backend FastAPI (`/app/backend/server.py`) com todos endpoints prefixados `/api`, MongoDB Motor, JWT (PyJWT), bcrypt, httpx para AwesomeAPI.
- Frontend React 19 + React Router 7 + Tailwind + Shadcn UI. Fontes: Chivo (títulos), IBM Plex Sans (corpo), IBM Plex Mono (números/moeda). Design: Swiss Brutalism / Industrial Logistics (bordas 1px, sem drop-shadows, laranja #FF5A00 + slate-950).
- Cookies httpOnly para access + refresh tokens.

## Implementado (Fev/2026)
- **Auth**: login/logout/me/register/refresh, seed admin, brute-force protection, RBAC.
- **Câmbio USD/BRL** em tempo real via AwesomeAPI com fallback.
- **Dashboard**: KPIs, ticker de dólar, quick-access, operações em andamento.
- **CRUD completo** para 15 coleções: pedidos, sugestoes, aprovacoes, processos, containers, portos, navios, proformas, produtos, depositos, movimentacoes, adiantamentos, saldo, numerario, cambio, agenda.
- **Agenda** com calendário Shadcn + lista.
- **Relatórios** com gráficos Recharts (bar + pie).
- **Administração** de usuários (criar, editar role, excluir).
- **Sidebar** industrial dark + Topbar com ticker.
- **Testing agent 100% passed** (backend + frontend).

## Backlog
### P1
- Vincular Pedidos ↔ Aprovações (workflow real com botões "Aprovar/Rejeitar")
- Cálculo automático BRL a partir de USD × taxa em pedidos/proformas
- Notificações in-app (badge no sino do topbar)
- Import CSV/Excel para Produtos e Movimentações
- Filtros avançados por status / data range nas tabelas

### P2
- Anexos em Proformas / Processos (object storage)
- Timeline visual de container tracking (stepper)
- Exportar relatórios em PDF/Excel
- Multi-empresa / multi-filial

### P3
- Integração com Receita Federal (NCM lookup)
- Alertas de câmbio (webhook quando USD/BRL passar de threshold)
- App mobile

## Credenciais de Teste
Ver `/app/memory/test_credentials.md`.
