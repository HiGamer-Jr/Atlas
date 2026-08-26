# Atlas — Foundation Architecture Design

**Data:** 26/08/2026
**Status:** Arquitetura inicial aprovada
**Origem:** Evolução do protótipo Cargo.Ops

## 1. Objetivo

O Atlas será uma plataforma corporativa especializada em Supply Chain, Compras, Estoque, Comércio Exterior e Financeiro.

O objetivo não é reproduzir um ERP genérico.

O sistema deverá conectar dados operacionais e transformá-los em:

* informação;
* alerta;
* recomendação;
* decisão;
* rastreabilidade.

O Atlas deverá ser preparado para evolução contínua de requisitos sem necessidade de reestruturações frequentes da aplicação.

## 2. Estratégia de evolução do Cargo.Ops

O Cargo.Ops existente será preservado como referência funcional e visual.

O protótipo atual não será utilizado como fundação técnica da aplicação de produção porque concentra responsabilidades em um frontend JavaScript monolítico e utiliza armazenamento local.

Nenhuma regra funcional útil será descartada sem avaliação.

Cada funcionalidade será classificada como:

* Manter;
* Evoluir;
* Refatorar;
* Substituir;
* Criar.

O protótipo deverá futuramente ser preservado em:

`legacy/cargo-ops-prototype/`

## 3. Estilo arquitetural

O Atlas utilizará inicialmente um **Monólito Modular**.

Não serão utilizados microserviços na primeira fase.

Motivos:

* menor complexidade operacional;
* implantação mais simples;
* transações consistentes;
* facilidade de desenvolvimento;
* facilidade de testes;
* menor custo de infraestrutura;
* possibilidade de separar serviços futuramente caso exista necessidade real.

Cada domínio deverá possuir limites e responsabilidades bem definidos.

## 4. Stack principal

### Frontend

* React;
* TypeScript;
* arquitetura por módulos;
* componentes reutilizáveis;
* comunicação através da API.

### Backend

* Python;
* FastAPI;
* API REST;
* validação por schemas;
* camada de serviços;
* camada de persistência;
* autenticação;
* autorização RBAC;
* auditoria.

### Banco principal

* PostgreSQL.

### Integrações

* Excel;
* e-mail;
* câmbio;
* APIs externas;
* ERP;
* outras integrações futuras.

## 5. Estrutura alvo

```text
Atlas---Cargo.Ops/
│
├── frontend/
│   └── src/
│       ├── app/
│       ├── components/
│       ├── modules/
│       ├── services/
│       ├── hooks/
│       └── types/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── integrations/
│   │   └── security/
│   └── tests/
│
├── database/
│   ├── migrations/
│   └── seeds/
│
├── docs/
│   ├── requirements/
│   ├── architecture/
│   ├── adr/
│   └── superpowers/specs/
│
├── legacy/
│   └── cargo-ops-prototype/
│
├── .gitignore
└── README.md
```

## 6. Módulos de domínio

### Identity

Responsável por:

* usuários;
* autenticação;
* perfis;
* permissões;
* sessões.

### Organization

Responsável por:

* empresas;
* lojas;
* centros de distribuição;
* depósitos;
* unidades administrativas;
* acesso do usuário por unidade.

### Inventory

Responsável por:

* produtos;
* SKUs;
* estoques;
* saldos;
* reservas;
* movimentações;
* transferências;
* cobertura;
* excesso;
* ruptura.

### Procurement

Responsável por:

* compras nacionais;
* compras internacionais;
* compradores responsáveis;
* sugestão de compra;
* fornecedores;
* RFQs;
* propostas;
* pedidos;
* aprovações.

### Imports / COMEX

Responsável por:

* processos;
* proformas;
* bookings;
* containers;
* navios;
* portos;
* ETD;
* ETA;
* parametrização;
* desembaraço;
* documentos;
* inspeções;
* Free Time;
* Time Left;
* demurrage;
* entrega;
* devolução do container.

### Finance

Responsável por:

* adiantamentos;
* saldos;
* numerário;
* câmbio;
* pagamentos;
* custos de importação.

### Data Hub

Responsável por:

* arquivos Excel;
* mapeamento de colunas;
* validação;
* preview;
* importação;
* sincronizações;
* divergências;
* histórico.

### Reporting

Responsável por:

* relatórios operacionais;
* indicadores;
* Dashboard operacional;
* Dashboard executivo.

### Operations

Responsável por:

* agenda;
* pendências;
* alertas;
* notificações;
* ações entre setores.

### Audit

Responsável por:

* trilha de auditoria;
* alterações críticas;
* histórico;
* usuário responsável;
* valor anterior;
* valor posterior.

## 7. Modelo de acesso

Perfis principais:

* DIRETORIA;
* COORDENACAO;
* SUPERVISAO;
* COMPRADOR;
* FINANCEIRO;
* LOJA;
* CENTRO_DISTRIBUICAO;
* ADMIN.

O perfil `COMPRADOR` possuirá adicionalmente um escopo:

* NATIONAL;
* INTERNATIONAL;
* BOTH.

O escopo de compra **não limitará a visualização do estoque corporativo**.

Compradores Nacional e Internacional deverão consultar o estoque global para tomar decisões de compra.

O escopo limitará as operações de aquisição sob responsabilidade do usuário.

Produtos, categorias, famílias ou linhas poderão possuir compradores responsáveis.

