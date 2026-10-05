# HiAtlas — sanity após implantação autorizada

Este checklist é somente leitura no domínio. Login/logout e seleção/encerramento de contexto geram os eventos técnicos normais. Usar uma identidade real autorizada, nunca credencial padrão, e parar diante de qualquer falha. Não executar correções, resets, convites ou alterações de configuração.

1. Consultar /api/health/live e /api/health/ready:200 e status ok, sem dados internos; registrar request_id de falha.
2. Abrir origem HTTPS oficial e efetuar login Admin. Verificar cookie Secure/HttpOnly/SameSite/host prefix sem copiar seus valores.
3. Selecionar contrato previamente autorizado; confirmar empresa/contrato/ambiente permanentemente visíveis.
4. Consultar Usuários, Perfis e Permissões, Estrutura, Módulos e Auditoria: resultados contextuais, paginação, ausência de dados de outros contratos.
5. Confirmar que módulos operacionais indisponíveis não exibem dados demonstrativos nem recebem acesso apenas pela contratação.
6. Consultar Manutenção: na configuração normal, nenhum handler operacional registrado. Não habilitar factory fixture.
7. Verificar tema claro/escuro, foco e teclado, reload com revalidação e ausência de dados persistentes de usuários/auditoria no storage.
8. Fazer logout, confirmar retorno ao login e rejeição da sessão anterior pelo servidor. Nunca registrar cookie, senha ou token como evidência.

O gate de desenvolvimento usa Chrome headless com PostgreSQL descartável e transporte de email falso. Isso não substitui a execução deste sanity na infraestrutura aprovada após um deploy posteriormente autorizado.
## Headers do HTML e dos assets

Verificar na origem HTTPS publicada, além dos endpoints API: Referrer-Policy:no-referrer; X-Content-Type-Options:nosniff; X-Frame-Options:DENY; Content-Security-Policy com frame-ancestors 'none', scripts/conexões somente da própria origem e política compatível com o build real. HSTS somente na implantação de produção HTTPS explicitamente configurada. Abrir DevTools sem copiar cookies/tokens, confirmar ausência de violações CSP durante login/seleção/listagens/logout e verificar que nenhuma navegação carrega recursos externos. A configuração de headers da API não cobre automaticamente HTML servido por outro reverse proxy.
