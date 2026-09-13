# HiAtlas Horizon Dashboard v1 — validação técnica

Data: 2026-09-13
Branch: feat/hiatlas-international-buyer-copilot
Plano executado: D:/Projeto HiAtlas/2026-09-13-hiatlas-horizon-dashboard-v1.md

## Escopo entregue

- Comprador Internacional usa INTERNATIONAL; Comprador Nacional usa NATIONAL.
- Um único HorizonDashboard, com indicadores e sinais demonstrativos por perfil.
- Quatro cards filtram a Central; segundo clique e Limpar filtro restauram os itens.
- Hoje, próximos 1–7 dias e horizonte 7–30 dias, com impacto, próxima ação e duas evidências por sinal.
- Empresa/unidade filtram os sinais e limpam a seleção anterior. Outros contextos sem fixtures mostram ausência de dados.
- Temas, navegação, permissões e detalhes operacionais existentes preservados.
- Nenhum backend, LLM ou integração externa introduzido.

## Ciclos TDD registrados

| Ciclo | RED observado antes da implementação | GREEN |
| --- | --- | --- |
| Cenários por perfil | 2 falhas: Free Time/container e carga Bauru ausentes | 9 testes Workspace |
| Cards e filtros | 1 falha: botão Exigem atenção ausente | 10 testes Workspace |
| Janelas e evidências | 2 falhas: janela Hoje ausente nos dois perfis | 12 testes Workspace |
| Indicadores/contexto | 3 falhas: indicadores e região contextual ausentes | 18 testes na suíte completa |
| Acessibilidade/tema | 1 falha: aria-controls ausente | 20 testes na suíte completa |
| Mobile real | Asserção esperava 1 coluna em 390px, encontrou 2 | 1 coluna em 390px; 2 em 768px; 4 em 1440px |

Comando focal: `npm test -- Workspace.test.tsx --maxWorkers=1 --pool=threads`.
Comando completo durante os ciclos: `npm test -- --maxWorkers=1 --pool=threads`.

O caso mobile foi executado no navegador real com o HiAtlas servido em localhost:5174.
A regra de Workspace.css carregada depois de HorizonDashboard.css sobrescrevia o breakpoint; o seletor agora é limitado por .horizon-dashboard.
Asserção usada antes e depois da correção, com viewport de 390 × 844:

```js
const columns = await tab.playwright.evaluate(() =>
  getComputedStyle(document.querySelector('.horizon-summary'))
    .gridTemplateColumns.split(' ').length
)
if (columns !== 1) throw new Error(`Esperado 1 coluna; encontrado ${columns}`)
```

## Verificação no navegador

- Internacional: container MSCU1234567, Free Time, evidências e seleção por Enter confirmados.
- Nacional: carga NAC-2026-01842 em trânsito, família Aço, perfis/juntas/cantoneiras, cobertura 3 dias versus ETA 5 dias confirmados.
- Claro e escuro inspecionados visualmente; seleção continua ativa ao trocar tema.
- Desktop 1440px, tablet 768px e celular 390px inspecionados. Sem overflow horizontal em 390px.
- Troca para Horizonte Industrial remove os sinais de Aurora e apresenta estado sem dados nos indicadores.
- Revisão independente de código: nenhum defeito importante identificado.

## Decisões de execução

- A etapa 1 do plano permitia avançar com testes UI vermelhos. A integração mínima foi antecipada para encerrar cada ciclo em verde, conforme a instrução explícita do usuário.
- A especificação citada pelo plano não foi encontrada no repositório nem na pasta do plano. A implementação segue os requisitos detalhados do próprio plano.
- Os cenários são de compras da Matriz de Aurora Distribuição; Bauru é o destino operacional da carga nacional. As opções existentes de empresa/unidade foram preservadas.
- As constantes dos filtros foram separadas em summaryFilters.ts para manter Fast Refresh sem avisos de lint.

## Checkpoint humano

Validação técnica concluída; validação de produto e feedback da Dayana ainda pendentes.
Abrir http://localhost:5174, expandir Opções de demonstração, selecionar um dos dois perfis compradores e entrar.
Usar Aurora Distribuição / Todas as unidades (ou Matriz) para os cenários principais.
Feedback futuro deve ser registrado como mudança delimitada, conforme a tarefa 6 do plano.
