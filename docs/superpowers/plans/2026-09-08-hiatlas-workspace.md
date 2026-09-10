# HiAtlas Workspace Implementation Plan
Goal: implementar o escopo aprovado em docs/superpowers/specs/2026-09-08-hiatlas-workspace.md.
Architecture: React modular, catálogo e registros separados da apresentação; contexto filtra todas as visões. Sem novas dependências.
1. Criar workspace/catalog.ts: módulos, perfis e registros representativos por página.
2. Criar testes de navegação, contexto, busca e persistência de tema. Executar antes da implementação.
3. Criar Workspace.tsx e Workspace.css: shell responsivo, dashboard, listas, detalhe acessível e filtros.
4. Integrar App.tsx ao login existente, preservando marca e selecionando todos os perfis solicitados.
5. Executar testes, lint e build. Conferir navegador em claro/escuro e móvel. Atualizar web/ com build validado sem remover arquivos existentes.
