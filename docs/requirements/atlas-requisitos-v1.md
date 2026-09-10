# ATLAS — Documento de Requisitos v1.0

**Projeto:** Atlas Supply / Cargo.Ops  
**Tipo:** Plataforma de Gestão de Supply Chain, Compras e Comércio Exterior  
**Versão:** 1.0 — Baseline Inicial  
**Status:** Em levantamento e validação  
**Data de registro no repositório:** 29/08/2026

## 1. Objetivo

O Atlas será uma plataforma corporativa para centralizar operações de Compras, Estoque, Importação, Financeiro e Supply Chain.

O sistema deve substituir controles espalhados em planilhas e rotinas manuais por uma visão única da operação, respondendo perguntas como:

- O que temos em estoque?
- Onde está esse estoque?
- Qual o consumo e a cobertura de cada produto?
- O que precisa ser comprado?
- O que já foi comprado?
- O que está em produção ou importação?
- Onde estão os containers e quando chegarão?
- Qual o status aduaneiro?
- Quanto tempo resta para devolver containers?
- Existe risco de multa ou demurrage?
- Quanto já foi pago e quanto falta pagar?
- Qual câmbio está sendo utilizado?
- Quais atividades exigem atenção imediata?

## 2. Visão do Produto

O Atlas atuará como uma **Control Tower de Supply Chain**, integrando Coordenação, Supervisão, Compradores, Financeiro, COMEX, Estoque e Administração.

```text
ATLAS
├── Compras
├── Importação / COMEX
├── Estoque
├── Financeiro
├── Agenda
├── Relatórios
└── Administração
        ↓
Dashboard / Control Tower
```

O produto deve evoluir em três níveis de maturidade:

- **Informação:** o que está acontecendo?
- **Alerta:** o que necessita de atenção?
- **Inteligência:** qual ação deve ser considerada?

## 3. Módulos

### Dashboard

Visão executiva e operacional personalizada por perfil.

### Compras

- Pedidos
- Sugestão de Compra
- Cotações
- Fornecedores
- Aprovações

### Importação

- Processos
- Containers
- Portos
- Navios
- Bookings
- Proformas
- Desembaraço Aduaneiro
- Entrega
- Devolução de Containers

### Estoque

- Produtos
- Lojas
- Depósitos
- Movimentações
- Cobertura
- Necessidade de Compra

### Financeiro

- Adiantamentos
- Saldos
- Numerário
- Câmbio
- Custos de Importação

### Agenda

Agenda operacional, eventos e alertas de atividade.

### Relatórios

Relatórios operacionais, gerenciais e executivos.

### Administração

- Usuários
- Perfis
- Permissões
- Empresas
- Fornecedores
- Integrações
- Auditoria

## 4. Perfis de Usuário

| Código | Perfil | Principais acessos |
|---|---|---|
| PERF-001 | Coordenação | Dashboard executivo, Compras, Importação, Estoque, Relatórios, Aprovações e Indicadores |
| PERF-002 | Supervisão | Dashboard operacional, Estoque, Produtos, Lojas, Depósitos, Movimentações, Importação e Relatórios |
| PERF-003 | Comprador Internacional | Produtos, Estoque, Necessidade de Compra, Sugestões, Fornecedores, Cotações e Pedidos |
| PERF-004 | Comprador Nacional | Produtos, Estoque, Necessidade de Compra, Sugestões, Fornecedores, Cotações e Pedidos |
| PERF-005 | Financeiro | Proformas, Adiantamentos, Pagamentos, Saldos, Numerário, Câmbio e Custos de Importação |
| PERF-006 | Administrador | Usuários, Perfis, Permissões, Configurações, Integrações, Auditoria e Logs |

## 5. Permissões Iniciais

O Atlas deve suportar controle por perfil e por permissão individual.

Permissões de referência:

- `STOCK_VIEW`
- `STOCK_IMPORT`
- `PURCHASE_CREATE`
- `PURCHASE_APPROVE`
- `RFQ_CREATE`
- `RFQ_SEND`
- `IMPORT_VIEW`
- `IMPORT_UPDATE`
- `FINANCE_VIEW`
- `FINANCE_UPDATE`
- `USER_MANAGE`

## 6. Requisitos Funcionais

### Autenticação e Acesso

- **RF-001:** permitir login com credenciais válidas.
- **RF-002:** controlar sessão autenticada.
- **RF-003:** permitir logout manual.
- **RF-004:** apresentar funcionalidades conforme perfil.
- **RF-005:** permitir permissões individuais por funcionalidade.

### Dashboard

- **RF-006:** apresentar dashboard personalizado por perfil.
- **RF-007:** apresentar cotação atual de dólar e euro no topo da interface, com compra, venda, data, horário e fonte quando disponíveis.
- **RF-008:** apresentar indicadores de estoque: críticos, sem estoque, excesso, cobertura média, estoque por loja e depósito.
- **RF-009:** apresentar indicadores de importação: containers em trânsito, no porto, liberados, aguardando desembaraço e com Free Time próximo do vencimento.
- **RF-010:** exibir alertas por prioridade: Informativo, Atenção, Crítico e Urgente.

