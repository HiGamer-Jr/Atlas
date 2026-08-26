# Cargo.Ops Supply Chain

## Proposta

Sistema focado em Compras e Supply Chain para ir além de um ERP genérico: ele conecta demanda de estoque, cotação com fornecedor, pedido, aprovação, importação, câmbio e financeiro em um fluxo único.

## Perfis

- Coordenador: visão completa, aprovações, governança de compras e indicadores.
- Supervisão: acompanha operação, valida compras, monitora estoque e importação.
- Comprador: cria pedidos, dispara cotações, consulta produtos e acompanha aprovações.
- Financeiro: gera pré-notas, acompanha adiantamentos, saldo, numerário e câmbio.
- Administração: usuários, perfis, parâmetros e integrações.

## Estrutura funcional

Login
↓
Dashboard
├── Compras
│   ├── Pedidos
│   ├── Sugestão de Compra
│   ├── Aprovações
│
├── Importação
│   ├── Processos
│   ├── Containers
│   ├── Portos
│   ├── Navios
│   ├── Proformas
│
├── Estoque
│   ├── Produtos
│   ├── Depósitos
│   ├── Movimentações
│
├── Financeiro
│   ├── Adiantamentos
│   ├── Saldo
│   ├── Numerário
│   ├── Câmbio
│
├── Agenda
│
├── Relatórios
│
└── Administração

## Fluxos principais

1. Cotação automática
   - Comprador seleciona um ou mais produtos.
   - Sistema identifica categoria, NCM, fornecedores homologados e fornecedores internacionais.
   - Um clique gera RFQ e abre e-mail com produtos, quantidade sugerida, prazo de resposta e condições solicitadas.
   - Em produção, esse fluxo deve evoluir para SMTP/API de e-mail, trilha de auditoria e portal do fornecedor.

2. Sugestão de compra
   - Estoque compara saldo atual versus estoque mínimo.
   - Produtos abaixo do mínimo entram na fila de sugestão.
   - Sugestão pode virar RFQ ou pedido.

3. Aprovação
   - Pedido nasce em aprovação.
   - Supervisão ou Coordenador aprova/rejeita.
   - Pedido aprovado fica disponível para financeiro gerar pré-nota e tratar pagamento.

4. Excel
   - Exportação de produtos e pedidos em arquivo compatível com Excel.
   - Importação de produtos via CSV e, quando a biblioteca XLSX estiver disponível, `.xlsx`/`.xls`.
   - Em produção, usar fila de importação com validação de SKU, NCM, duplicidade e relatório de erros.

5. Dólar
   - Box global USD/BRL no topo do sistema.
   - Atualização automática a cada 5 minutos via AwesomeAPI.
   - Fallback gracioso quando a rede/API não estiver disponível.

6. Financeiro e nota fiscal
   - O protótipo gera pré-nota/espelho fiscal operacional.
   - Emissão fiscal real exige integração com SEFAZ, certificado digital, regras tributárias, XML NF-e/NFS-e e autorização de uso.
   - Financeiro envia e-mails para fornecedores solicitando dados cadastrais, bancários e tratativas.

## Diferenciais para superar ERPs genéricos em Compras

- RFQ orientado por produto, categoria e fornecedor homologado.
- Câmbio visível no contexto de pedido, proforma e financeiro.
- Conversão automática USD → BRL para compras internacionais.
- Sugestão de compra baseada em estoque mínimo.
- Pipeline integrado: estoque → cotação → pedido → aprovação → financeiro.
- Preparação para importação com containers, portos, navios e proformas.
- Operação por perfil, com navegação reduzida ao papel de cada usuário.

## Arquitetura recomendada para produção

- Frontend: React, TypeScript, React Router, Tailwind ou design system próprio.
- Backend: FastAPI ou NestJS, API REST/GraphQL, JWT com refresh token httpOnly.
- Banco: PostgreSQL para dados transacionais; Redis para filas/cache; object storage para anexos.
- Integrações: SMTP/API de e-mail, AwesomeAPI/Banco Central, SEFAZ, Receita Federal para NCM/CNPJ, ERP contábil, gateways de câmbio e planilhas.
- Auditoria: eventos imutáveis por pedido, aprovação, cotação, nota e e-mail.
- Segurança: RBAC por perfil, logs, LGPD, MFA para perfis críticos.

## Próximos incrementos

- Portal do fornecedor para responder RFQ sem e-mail.
- Comparativo automático de propostas.
- Workflow de alçada por valor, categoria e centro de custo.
- Anexos em proformas, pedidos e notas.
- Importação Excel com validação detalhada.
- API real de NF-e com autorização SEFAZ.
- Dashboard de saving, lead time e performance de fornecedor.
