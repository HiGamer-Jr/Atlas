# Fase11 — ensaio browser operacional integrado

Data:2026-10-05. Chrome headless real, FastAPI real, React/Vite e bundle de produção reais, PostgreSQL18.6 real. **8/8 rodadas PASS; zero rodadas FAIL na execução funcional; 78 capturas PNG novas.** Transporte é FakeEmailTransport controlado, sem SMTP externo. Nenhum deploy ou handler de produção foi criado.

Banco exclusivo: hiatlas_phase11_e2e_test, marcador hiatlas-disposable-test-db, revision0010; owner phase11_e2e_owner e runtime phase11_e2e_runtime distintos dos roles/banco do pytest. Ambos não superuser, sem CREATEDB/CREATEROLE/BYPASSRLS. Instância portátil em127.0.0.1:55491. API normal127.0.0.1:8011; frontend HTTPSlocalhost:5181. Build usa FastAPI HTTPS5181 diretamente, sem Vite. Certificado temporário SANlocalhost/127.0.0.1, Chrome ignoreHTTPSErrors somente para esse certificado local. Python3.13.15, Node22.23.2, npm10.9.8; Playwright instalado somente em TEMP separado. Senhas/chaveoutbox/URLs ficam em arquivo externo com ACL restrita, nunca neste relatório.

## Rodadas observadas

| Rodada/flags | Resultado | PNG | Verificação real |
|---|---|---:|---|
|05 normal|PASS|12|Recuperação neutra; reset consumido; login com nova senha; sessão/contexto antigos negados; convite aceito e login do convidado; replay/expiração negados; email indisponível; token ausente de URL/storage/UI; claro/escuro/mobile/teclado; zero pageerror|
|06 normal|PASS|12|Admin usuários/convite/aceitação/papel/bloqueio/perfil/auditoria; Suporte criar/reenviar/reset/papel elegível e negação sensível403; histórico sanitizado; A/A2/B; contexto/storage/layout/teclado|
|07 normal|PASS|12|Hierarquia/criar/editar/inativar/ciclo/rejeiçãoPROJECT; módulos contratados/ativos/conflito/auditoria; Suporte somente leitura e403 manual; nós/parents/módulos/auditoria A/A2/B|
|08 normal|PASS|12|Admin/Suporte READ_ONLY com operador real e autenticação preservada; mutações diretas child/parent/semcontexto negadas; reload/abas independentes/bindingHTTP/A/A2/B/end/history/expiry; workspace indisponível verdadeiro; banner persistente|
|09 normal|PASS|12|Admin/Suporte grants temporários; bindingHTTP/contrato; reauth; lifecycle; módulos/manutenção indisponíveis reais; themes/mobile/teclado/storage|
|10 normal|PASS|4|Registry de manutenção realmente vazio; Admin/Suporte reais; negações; claro/escuro/mobile/teclado/storage|
|10 controlled|PASS|10|Correção/preview/confirmação/conflito/reprocess/idempotência/auditoria/scopes reais; Admin/Suporte; A/A2/B; temas/mobile/teclado/storage; handler exclusivamente no factory controlado|
|10 normal -Build|PASS|4|Bundle /assets de produção carregado sob CSP real; cabeçalhos exatos HTML/assets; login/Admin/Suporte normal com registry vazio; zero violaçõesCSP/pageerror e sem markerFIXTURE_NODE_RENAME|

Saídas finais PASS de cada harness foram observadas com exit0. Build observou adicionalmente PASS de frontend/e2e/phase11-build.mjs antes do harness10normal. São rodadas integradas de browser, não contagens de casos unitários pytest/vitest.

## HTML/assets e build de produção

