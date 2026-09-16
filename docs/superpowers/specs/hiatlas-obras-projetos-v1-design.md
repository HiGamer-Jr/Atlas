# HiAtlas — Obras & Projetos v1 — Design Oficial

**Data:** 2026-09-16  
**Status:** Design formalizado após aprovação conceitual  
**Produto:** HiAtlas  
**Posicionamento:** Supply Chain Intelligence  
**Slogan:** *Um novo horizonte para o seu negócio.*

## 1. Visão

O módulo **Obras & Projetos** amplia o HiAtlas para conectar planejamento, compras, materiais, logística, estoque, pessoas, liberações, documentos, custos e execução de obras em uma única visão operacional.

O objetivo não é transformar o HiAtlas em um ERP genérico de construção civil. O objetivo é permitir que uma empresa saiba, com antecedência, se uma obra está realmente pronta para iniciar e se continuará saudável em prazo, custo, materiais, equipe e conformidade.

> **Uma obra não deveria começar sem o HiAtlas conseguir explicar se pessoas, materiais, documentos, recursos e orçamento estão realmente prontos.**

Durante a execução:

> **Um atraso ou estouro não deveria ser descoberto depois que aconteceu se os dados necessários para prevê-lo já estavam disponíveis.**

## 2. Perguntas que o módulo deve responder

Ao abrir uma obra, o usuário deve conseguir responder rapidamente:

- Quando a obra começa e quando deveria terminar?
- Qual é o prazo projetado de conclusão?
- O cronograma está adiantado, no prazo ou atrasado?
- Qual era o orçamento aprovado?
- Quanto já foi comprometido?
- Quanto foi efetivamente realizado?
- Quanto ainda deverá ser gasto?
- Qual é a previsão de custo final?
- A obra está positiva ou negativa em relação ao orçamento?
- Se for uma obra vendida a cliente, qual é a margem projetada?
- Todo o material necessário já foi comprado?
- O que já chegou?
- O que está em trânsito?
- O que ainda falta?
- Algum material chegará depois do início da atividade que depende dele?
- Existe estoque em outro CD, loja, depósito ou obra que possa evitar uma nova compra?
- A equipe está liberada?
- Treinamentos obrigatórios estão válidos?
- Documentos, acessos, permissões e liberações estão completos?
- Existem riscos que podem afetar os próximos 1–7 dias?
- O que está surgindo no horizonte de 7–30 dias?
- Quais decisões precisam ser tomadas hoje?

## 3. Navegação

```text
OBRAS & PROJETOS
│
├── Visão Geral
├── Portfólio de Obras
├── Cronograma
├── Calendário
│
├── Orçamento & Custos
│   ├── Orçamento Original
│   ├── Orçamento Revisado
│   ├── Custos Comprometidos
│   ├── Custos Realizados
│   └── Previsão de Fechamento
│
├── Materiais
│   ├── Necessidades
│   ├── Comprados
│   ├── Em Trânsito
│   ├── Recebidos
│   ├── Consumidos
│   └── Pendentes
│
├── Compras da Obra
├── Equipes & Terceiros
├── Treinamentos & Liberações
├── Documentos
├── Equipamentos
├── Diário de Obra
├── Medições
├── Mudanças & Aditivos
├── Riscos & Pendências
└── Relatórios
```

## 4. Entidade Obra

Cada obra deve possuir um identificador único, por exemplo `OBR-2026-001`.

Campos principais:

- código;
- nome;
- empresa;
- cliente, quando aplicável;
- unidade / canteiro;
- tipo da obra;
- responsável;
- gestor;
- status;
- início previsto;
- início real;
- entrega prevista;
- entrega projetada;
- entrega real;
- progresso físico;
- progresso planejado;
- orçamento aprovado;
- orçamento revisado;
- custo comprometido;
- custo realizado;
- custo a realizar;
- custo final projetado;
- valor do contrato, quando aplicável;
- margem projetada;
- observações;
- tenant;
- empresa;
- unidade organizacional.

Status iniciais:

- PLANEJADA
- PRONTA_PARA_INICIAR
- EM_RISCO
- EM_ANDAMENTO
- PAUSADA
- ATRASADA
- CONCLUIDA
- CANCELADA

## 5. EAP / WBS — Estrutura Analítica da Obra

Toda obra deve poder ser dividida em:

```text
OBRA
└── ETAPA
    └── ATIVIDADE
        └── SUBATIVIDADE (opcional)
```

Cada atividade pode ter responsável, início/fim previsto e real, duração, dependências, percentual concluído, materiais, equipe, documentos/liberações, equipamentos e custos vinculados.

## 6. Cronograma

Duas visões principais:

**Calendário:** datas de início, término, marcos, entregas, vencimentos, treinamentos, medições e eventos.

**Gantt:** etapas, atividades, dependências e desvios.

Indicadores:

- planejado x realizado;
- dias de atraso;
- atividades críticas;
- atividades bloqueadas;
- impacto na entrega final;
- marcos atrasados;
- predecessoras não concluídas.