### Estoque

- **RF-011:** permitir cadastro e consulta de produtos com código, nome e descrição/grupo.
- **RF-012:** armazenar estoque por loja, depósito e centro de distribuição.
- **RF-013:** permitir visão consolidada do estoque.
- **RF-014:** registrar entradas, saídas, transferências e ajustes.
- **RF-015:** manter histórico de movimentações.
- **RF-016:** calcular cobertura de estoque.
- **RF-017:** identificar estoque crítico.
- **RF-018:** identificar excesso de estoque.
- **RF-019:** separar estoque em trânsito do estoque físico disponível.
- **RF-020:** identificar necessidade de compra usando estoque, consumo, pedidos e trânsito.

### Sugestão de Compra

- **RF-021:** gerar sugestões com estoque disponível, reservado, venda média, cobertura, mínimo, máximo, lead time, trânsito e pedidos existentes.
- **RF-022:** permitir ajuste manual da quantidade sugerida.
- **RF-023:** exigir justificativa para alterações relevantes quando configurado.

### Fornecedores e Cotações

- **RF-024:** permitir cadastro de fornecedor com dados fiscais, internacionais, contatos, produtos, condições, lead time e status.
- **RF-025:** permitir seleção de produtos para cotação.
- **RF-026:** permitir seleção de fornecedores participantes.
- **RF-027:** enviar solicitação de cotação por e-mail aos fornecedores selecionados.
- **RF-028:** gerar identificador único de cotação no padrão `COT-AAAA-NNNNNN`.
- **RF-029:** registrar respostas de fornecedor com preço, ICMS, IPI, quantidade, prazo, frete, pagamento, validade e observações.
- **RF-030:** gerar mapa comparativo entre propostas recebidas.
- **RF-031:** converter cotação aprovada em Pedido de Compra.

### Pedidos de Compra

- **RF-032:** permitir cadastro de pedidos de compra.
- **RF-033:** permitir múltiplos itens por pedido.
- **RF-034:** controlar estados: Rascunho, Aguardando Aprovação, Aprovado, Enviado Fornecedor, Em Produção, Pronto Embarque, Em Trânsito, Recebido e Cancelado.
- **RF-035:** permitir aprovação conforme regras configuráveis.
- **RF-036:** registrar histórico de aprovação com usuário, data, horário, decisão e comentário.

### Importação

- **RF-037:** criar processo de importação no padrão `IMP-AAAA-NNNNNN`.
- **RF-038:** vincular processo a um ou mais pedidos.
- **RF-039:** cadastrar e anexar Proforma Invoice.
- **RF-040:** armazenar informações de booking.
- **RF-041:** registrar navio.
- **RF-042:** registrar porto de origem.
- **RF-043:** registrar porto de destino.
- **RF-044:** armazenar ETD.
- **RF-045:** armazenar ETA.
- **RF-046:** registrar histórico de alterações de previsão.

### Containers

- **RF-047:** cadastrar containers associados ao processo de importação.
- **RF-048:** registrar número do container.
- **RF-049:** classificar tipo: 20GP, 40GP, 40HQ, 40NOR.
- **RF-050:** apresentar timeline do container: Booking, Embarcado, Em Trânsito, Chegada ao Brasil, Descarregado, Parametrização, Desembaraçado, Gate Out, Entrega, Descarga, Devolução e Finalizado.

### Desembaraço Aduaneiro

- **RF-051:** registrar canal de parametrização: Verde, Amarelo, Vermelho e Cinza.
- **RF-052:** vincular documentos obrigatórios por canal.
- **RF-053:** apresentar checklist documental.
- **RF-054:** registrar inspeção física quando necessário.
- **RF-055:** registrar data e horário de liberação aduaneira.

### Free Time / Time Left

- **RF-056:** armazenar Free Time concedido ao container.
- **RF-057:** calcular data limite para devolução.
- **RF-058:** apresentar tempo restante para devolução.
- **RF-059:** gerar alertas progressivos: 7 dias Normal, 3 dias Atenção, 2 dias Alerta, 1 dia Crítico e vencido Urgente.
- **RF-060:** cadastrar custo diário de atraso.
- **RF-061:** calcular custo acumulado ou projetado de demurrage.

### Financeiro

- **RF-062:** registrar adiantamentos pagos a fornecedor.
- **RF-063:** apresentar saldo pendente.
- **RF-064:** registrar condições de pagamento específicas por processo.
- **RF-065:** registrar câmbio utilizado por operação financeira.
- **RF-066:** manter histórico cambial usado em operações.
- **RF-067:** acompanhar numerário da operação.
- **RF-068:** registrar custos de importação: frete, seguro, armazenagem, desembaraço, transporte, demurrage, taxas e impostos.

### Integração Excel

