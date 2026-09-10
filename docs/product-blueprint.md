# Atlas Supply — Blueprint de Produto

## Proposta

O Atlas é uma Control Tower de Supply Chain para centralizar Compras, Estoque, Importação, Financeiro e Relatórios em uma única plataforma corporativa.

O objetivo é reduzir controles paralelos, dar visibilidade operacional e apoiar decisões com informação, alerta e inteligência.

## Origem

O projeto começou como Cargo.Ops.

A partir da versão v1.0 de requisitos, o nome oficial é **Atlas**. O protótipo Cargo.Ops permanece preservado em `legacy/cargo-ops-prototype/` como referência visual, funcional e histórica.

## Módulos

### Dashboard

Painel personalizado por perfil com cotações USD/BRL e EUR/BRL, indicadores de estoque, importação, financeiro e alertas por prioridade.

### Compras

Pedidos, sugestões de compra, cotações, fornecedores, aprovações, respostas de fornecedores e mapa comparativo.

### Importação / COMEX

Processos, containers, portos, navios, bookings, proformas, desembaraço aduaneiro, entrega, devolução de containers, Free Time, Time Left e demurrage.

### Estoque

Produtos, lojas, depósitos, movimentações, cobertura, estoque crítico, excesso, trânsito e necessidade de compra.

### Financeiro

Adiantamentos, saldos, numerário, câmbio utilizado, histórico cambial, pagamentos e custos de importação.

### Agenda

Eventos operacionais, vencimentos, alertas de agenda e atividades entre setores.

### Relatórios

Relatórios de estoque, cobertura, necessidade de compra, containers, importações, financeiro e exportações XLSX, CSV e PDF.

### Administração

Usuários, perfis, permissões, empresas, fornecedores, integrações, configurações e auditoria.

## Perfis

- Coordenação: visão ampla, aprovações e indicadores.
- Supervisão: operação, estoque, produtos, unidades, importação e relatórios.
- Comprador Internacional: produtos, estoque, necessidade, fornecedores, cotações e pedidos internacionais.
- Comprador Nacional: produtos, estoque, necessidade, fornecedores, cotações e pedidos nacionais.
- Financeiro: proformas, adiantamentos, pagamentos, saldos, numerário, câmbio e custos.
- Administrador: usuários, perfis, permissões, integrações, auditoria e logs.

## Fluxo Macro

```text
Estoque
  ↓
Análise de cobertura
  ↓
Necessidade de compra
  ↓
Cotação
  ↓
Fornecedores
  ↓
Comparativo
  ↓
Aprovação
  ↓
Pedido de compra
  ↓
Proforma
  ↓
Pagamento / Adiantamento
  ↓
Produção
  ↓
Booking
  ↓
Embarque
  ↓
Container em trânsito
  ↓
Chegada ao Brasil
  ↓
Desembaraço
  ↓
Retirada do porto
  ↓
Entrega
  ↓
Descarga
  ↓
Devolução container
  ↓
Entrada no estoque
  ↓
Novo ciclo
```

## Diferenciais

- Visão única da operação, sem depender de planilhas isoladas.
- Estoque por loja, depósito e centro de distribuição.
- Necessidade de compra baseada em cobertura, consumo, pedidos e trânsito.
- Cotações com fornecedores, respostas e comparativo.
- Tracking de containers com Free Time, Time Left e risco de demurrage.
- Câmbio preservado por operação financeira.
- Auditoria para alterações críticas.
- Evolução modular para não recriar o sistema a cada nova regra.

## Arquitetura Recomendada

- Frontend: React + TypeScript + Vite.
- Backend: FastAPI.
- Banco: PostgreSQL.
- Integrações: Excel, e-mail, câmbio, ERP e APIs futuras.
- Segurança: hash de senha, autorização no backend, HTTPS em produção, audit log e controle por permissão.

## Referências

- Requisitos v1.0: `docs/requirements/atlas-requisitos-v1.md`.
- Arquitetura da fundação: `docs/superpowers/specs/2026-08-26-atlas-foundation-design.md`.
- Plano da fundação: `docs/superpowers/plans/2026-08-26-atlas-foundation-implementation.md`.