O caminho crítico completo pode entrar depois; a v1 precisa ao menos modelar dependências e bloqueios.

## 7. Orçamento e Custos

Categorias mínimas:

- materiais;
- mão de obra;
- terceiros/subcontratados;
- equipamentos;
- frete/logística;
- locações;
- impostos e taxas;
- licenças;
- segurança/EPI;
- administrativo;
- contingência;
- outros.

Para cada categoria:

- previsto;
- revisado;
- comprometido;
- realizado;
- a realizar;
- projeção final;
- desvio absoluto;
- desvio percentual.

### Obra interna

```text
Orçamento revisado
x
Custo final projetado
=
Desvio projetado
```

### Obra vendida

```text
Valor do contrato
-
Custo final projetado
=
Margem projetada
```

## 8. Integração com Compras

Todo pedido pode ser relacionado a obra, etapa, atividade, centro de custo, material, quantidade, data de necessidade, destino e responsável.

Exemplo:

```text
PO-001245
Obra: OBR-2026-014
Etapa: Estrutura metálica
Material: Perfil galvanizado
Quantidade: 12.000
Necessário até: 18/10
Entrega prevista: 21/10
```

Resultado:

> **Risco: material previsto três dias depois do início da atividade.**

## 9. Materiais da Obra

Controlar:

- necessidade planejada;
- quantidade solicitada;
- comprada;
- em trânsito;
- recebida;
- reservada;
- consumida;
- excedente;
- saldo projetado.

Antes de sugerir nova compra, o HiAtlas deve verificar estoque físico, pedidos abertos, cargas em trânsito, transferências e estoque em outras unidades/obras.

## 10. Obra como Unidade Operacional

Adicionar conceitualmente um novo tipo de unidade:

```text
WORKSITE
```

Isso permite controlar material fisicamente disponível no canteiro.

## 11. Prontidão da Obra

Criar indicador de **Prontidão para Início** e, opcionalmente, prontidão por etapa.

Dimensões:

- materiais;
- equipe;
- terceiros;
- treinamentos;
- documentos;
- liberações;
- equipamentos;
- acessos;
- segurança;
- planejamento.

Requisitos obrigatórios não cumpridos podem bloquear a prontidão independentemente da média.

## 12. Pessoas, Terceiros e Treinamentos

Relacionamento:

```text
PESSOA
  ↓
EMPRESA / TERCEIRO
  ↓
OBRA
  ↓
ATIVIDADE
  ↓
REQUISITOS
```

Alertas:

- treinamento vencido;
- treinamento vencendo;
- documento ausente;
- terceiro não homologado;
- pessoa não liberada;
- requisito incompatível com a data da atividade.

## 13. Documentos e Liberações

Cada obra e atividade pode possuir checklist documental configurável por tipo de obra e cliente.

Exemplos: contrato, projeto aprovado, licenças, autorizações, documentos técnicos, documentos de segurança, documentação de terceiros, permissões de acesso, inspeções e aprovações internas.

## 14. Equipamentos e Recursos

Controlar recurso, quantidade, disponibilidade, reserva, manutenção, locação, fornecedor, data necessária, data disponível e atividade vinculada.

Exemplo:

> **Guindaste necessário em 4 dias, mas reserva ainda não confirmada.**

## 15. Diário de Obra

Registrar diariamente:

- data;
- responsável;
- equipe/terceiros presentes;
- horas trabalhadas;
- atividades executadas;
- progresso;
- materiais recebidos;
- materiais consumidos;
- equipamentos utilizados;
- paralisações;
- motivos;
- ocorrências;
- riscos;
- fotos/anexos;
- observações.

## 16. Medições

Registrar obra, período, etapa, percentual executado, quantidade executada, valor medido, valor aprovado, data, responsável, status, observações e anexos.

## 17. Mudanças e Aditivos

Fluxo:

```text
SOLICITAÇÃO
   ↓
ANÁLISE DE IMPACTO
   ↓
CUSTO / PRAZO
   ↓
APROVAÇÃO
   ↓
NOVO BASELINE
```

Alerta importante:

> **Custo de mudança sendo realizado antes da aprovação do aditivo.**

## 18. Riscos e Pendências

Cada risco possui descrição, categoria, probabilidade, impacto, criticidade, responsável, prazo, plano de resposta, status e evidências.

Categorias iniciais: prazo, custo, material, fornecedor, logística, equipe, segurança, documentação, qualidade, cliente, clima e equipamento.

## 19. Horizon / Copiloto para Obras

### Hoje

- material crítico ainda não entregue;
- atividade inicia hoje sem prontidão;
- pessoa sem liberação;
- documento obrigatório vencido;
- medição aguardando aprovação;
- custo crítico sem aprovação.

### 1–7 dias

- atividade inicia com materiais incompletos;
- treinamento vence antes da atividade;
- pedido possui ETA posterior à data de necessidade;
- equipamento ainda não reservado;
- predecessora atrasada ameaça próxima atividade.

### 7–30 dias

