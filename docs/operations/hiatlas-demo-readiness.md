# HiAtlas — prontidão para demonstração

DEMO INTERNO ≠ PRODUÇÃO. Este documento prepara uma atividade posterior à aprovação da Fase11. Nenhum ambiente demo, domínio, serviço ou massa comercial é provisionado por esta entrega.

## Fronteiras obrigatórias

- Banco, owner/runtime, chaves de outbox, credenciais, origem HTTPS e domínio/subdomínio separados da produção.
- Tenant e contratos fictícios; somente dados sintéticos. Nenhuma empresa GDSUL real, informação de cliente, cópia de produção ou associação real de identidade.
- SMTP controlado: transporte falso em testes ou caixa autorizada restrita no ambiente demo. Nunca usar destinatário real por padrão.
- Aviso permanente DEMONSTRAÇÃO, incluindo páginas autenticadas e eventual ambiente comercial futuro.
- Credenciais sintéticas distribuídas por canal autorizado, sem senhas padrão no repositório.
- VITE_ENABLE_DEMO=false é padrão. O protótipo atual /demo depende de DEV + flag; builds normais eliminam essa entrada. Não usar fixtures de manutenção como operações comerciais.

## Checklist da próxima atividade

1. Aprovar separadamente o objetivo, público, hospedagem e responsáveis do demo.
2. Provisionar banco/origem/HTTPS e identidades de banco exclusivas com os mesmos limites de privilégio da fundação.
3. Definir catálogo e massa sintética claramente identificada; não alegar Compras/COMEX/Estoque/Financeiro/Obras operacionais por existir menu ou catálogo.
4. Definir delivery controlado, expiração/reset de dados e acesso dos demonstradores.
5. Validar isolamento contra qualquer ambiente real, cookies, CSRF, backups e logs sem segredos.
6. Executar sanity e inspeção light/dark, mobile e teclado no ambiente aprovado.
7. Publicar somente após autorização explícita; definir remoção do ambiente e proteção dos backups.

O demo não altera permissões de produção, não habilita handlers test-only na aplicação normal e não substitui os gates de implantação comercial.