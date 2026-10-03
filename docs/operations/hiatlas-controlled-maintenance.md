# HiAtlas — manutenção controlada (Fase 10)

Manutenção exige operador PLATFORM_ADMIN real, AuthSession e AccessContext válidos,
concessão MAINTENANCE vigente, ação/entidade exatamente autorizadas, capability,
módulo aplicável disponível e política de domínio. Financeiro/Fiscal e SupportSession
READ_ONLY não substituem essa autorização.

## Operações registradas

Registry é imutável após startup, com schemas concretos, resolvers contextuais,
projeções permitidas e handlers conhecidos no servidor. Nenhum fallback genérico.
A aplicação normal desta entrega registra zero handlers operacionais. A mensagem de
indisponibilidade é real; não existe edição por tabela/coluna/SQL/script/JSON Patch.

Fixtures podem registrar FIXTURE_NODE_RENAME somente no ambiente descartável atestado.
Esse handler verifica infraestrutura da fundação, sem simular módulo Compras, COMEX,
Estoque, Financeiro ou Obras. O entry frontend controlado é separado do bundle normal.

## Correção

O servidor valida o input pelo schema da ação e consulta a entidade do contexto.
Preview não modifica o domínio: devolve apenas Antes/Depois/efeitos permitidos e versão.
Um comprovante assinado vincula a revisão ao comando validado, operador, concessão,
contexto, entidade, estado atual e prazo. Não persistir esse comprovante no browser.

Confirmar exige nova consulta/lock e revalidação completa. Conflito de versão retorna
409 e requer novo preview; não há reaplicação silenciosa. Before e actor nunca vêm do
browser. O handler aplica regras do domínio e incrementa versão. Alteração e auditoria
compartilham commit; falha da auditoria impede sucesso e causa rollback.

## Reprocessamento e diagnóstico

Somente ProcessingRun conhecido, contextual e com handler elegível pode originar
reprocessamento. Chave de idempotência e fingerprint do comando são persistentes;
replay autorizado retorna o estado já existente sem executar novamente. Chave reutilizada
com comando diferente conflita. UNKNOWN não possui retry automático.

A infraestrutura inicial executa handlers transacionais controlados, sem queue universal
ou executor de payload arbitrário. Toda operação revalida concessão/contexto após espera
por locks. Diagnósticos utilizam códigos e projeções allowlisted, nunca stack trace, SQL,
segredo, ambiente, path interno ou payload bruto. Suporte recebe somente projeção reduzida
permitida; não pode abrir Manutenção nem iniciar correção/reprocessamento.

## Operação e limites

Migrações são exclusivas da identidade owner. Runtime não é owner/superuser e recebe
privilégios mínimos; auditoria permanece imutável. Dados de negócio não são apagados.
Concessões expiram/revogam sem renovação automática; o browser cancela requests e limpa
estado privilegiado, mas o servidor é sempre autoridade.

Sem deploy, migração de produção, merge ou Fase 11. Gates, revisões, RED/GREEN e riscos
concretos são registrados em docs/superpowers/validation/hiatlas-platform/phase-10.md.

### Garantias adicionais da Fase 10

O preview executa a projeção em SAVEPOINT e sempre faz rollback desse trecho, inclusive
se um callback tentar flush ou SQL de domínio. O comprovante HMAC vincula Antes,
Depois e efeitos apresentados ao comando/contexto/prazo; o apply recalcula tudo.
A chave do comprovante é efêmera por processo: reiniciar o servidor exige nova revisão.

A linhagem persistente impede uma nova intenção de reprocessamento quando existir
execução PENDING, RUNNING, SUCCEEDED ou UNKNOWN impeditiva. Replay autorizado com a
mesma chave é consultado antes desse bloqueio e não executa novamente. FAILED pode
ser repetido explicitamente conforme a elegibilidade definida pelo domínio. A UI
preserva a intenção em memória durante revalidação; reload não persiste comandos nem
chaves e depende dessa proteção do servidor.

Falha de handler transacional desfaz o efeito de domínio em SAVEPOINT e registra
ProcessingRun FAILED com código permitido e auditoria na transação externa. Falha
na auditoria desfaz também o registro da execução. Não há suporte nesta entrega a
efeitos externos não transacionais, retry automático ou executor universal.

O vínculo físico de entidade atualmente acompanha o escopo OrganizationNode da
fundação/Fase 9. Introduzir domínio operacional exige contrato, política, projeção,
formulário específico e migração de referências desse domínio; não basta registrar
uma string. Diagnósticos do Suporte exigem ação conhecida e explicitamente segura,
além da classificação armazenada, e excluem Financeiro/Fiscal.