- custo final projetado acima do orçamento;
- tendência de atraso;
- queda de margem;
- estoque excedente em outra obra que pode ser transferido;
- concentração de atividades sem recursos suficientes;
- vencimento futuro de documentação relevante.

Tipos de sinal:

- ACTION
- RISK
- OPPORTUNITY
- DATA_QUALITY

Todo sinal deve explicar o que aconteceu/pode acontecer, por quê, quais dados sustentam a conclusão, impacto e ação recomendada.

## 20. Modo Reunião

Visão consolidada:

```text
OBRA: Ampliação CD Bauru
STATUS: EM RISCO

Progresso físico        42%
Progresso planejado     48%

Orçamento revisado      R$ 2,64 mi
Projeção final          R$ 2,78 mi
Desvio projetado      + R$ 140 mil

Entrega prevista        20/01
Entrega projetada       28/01
Desvio                  +8 dias

Prontidão próxima fase  76%

Materiais críticos       3
Pedidos atrasados         2
Documentos pendentes      4
Treinamentos pendentes    2

TOP RISCOS
DECISÕES PENDENTES
PRÓXIMOS 7 DIAS
```

Objetivo:

> **O HiAtlas deve ser a fonte da reunião, não mais uma planilha a ser procurada durante a reunião.**

## 21. Dashboard Executivo de Obras

Indicadores: obras ativas, em risco, atrasadas, críticas, orçamento total, custo realizado, comprometido, custo final projetado, exposição, margem, materiais críticos, decisões pendentes, prontidão e principais riscos.

## 22. Data Hub / Template de Obras

Arquivo conceitual:

`HiAtlas_Obras_Template.xlsx`

Abas:

- OBRAS
- ETAPAS
- ATIVIDADES
- MARCOS
- ORCAMENTO
- MATERIAIS
- PEDIDOS
- ENTREGAS
- EQUIPE
- TERCEIROS
- TREINAMENTOS
- DOCUMENTOS
- LIBERACOES
- EQUIPAMENTOS
- RISCOS
- MEDICOES
- ADITIVOS

## 23. Perfis e Permissões

Usar o RBAC central do HiAtlas.

Perfis possíveis: Diretoria, Coordenação, Gestor de Obras, Engenharia, Planejamento, Comprador, Financeiro, Estoque/CD, Segurança/Qualidade, Fiscalização e Administrador.

## 24. Arquitetura

Manter **monólito modular**.

Fronteiras lógicas sugeridas:

```text
projects
schedules
project_costs
project_materials
project_readiness
project_people
project_documents
project_equipment
project_risks
project_changes
project_daily_logs
project_measurements
project_horizon
```

Integrações com Compras, Estoque, Inbound/Cargas, Financeiro, Agenda, Data Hub, Notificações, Auditoria e Identity/RBAC.

Toda entidade deve respeitar tenant, empresa, unidade organizacional, permissões e auditoria.

## 25. Indicadores avançados — evolução futura

Após a fundação, poderão entrar:

- valor planejado;
- valor agregado;
- custo real;
- CPI;
- SPI;
- estimativa no término;
- desvio no término;
- produtividade;
- desempenho por fornecedor;
- horas perdidas por causa;
- custo de retrabalho.

Não entram na Fase 1.

## 26. Fora do escopo inicial

Não implementar agora: BIM, CAD/3D, emissão fiscal, folha, jurídico completo, SST completo, gestão de frota completa, machine learning, microserviços ou chatbot generativo completo.

## 27. Roadmap recomendado

### Fase 1 — Foundation Obras
Cadastro, status, datas, responsável, empresa/unidade, orçamento-base, dashboard inicial, dados demonstrativos e permissões.

### Fase 2 — Cronograma
Etapas, atividades, marcos, dependências, calendário e planejado x realizado.

### Fase 3 — Orçamento & Custos
Orçamento, categorias, comprometido, realizado, projeção final e margem.

### Fase 4 — Materiais
Necessidade, pedidos, estoque, inbound, recebimento, consumo e transferências.

### Fase 5 — Prontidão
Pessoas, terceiros, treinamentos, documentos, liberações, equipamentos e indicador de prontidão.

### Fase 6 — Horizon Obras
Hoje, 1–7, 7–30, ações, riscos, oportunidades e recomendações explicáveis.

### Fase 7 — Execução
Diário, medições, mudanças, aditivos e histórico.

### Fase 8 — Executivo
Portfólio, comparação entre obras, indicadores executivos e modo reunião.

## 28. Critério de sucesso

Em menos de 30 segundos, o responsável deve responder: está no prazo, está no orçamento, está pronta para a próxima etapa, o material está disponível, o que está em trânsito, há pessoas/documentos/equipamentos pendentes, o que exige ação hoje, o que pode virar problema em 7 dias, o que surge em 30 dias e qual ação o HiAtlas recomenda.

## 29. Regra de produto consolidada

> **O HiAtlas Obras & Projetos deve conectar planejamento, materiais, pessoas, custos e execução para antecipar riscos antes que eles interrompam uma obra ou destruam sua margem.**

# **Um novo horizonte para o seu negócio.**