Chrome validou Content-Security-Policy exata: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'. Referrer-Policy:no-referrer, X-Content-Type-Options:nosniff, X-Frame-Options:DENY e Strict-Transport-Security:max-age=31536000. Scripts efetivamente carregados vieram de /assets/*.js, sem handlerfixture; houve zero securitypolicyviolation/pageerror. Factory está em scripts/phase11_browser_fixture.py exclusivamente de teste, servindo frontend/dist por GET sob os middlewares; nenhuma rota estática foi adicionada a app.main. O teste usa código frontend compilado de produção com Settings de teste e transporte fake, não a infraestrutura de deploy de produção.

## Guard do runner — RED/GREEN sem mutação

Revisão detectou que o runner poderia aceitar o banco fonte marcado _test e sua limpeza. Antes da correção, executar helper --validate-env com configuração fonte retornouexit0: RED observado, **sem invocar clean**. Corrigido por validate_e2e_environment: parser SQLAlchemy exige banco hiatlas_phase11_e2e_test, owner/runtime phase11_e2e_owner/phase11_e2e_runtime, endpoint127.0.0.1:55491, origem/publicorigin HTTPSlocalhost:5181, APItarget127.0.0.1:8011 e reset1. Diagnósticos nunca imprimem URLs/credenciais.

GREEN observado: configuração fonte recusadaexit1 e dedicadaE2E aceitaexit0, ambos somente validação pura sem tocar banco. Runner chama o guard antes de clean; clean ainda usa attestation do harness no PostgreSQL real. Banco/roles do PIDmanifest vêm do resultado validado. Factory/helper de senha também aplicam guard dedicado. As duas últimas rodadas (controlled eBuild) executaram o runner corrigido. As seis primeiras já usavam o banco/roles exclusivos corretos; o achado era proteção contra seleção acidental futura, não isolamento incorreto dessas rodadas.

## Reprodução e artefatos

Na raiz da worktree, com arquivo de ambiente protegido externo da base exclusiva e as ferramentas já instaladas:

```powershell
.\scripts\phase11_browser_checks.ps1 -EnvironmentFile <env-e2e.ps1-protegido> -Phase 05 -Mode normal
# Repetir sequencialmente Phase06/07/08/09/10 com Mode normal.
.\scripts\phase11_browser_checks.ps1 -EnvironmentFile <env-e2e.ps1-protegido> -Phase 10 -Mode controlled
.\scripts\phase11_browser_checks.ps1 -EnvironmentFile <env-e2e.ps1-protegido> -Phase 10 -Mode normal -Build
```

Cada rodada cria cópia TEMP do harness versionado05–10 alterando **somente sua linha de output**, para docs/superpowers/validation/hiatlas-platform/phase-11-visual/phase-NN-MODE. Capturas aprovadas das fases05–10 foram preservadas; git status desses diretórios anteriores ficou vazio. Senha aleatória é instalada apenas no seed de banco dedicado atestado com flagHIATLAS_PHASE11_E2E=1; não existe sitecustomize versionado ou mudança de comportamento de produção.

Amostras inspecionadas: convite mobile05 e suporte READ_ONLY mobile08, ambos legíveis sem clipping; estados claros/escuros/mobile também foram verificados pelos harnesses. Capturas adicionais10controlled/build preservadas para revisão.

Runner usa Start-Process Hidden, sem serviços globais, e desativa access log ASGI; logs privados somente TEMP. Encerra somente processos API/Vite que criou via PID e finally. Após a oitava rodada, listeners8011/5181 ausentes; PostgreSQL permaneceu ativo para o gate fonte do coordenador. PIDmanifest inclui clusterPG e último API7520 encerrado, nenhum Vite em modoBuild, banco/rolesE2E validados. Cleanup de cluster/TEMP só ocorrerá após autorização do coordenador e verificação de contenção dos caminhos e ausência de ReparsePoint. Nenhum cleanup/deploy/commit automático foi realizado.

Ruff dos quatro scripts Python validado no cwdbackend após correção de imports; parser PowerShell e node --check aprovados; git diff --check sem erro nos artefatos desta entrega.
