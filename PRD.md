# PRD — Atlas Supply

## Problema

Empresas que operam Compras, Estoque, Importação, COMEX e Financeiro ainda dependem de planilhas, controles manuais e sistemas separados para responder perguntas críticas da operação.

O Atlas nasce para centralizar esses dados e transformar a operação em uma Control Tower de Supply Chain.

## Objetivo

Fornecer uma plataforma corporativa que mostre:

- estoque físico, reservado, em trânsito e consolidado;
- cobertura, ruptura, excesso e necessidade de compra;
- pedidos nacionais e internacionais;
- cotações, fornecedores, propostas e comparativos;
- processos de importação, containers, bookings, ETA, ETD, desembaraço e Free Time;
- adiantamentos, saldos, numerário, câmbio e custos de importação;
- alertas, agenda, auditoria e relatórios.

## Nome do Produto

O nome oficial passa a ser **Atlas**.

Cargo.Ops fica preservado como origem histórica e protótipo legado em `legacy/cargo-ops-prototype/`.

## Perfis

- Coordenação.
- Supervisão.
- Comprador Internacional.
- Comprador Nacional.
- Financeiro.
- Administrador.

## Módulos

- Dashboard.
- Compras.
- Importação.
- Estoque.
- Financeiro.
- Agenda.
- Relatórios.
- Administração.

## Requisitos Baseline

O baseline v1.0 está em:

`docs/requirements/atlas-requisitos-v1.md`

Resumo:

- 91 requisitos funcionais.
- 23 regras de negócio.
- 15 requisitos não funcionais.

## Arquitetura

- Frontend: React + TypeScript + Vite.
- Backend: FastAPI.
- Banco transacional alvo: PostgreSQL.
- Estilo inicial: Monólito Modular.
- Comunicação: REST / JSON.
- Integrações previstas: Excel, e-mail, câmbio, ERP e APIs futuras.

## Princípio Funcional

O Atlas deve evoluir em três níveis:

1. **Informação:** o que está acontecendo?
2. **Alerta:** o que necessita de atenção?
3. **Inteligência:** o que provavelmente deve ser feito?

## Próxima Fase Recomendada

Implementar Identity, Perfis e Acesso Organizacional:

- autenticação;
- sessão;
- perfis;
- permissões;
- usuários;
- unidades organizacionais;
- escopo de comprador Nacional, Internacional ou Ambos.