- **RF-069:** permitir upload de arquivos Excel.
- **RF-070:** validar dados antes da importação definitiva.
- **RF-071:** apresentar preview dos registros.
- **RF-072:** destacar registros inválidos.
- **RF-073:** permitir importação parcial quando possível.
- **RF-074:** apresentar relatório de erros.
- **RF-075:** manter histórico de importações com arquivo, usuário, data, horário, registros, sucessos, erros e tipo.

### Agenda

- **RF-076:** cadastrar eventos operacionais: embarque, ETA, pagamento, vencimento documental, inspeção, retirada e devolução de container.
- **RF-077:** gerar alertas de agenda.

### Relatórios

- **RF-078:** gerar relatório de estoque por loja e depósito.
- **RF-079:** gerar relatório de cobertura.
- **RF-080:** gerar relatório de necessidade de compra.
- **RF-081:** gerar relatório de containers.
- **RF-082:** gerar relatório de importações.
- **RF-083:** gerar relatórios financeiros de pagamentos e custos.
- **RF-084:** exportar relatórios em XLSX, CSV e PDF quando aplicável.

### Administração

- **RF-085:** permitir cadastrar, alterar, ativar e inativar usuários.
- **RF-086:** administrar perfis.
- **RF-087:** vincular permissões a perfis.
- **RF-088:** configurar parâmetros operacionais sem alteração de código quando possível.

### Auditoria

- **RF-089:** registrar audit log de alterações críticas.
- **RF-090:** armazenar usuário, data, hora, operação, entidade, registro, valor anterior, novo valor e origem.
- **RF-091:** manter histórico imutável para usuários comuns.

## 7. Regras de Negócio

- **RN-001:** usuário só acessa funcionalidades permitidas.
- **RN-002:** produtos possuem identificador único.
- **RN-003:** estoques se relacionam a unidade física válida.
- **RN-004:** cobertura recalcula quando estoque ou consumo mudam.
- **RN-005:** mercadoria em trânsito não é estoque físico disponível.
- **RN-006:** pedidos cancelados não compõem necessidade futura.
- **RN-007:** cotação exige pelo menos um produto.
- **RN-008:** cotação exige pelo menos um fornecedor antes do envio.
- **RN-009:** resposta de fornecedor não substitui outra sem histórico.
- **RN-010:** pedido em aprovação não sofre alteração crítica sem retornar ao fluxo.
- **RN-011:** processo de importação pode possuir mais de um container.
- **RN-012:** container possui número único na operação.
- **RN-013:** alterações de ETA mantêm histórico.
- **RN-014:** canal aduaneiro determina fluxo documental.
- **RN-015:** canal Vermelho indica necessidade de verificação física.
- **RN-016:** Free Time exige data inicial ou evento de referência.
- **RN-017:** data limite de devolução usa condições vinculadas ao container.
- **RN-018:** container vencido no Free Time fica crítico.
- **RN-019:** custo de atraso considera dias excedidos e multa diária.
- **RN-020:** operação financeira em moeda estrangeira preserva o câmbio efetivamente usado.
- **RN-021:** importações Excel passam por validação antes da persistência.
- **RN-022:** arquivo já processado deve ter proteção contra duplicidade acidental.
- **RN-023:** alterações críticas geram auditoria.

## 8. Requisitos Não Funcionais

- **RNF-001:** armazenar credenciais com hash seguro.
- **RNF-002:** validar autorização no backend.
- **RNF-003:** usar HTTPS em produção.
- **RNF-004:** funcionar bem em computadores e tablets.
- **RNF-005:** deixar informações principais acessíveis com poucas interações.
- **RNF-006:** buscar tempo de resposta de até 2 segundos para consultas comuns.
- **RNF-007:** permitir inclusão futura de unidades, usuários, fornecedores e integrações.
- **RNF-008:** garantir consistência em transações críticas.
- **RNF-009:** possuir política de backup.
- **RNF-010:** registrar erros em logs técnicos.
- **RNF-011:** rastrear eventos críticos.
- **RNF-012:** separar responsabilidades de frontend e backend.
- **RNF-013:** comunicar frontend e backend por APIs documentadas.
- **RNF-014:** manter documentação técnica de endpoints.
- **RNF-015:** tratar indisponibilidade de integrações externas.

## 9. Arquitetura Inicial

```text
Frontend React
      │ REST / JSON
      ▼
Backend FastAPI
      │
      ▼
PostgreSQL

Integrações externas:
Excel · E-mail · Câmbio · ERP · APIs futuras
```

## 10. Fluxo Macro

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

## 11. Próximas Etapas Documentais

1. Documento de Requisitos
2. Regras de Negócio detalhadas
3. Matriz de Perfis e Permissões
4. Fluxogramas
5. Modelo de Dados / DER
6. Protótipos
7. Contratos da API
8. Backend
9. Frontend
10. Plano de Testes
11. Documentação Técnica
12. Implantação

## 12. Status da Versão 1.0

- 91 requisitos funcionais.
- 23 regras de negócio iniciais.
- 15 requisitos não funcionais.

Este documento é o baseline inicial do Projeto Atlas e deve ser atualizado conforme validações com Compras, Supply Chain, Financeiro, COMEX, Supervisão e Coordenação.
