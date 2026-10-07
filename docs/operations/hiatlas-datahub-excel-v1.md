# HiAtlas Data Hub — Excel v1

Conector XLSX para registros informacionais próprios; não executa Compras/COMEX/Estoque/Financeiro. Template, Dataset e Perfil são conceitos distintos. Nome do perfil nunca autoriza dados; Admin interno precisa membership/capabilities tenant e unidades, Support não importa. Financeiro bloqueado nesta versão.

## Configuração

Feature DATAHUB_ENABLED desligada por padrão. Ativação requer módulo DATAHUB contratado/ativo, permissões de dataset, DATAHUB_RAW_ROOT privado absoluto e DATAHUB_RAW_KEY Fernet dedicada, separada da outbox. Distribuir logo oficial existente e indicar DATAHUB_LOGO_PATH quando backend separado do frontend. Não publicar diretório bruto via web/reverse proxy.

Linux: diretório0700/arquivos0600 e conta dedicada. Windows: aplicar ACL privada à identidade do serviço e administradores de infraestrutura; mode POSIX não substitui ACL. Excluir bruto/logs/chaves de assets, Git e backups sem proteção. Chave em secret store operacional, nunca argv, log ou documentação.

DATAHUB_LIMITS__RAW_SECONDS padrão86400; PREVIEW_SECONDS1800; ORPHAN_GRACE_SECONDS3600. Limites de tamanho/ZIP/XML/linhas/células/exportação são configuráveis via os mesmos Settings. Parsing síncrono limitado, sem executor arbitrário. Preview precisa confirmação explícita. Qualquer business key repetida dentro do arquivo é ERROR, mesmo com conteúdo idêntico. Contra registros já persistidos: conteúdo idêntico é SKIP/warning; conteúdo diferente é ERROR no preview ou409 se mudou depois, exigindo nova revisão e sem overwrite.

## Retenção

Executar localmente com ambiente do runtime: uv run --frozen python -m app.datahub.cleanup --limit 100. Agendamento é decisão operacional, não criado automaticamente. Resultado contém somente contagens. Runtime deve passar validação física (não owner/superuser). Nenhuma tabela é apagada.

Bruto cifrado tem retenção temporária independente; Rows/Issues/Records/digest/proveniência permanecem. Remover arquivo expirado não impede confirmar preview ainda vigente. Falha de remoção permanece elegível para retry. Rollback após remoção pode deixar referência a arquivo ausente; próxima execução reconciliará sem perda de evidência normalizada. Preview RECEIVED/VALIDATING/READY abandonado expira e gera auditoria atômica; falha de auditoria reverte estado. Evento explicita expiração automática do lifecycle original.

Órfãos são apenas arquivos regulares UUID.enc dentro da raiz validada e após margem; symlinks/junctions rejeitados. Cursor técnico privado avança entre execuções para não deixar órfãos posteriores sem exame. Nomes do diretório são enumerados; stat/consultas/remoções ficam limitados por lote/categoria. Diretórios grandes exigem acompanhamento da reconciliação. Não remover diretório ou executar limpeza genérica de filesystem. Backup de evidência normalizada segue runbook PostgreSQL da Foundation; bruto/chave precisam retenção e proteção próprias. Restore nunca transforma estado terminal em confirmável.

## Consulta e exportação

Histórico paginado reavalia permissões/módulos/unidades. Import com qualquer dataset/unidade não autorizado é oculto integralmente, inclusive contagens/Issues. Confirmação vinculada à sessão/contexto originais; histórico pode ser lido por novo contexto autorizado. Exportação projeta apenas campos schema tipados e códigos atuais das unidades autorizadas, com limite explícito, sem truncamento silencioso. Células textuais literais evitam formula injection; parsing não calcula fórmulas. Sem download de bruto.

CSV, mapeamento externo, APIs, ERP e adaptadores de domínio são evoluções futuras; não implementados nesta versão.

## Reproduzir validação local

Backend: uv run --frozen python -m pytest -q; uv run --frozen python -m ruff check app tests alembic. Harness exige PostgreSQL descartável real, marker hiatlas-disposable-test-db, owner/runtime distintos e não superuser, além de identidade recovery da Foundation. Configurar as variáveis do database/README.md fora de Git; não usar banco de cliente/Demo. Migrations executadas exclusivamente pelo owner.

Frontend: npm.cmd test; npm.cmd run lint; npm.cmd run build. Na raiz: git diff --check. E2E controlado Windows: scripts/datahub_browser_checks.ps1 -EnvironmentFile <arquivo privado>. A factory não é importada pela aplicação normal. Guard fixa checkout D:/Atlas, PostgreSQL loopback porta55493/base hiatlas_datahub_test e origem HTTPS local porta5188; API porta8018. Requer Chrome/Playwright e runtime Node disponíveis nesta máquina; os caminhos do harness precisam adaptação em outra estação. Não é harness de produção nem Demo.

Arquivo privado de ambiente deve definir TEST_DATABASE_OWNER_URL/TEST_DATABASE_RUNTIME_URL, HIATLAS_TEST_DATABASE_RESET, HIATLAS_DATAHUB_E2E, PUBLIC_ORIGIN, HIATLAS_E2E_STATE, HIATLAS_E2E_PASSWORD (aleatória sintética), HIATLAS_DATAHUB_KEY (Fernet dedicada), HIATLAS_TLS_CERT/HIATLAS_TLS_KEY, HIATLAS_API_TARGET, HIATLAS_PLAYWRIGHT_MODULE e VITE_ENABLE_DEMO=false. Não incluir valores/credenciais em evidências; aplicar ACL privada e remover arquivo/chaves/banco após teste. O harness recusa serviços já presentes nas suas portas; inicia ocultamente apenas API/Vite próprios, encerra esses processos e limpa as fixtures do banco atestado. PostgreSQL deve ser encerrado/removido pelo responsável pelo ambiente descartável. Jamais apontar para banco real.

Preview e confirmação mostram o template identificado do arquivo, independentemente do seletor usado para baixar outro modelo. Perfil exibido e nome do template são informativos; toda autoridade é do backend. O cliente guarda apenas estado transitório; somente id opaco do AccessContext e preferência de tema usam os storages existentes.
