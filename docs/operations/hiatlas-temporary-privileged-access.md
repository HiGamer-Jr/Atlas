# HiAtlas — acesso privilegiado temporário (Fase 9)

Somente PLATFORM_ADMIN pode solicitar e utilizar concessões FINANCIAL_FISCAL ou MAINTENANCE.
A seleção de contrato e a configuração do módulo Financeiro não concedem leitura financeira.
PLATFORM_SUPPORT permanece excluído, inclusive em sessão de suporte READ_ONLY.

## Configuração e lifecycle

GRANT_SECONDS inicia em 1800. REAUTHENTICATION_SECONDS existente inicia em 300.
O prazo efetivo é o menor entre concessão, AuthSession (absoluto e idle) e contexto pai.
Tenant/contrato, identidade e papel interno continuam sendo revalidados no servidor.
Não há renovação por atividade, polling ou reload.

Reautenticação utiliza o endpoint de identidade existente; senha não integra a concessão.
Cada concessão pertence à sessão HTTP exata e ao contexto administrativo pai.
Seu contexto derivado conserva o operador real, tenant e contrato.
Somente o id opaco desse contexto pode persistir em sessionStorage por aba.
Contextos normais e outras abas não recebem privilégios implicitamente.

Encerramento confirmado invalida o contexto derivado e conserva a separação de eventos
ended/expired/revoked. Logout e revogação da sessão retiram acesso.
Mudanças de elegibilidade são verificadas após locks; a observação persiste estado
terminal e auditoria atomicamente. Não existe serviço externo ou renovador automático.

## Política financeira

A concessão prepara as capacidades excepcionais fechadas finance.read e fiscal.read.
Toda leitura futura deve declarar sua política segura e validar entidade contextual.
require_capability continua exigindo módulo contratado, ativo e operacionalmente disponível.
Concessão vigente é necessária e insuficiente; nenhuma rota financeira operacional foi criada.
Todos os módulos operacionais da fundação continuam indisponíveis.

## Manutenção

O registry de produção é vazio. A aplicação informa a indisponibilidade real.
Ações desconhecidas, código, SQL, tabela, coluna ou payload genérico não constituem autorização.
O escopo inicial é tipado, contextual e associado a ações registradas exclusivamente no servidor.
Autorização não executa correção nem reprocessamento e não libera mutações genéricas.
Handlers, outros tipos de entidade e operações reais exigem a Fase 10 e sua revisão própria.
Testes podem injetar registry e resolvers controlados, sem rota ou handler de teste em produção.

## Auditoria e operação

Criação e transição terminal compartilham transação com AuditEvent.
O ator é sempre o operador real. Escopo, motivo e referência usam schemas allowlisted.
Não registrar senha, cookie, tokens, credenciais, ciphertext ou conteúdo Financeiro/Fiscal.
Runtime recebe SELECT/INSERT/UPDATE nas tabelas técnicas novas, sem DELETE/TRUNCATE.
Migrações são executadas somente pela identidade owner.

A entrega não inclui deploy, migração de produção, merge, manutenção operacional ou concessão
ao Suporte. O relatório phase-09.md distingue verificações executadas de limitações.
