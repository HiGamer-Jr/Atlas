# HiAtlas Data Hub — Excel v1

Conector XLSX para registros informacionais próprios; não executa Compras/COMEX/Estoque/Financeiro. Template, Dataset e Perfil são conceitos distintos. Nome do perfil nunca autoriza dados; Admin interno precisa membership/capabilities tenant e unidades, Support não importa. Financeiro bloqueado nesta versão.

## Configuração

Feature DATAHUB_ENABLED desligada por padrão. Ativação requer módulo DATAHUB contratado/ativo, permissões de dataset, DATAHUB_RAW_ROOT privado absoluto e DATAHUB_RAW_KEY Fernet dedicada, separada da outbox. Distribuir logo oficial existente e indicar DATAHUB_LOGO_PATH quando backend separado do frontend. Não publicar diretório bruto via web/reverse proxy.

Linux: diretório0700/arquivos0600 e conta dedicada. Windows: aplicar ACL privada à identidade do serviço e administradores de infraestrutura; mode POSIX não substitui ACL. Excluir bruto/logs/chaves de assets, Git e backups sem proteção. Chave em secret store operacional, nunca argv, log ou documentação.

DATAHUB_LIMITS__RAW_SECONDS padrão86400; PREVIEW_SECONDS1800; ORPHAN_GRACE_SECONDS3600. Limites de tamanho/ZIP/XML/linhas/células/exportação são configuráveis via os mesmos Settings. Parsing síncrono limitado, sem executor arbitrário. Preview precisa confirmação explícita; duplicatas idênticas SKIP, conteúdo diferente rejeita409/nova revisão, sem overwrite.

## Retenção

Executar localmente com ambiente do runtime: uv run --frozen python -m app.datahub.cleanup --limit 100. Agendamento é decisão operacional, não criado automaticamente. Resultado contém somente contagens. Runtime deve passar validação física (não owner/superuser). Nenhuma tabela é apagada.

Bruto cifrado tem retenção temporária independente; Rows/Issues/Records/digest/proveniência permanecem. Remover arquivo expirado não impede confirmar preview ainda vigente. Falha de remoção permanece elegível para retry. Rollback após remoção pode deixar referência a arquivo ausente; próxima execução reconciliará sem perda de evidência normalizada. Preview RECEIVED/VALIDATING/READY abandonado expira e gera auditoria atômica; falha de auditoria reverte estado. Evento explicita expiração automática do lifecycle original.

Órfãos são apenas arquivos regulares UUID.enc dentro da raiz validada e após margem; symlinks/junctions rejeitados. Limite controla entradas examinadas e itens por categoria; diretórios grandes exigem acompanhamento da reconciliação. Não remover diretório ou executar limpeza genérica de filesystem. Backup de evidência normalizada segue runbook PostgreSQL da Foundation; bruto/chave precisam retenção e proteção próprias. Restore nunca transforma estado terminal em confirmável.

## Consulta e exportação

Histórico paginado reavalia permissões/módulos/unidades. Import com qualquer dataset/unidade não autorizado é oculto integralmente, inclusive contagens/Issues. Confirmação vinculada à sessão/contexto originais; histórico pode ser lido por novo contexto autorizado. Exportação projeta apenas campos schema tipados e códigos atuais das unidades autorizadas, com limite explícito, sem truncamento silencioso. Células textuais literais evitam formula injection; parsing não calcula fórmulas. Sem download de bruto.

CSV, mapeamento externo, APIs, ERP e adaptadores de domínio são evoluções futuras; não implementados nesta versão.