## 8. Hierarquia operacional

A estrutura principal será:

```text
DIRETORIA
    │
COORDENACAO
    │
SUPERVISAO
    │
    ├── COMPRADOR NACIONAL
    │
    └── COMPRADOR INTERNACIONAL
```

O Financeiro será uma área especializada integrada aos processos necessários.

Lojas e Centros de Distribuição terão usuários e permissões próprios, associados às respectivas unidades operacionais.

## 9. Unidades organizacionais

Loja, Centro de Distribuição e Depósito não serão tratados apenas como perfis de usuário.

Serão entidades da estrutura organizacional da empresa.

Tipos iniciais:

* STORE;
* DISTRIBUTION_CENTER;
* WAREHOUSE;
* OFFICE.

Usuários poderão receber acesso a uma ou várias unidades.

O estoque deverá sempre estar associado a uma unidade operacional.

## 10. Diretoria

A Diretoria possuirá uma experiência própria.

Seu Dashboard Executivo deverá apresentar informações consolidadas e orientadas à decisão, evitando excesso de informação operacional.

Indicadores previstos:

* estoque total;
* excesso de estoque;
* risco de ruptura;
* cobertura;
* compras nacionais;
* compras internacionais;
* containers;
* exposição financeira;
* custos;
* câmbio;
* riscos;
* savings;
* aprovações relevantes.

Indicadores poderão possuir drill-down quando autorizado.

## 11. Princípio de decisão de compra

A sugestão de compra não deverá analisar apenas estoque mínimo.

O modelo deverá evoluir considerando:

* estoque físico;
* estoque reservado;
* estoque disponível;
* estoque em outras unidades;
* vendas;
* consumo;
* cobertura;
* estoque de segurança;
* pedidos existentes;
* mercadoria em trânsito;
* lead time;
* origem nacional ou internacional;
* demanda prevista.

Antes de recomendar uma nova compra, o Atlas deverá verificar se uma transferência interna pode atender à necessidade.

Fluxo conceitual:

```text
Necessidade identificada
        │
        ▼
Existe estoque em outra unidade?
        │
   ┌────┴────┐
  SIM       NÃO
   │          │
   ▼          ▼
Transferir   Existe pedido em trânsito?
                  │
             ┌────┴────┐
            SIM       NÃO
             │          │
             ▼          ▼
      Avaliar chegada   Sugerir compra
```

## 12. Estoque corporativo

O estoque será corporativo e organizado por unidade.

Um produto poderá possuir estoque simultaneamente em:

* lojas;
* centros de distribuição;
* depósitos.

O Atlas deverá permitir visualização:

* por produto;
* por unidade;
* por região;
* consolidada da empresa.

Compradores Nacional e Internacional terão acesso à visão corporativa necessária para decisão de compra.

## 13. Evolução contínua

Novos requisitos operacionais deverão preferencialmente ser adicionados ao módulo de domínio correspondente.

Regras específicas não deverão ser espalhadas pelo sistema.

Validações feitas por usuários-chave deverão gerar requisitos rastreáveis antes da implementação.

Mudanças relevantes de arquitetura deverão ser registradas em ADRs — Architecture Decision Records.

A arquitetura deverá permitir inclusão de novas regras de negócio sem exigir reconstrução do sistema.

## 14. Isolamento

Atlas e Site HiGamer serão projetos independentes.

Cada sistema possuirá:

* ambiente;
* dependências;
* arquivos `.env`;
* banco de dados;
* portas;
* versionamento;
* processo de implantação próprios.

Nenhuma atualização do Atlas deverá exigir atualização do Site HiGamer.

## 15. Segurança

Arquivos contendo segredos nunca deverão ser versionados.

O backend será responsável pela autorização final das operações.

Ocultar uma opção no frontend não será considerado mecanismo de segurança.

Operações críticas deverão gerar auditoria.

Credenciais deverão ser fornecidas através de variáveis de ambiente ou mecanismos equivalentes.

## 16. Fora do escopo da fundação inicial

Não implementar nesta etapa:

* microserviços;
* Kubernetes;
* Redis sem necessidade comprovada;
* inteligência artificial;
* machine learning;
* substituição completa de ERP;
* integrações fiscais complexas;
* automações não validadas pelo negócio.

Esses itens poderão ser avaliados posteriormente.

## 17. Critérios de sucesso da fundação

A fundação será considerada adequada quando:

1. Frontend e backend forem independentes.
2. O protótipo Cargo.Ops permanecer preservado.
3. Os módulos de negócio possuírem limites claros.
4. Usuários, perfis e unidades forem conceitos separados.
5. Compras Nacional e Internacional forem diferenciadas.
6. Estoque for corporativo e organizado por unidade.
7. Banco transacional utilizar PostgreSQL.
8. Integrações forem isoladas das regras de negócio.
9. Alterações críticas forem auditáveis.
10. Novos requisitos puderem ser incorporados sem reestruturar toda a aplicação.
11. Atlas e Site HiGamer permanecerem tecnicamente isolados.

## 18. Princípio do produto

O Atlas deverá evoluir em três níveis:

### INFORMAÇÃO

O que está acontecendo?

### ALERTA

O que necessita de atenção?

### INTELIGÊNCIA

Qual ação deve ser considerada?

A prioridade do produto será reduzir esforço operacional e aumentar a qualidade da decisão.
