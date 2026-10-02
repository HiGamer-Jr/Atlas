# HiAtlas — Atendimento somente leitura (Fase 8)

O atendimento mantém o operador autenticado como ator. O usuário do cliente é apenas
visualizado, pelo membership do contrato selecionado. Não há login, senha, cookie,
token ou sessão autenticada emitida para esse usuário.

## Iniciar e encerrar

No detalhe de um vínculo elegível, Administração e Suporte autorizados podem iniciar
sessão com motivo obrigatório e referência opcional. A confirmação identifica usuário,
empresa, contrato e perfil e declara somente leitura. O servidor cria uma SupportSession
persistente e um AccessContext derivado, ambos vinculados à sessão HTTP real do operador.

Durante o atendimento, a faixa distingue Operador e Usuário visualizado, informa
empresa/contrato/ambiente, perfil, tempo restante e encerramento. Ferramentas de gestão
ficam fora deste modo. Para bloquear acesso, trocar perfil, emitir convite ou reset,
encerrar primeiro a sessão e retornar ao portal normal.

Encerrar depende do commit real do servidor. Contexto derivado é invalidado e requests
pendentes/dados visualizados são descartados antes do retorno. O histórico permanece
somente no contrato selecionado, sem central multiempresa.

## Autorização

Principal nunca muda para o usuário visualizado. EffectiveAccess usa interseção das
permissões atuais desse vínculo, limites de leitura do operador, disponibilidade dos
módulos e restrições da sessão. Financeiro/Fiscal, capacidades sensíveis, gestão de
acessos, auditoria completa e configurações internas permanecem excluídos.

A política central falha fechada: rotas não declaradas seguras são negadas durante
atendimento. Verbo GET sozinho não é prova de segurança. POST/PATCH/PUT/DELETE de negócio
são negados tanto pelo contexto derivado como pelo contexto pai suspenso, inclusive
chamadas manuais. Ações estreitas de controle (encerrar, logout e CSRF do operador) não
concedem credenciais ou identidade ao usuário visualizado. Outro AccessContext realmente
independente continua isolado.

Não existe backend operacional de Compras/COMEX/Estoque/Obras/DataHub nesta fase. O
workspace usa somente projeções reais permitidas e informa indisponibilidade; não
utiliza demo ou páginas operacionais fictícias. O componente e EffectiveAccess são a
base para integrar futuramente o workspace comum, sem duplicar privilégios de suporte.

## Validade, reload e privacidade

Configure `SUPPORT_SESSION_SECONDS` entre 60 e 1800 segundos; padrão 1800 (30 minutos). A validade é limitada pela sessão principal e pelo
AccessContext. Estado de tenant/contrato/identidade/membership/perfil e permissões é
revalidado, inclusive após esperar locks. Sessão expirada, encerrada ou revogada não
pode ser restaurada nem retargetada. Trocar usuário/contrato exige novo atendimento.

Reload revalida autenticação, contexto e SupportSession no servidor antes de exibir o
ambiente. Apenas ids opacos de contexto/suporte podem permanecer no sessionStorage da
aba; motivos, histórico, permissões e dados de usuários não são autoridade persistida.
Duas abas/fluxos não compartilham a referência de atendimento. Nova sessão HTTP do mesmo
operador não pode reutilizar o atendimento antigo.

Auditoria captura operador real, papel, contexto e alvo, modo, motivo/referência
normalizados, horário e request_id. Transições e eventos compartilham commit; falha de
auditoria impede alteração. Projeções do servidor excluem credenciais, segredos e dados
operacionais sensíveis. Histórico não devolve identificadores de contexto derivado.

## Limites

Somente READ_ONLY. Não existem manutenção, escrita, impersonação, concessão financeira,
correções/reprocessamento, help desk integrado ou gravação de sessão. Testes usam banco
PostgreSQL descartável atestado, owner/runtime separados e FakeEmailTransport, sem
SMTP real. Resultados executados, revisão e capturas estão consolidados em
[phase-08.md](../superpowers/validation/hiatlas-platform/phase-08.md).
