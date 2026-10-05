# HiAtlas Platform Foundation v1

STATUS: VALIDATED

Fases 1–10 aprovadas; Fase 11 implementada e validada tecnicamente, entregue para revisão. Este status descreve a fundação de identidade, segurança, multi-tenancy, administração, suporte, organização, auditoria e manutenção; não a entrega de todos os módulos do HiAtlas.

## Fundação entregue

Identidade global com Argon2id, sessões persistentes revogáveis, CSRF e cookies HTTPS; tenants/contratos, memberships independentes e TenantRoles separados dos papéis internos; AccessContext por aba com autorização atualizada no servidor; convites e recuperação com tokens de uso único e outbox protegida; Administração contextual de usuários/perfis/auditoria; Suporte limitado ao contrato; OrganizationNode hierárquico incluindo WORKSITE; catálogo e contratação de módulos; atendimento READ_ONLY mantendo operador real; concessões temporárias Financeiro/Fiscal e MAINTENANCE com reautenticação; registry fechado de correções/reprocessamentos, ProcessingRun e diagnósticos sanitizados; auditoria transacional imutável para runtime.

A Fase 11 acrescenta recuperação administrativa offline, configuração de produção que falha fechada, health checks, runbooks, regressão integrada e prova de backup/restore. Resultados efetivamente executados estão em [phase-11](../superpowers/validation/hiatlas-platform/phase-11.md).

## Limites funcionais

PROCUREMENT, COMEX, INVENTORY, FINANCE, PROJECTS e DATAHUB existem no catálogo/configuração. Seus domínios operacionais reais não estão entregues: operational_available permanece false. Configurar um módulo não concede acesso aos dados; FINANCE exige ainda capability, concessão válida e política do domínio.

WORKSITE é unidade física, não Project/Obra. Não existem cronograma/orçamento de obra, cálculo fiscal, financeiro operacional, importadores/conectores reais, executor SQL/script, edição genérica de banco, MFA, Administrador do Cliente, help desk integrado ou dupla aprovação.

O registry da aplicação normal continua vazio: nenhum handler operacional real registrado. Handler controlado existe apenas em fixture/factory de testes atestados para comprovar infraestrutura; não é funcionalidade comercial. O protótipo demonstrativo de desenvolvimento permanece separado do caminho autenticado e do bundle normal.

## Dependências operacionais

PostgreSQL com owner/runtime separados, identidade de recuperação isolada e controlada por infraestrutura, origem única HTTPS/reverse proxy, chaves externas protegidas, SMTP explicitamente habilitado ou delivery indisponível, worker/outbox executado separadamente, backups protegidos e ensaio de restore. Deploy, distribuição de credenciais e retenção exigem decisão operacional; não existe SLA contratado nesta entrega.

## Riscos e próximos blocos

Não houve deploy ou validação de infraestrutura de produção. SMTP real não é alegado por testes com FakeEmailTransport. Chrome headless é o navegador do gate; multibrowser e auditoria WCAG completa permanecem recomendados antes da implantação comercial. Downgrade em banco descartável prova mecanismo técnico, não rollback seguro de produção.

O próximo estágio depende de revisão desta fundação e autorização posterior: ambiente demo isolado, implantação operacional e domínios reais com serviços/handlers próprios. Nenhum deles é iniciado automaticamente pela Fase 11.
## Inventário travado e revisão de dependências

Inventário do ambiente utilizado na Fase 11: Python 3.13.15, FastAPI 0.141.1, SQLAlchemy 2.0.52, Alembic 1.19.1, PostgreSQL 18.6, Node 22.23.2, React 19.2.8, TypeScript 6.0.3, Vite 8.2.2, Vitest 4.1.11, oxlint 1.80.0, Starlette 1.6.0, httpx 0.28.1, psycopg 3.3.4. Lockfiles continuam sendo a autoridade; faixas dos manifests não são versões efetivamente usadas.

A revisão usou pip-audit sobre o ambiente Python instalado e npm audit completo. Foram comprovados três advisories em urllib3 2.7.0 (dependência transitiva do CLI FastAPI) e advisories em undici 8.10.0 (dependência de desenvolvimento jsdom). Corrigiram-se apenas urllib3 para 2.8.0 e undici para 8.10.2; não houve atualização geral. Fontes primárias: [urllib3 TLS proxy](https://github.com/urllib3/urllib3/security/advisories/GHSA-8988-9cw3-xx77), [urllib3 Deflate](https://github.com/urllib3/urllib3/security/advisories/GHSA-gh4c-6fx4-qh6g), [urllib3 chunk-size](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw), [undici WebSocket](https://github.com/nodejs/undici/security/advisories/GHSA-rfgv-xxqx-mfg5), [undici TLS](https://github.com/nodejs/undici/security/advisories/GHSA-w293-vg96-wgc3).

A auditoria não prova ausência de vulnerabilidades desconhecidas. O warning herdado FastAPI/Starlette de integração TestClient com httpx é depreciação conhecida e continua documentado; não equivale a teste funcional falho. Nenhum observability SaaS foi adicionado ao runtime.
