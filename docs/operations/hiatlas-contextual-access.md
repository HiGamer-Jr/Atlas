# HiAtlas — Gestão contextual de acessos (Fase 6)

A gestão disponível aos operadores internos usa um AccessContext vigente e explícito.
Empresa, contrato e ambiente ficam visíveis durante listagens, detalhes e confirmações.
O backend revalida sessão, contexto, capacidade e estado após os locks, antes da mutação.

## Capacidades

Os nomes são os do catálogo existente. Nenhum perfil de Administrador do Cliente foi criado.

| Operação | Capability |
|---|---|
| Ler usuários/vínculos | memberships.read |
| Criar vínculo e solicitação de convite | users.create |
| Reemitir convite | users.invite |
| Iniciar redefinição | users.password_reset |
| Ativar/inativar/bloquear/desbloquear | users.status |
| Ler perfis elegíveis | roles.read |
| Associar TenantRole | roles.assign |
| Criar/editar perfil | roles.manage |
| Alterar elegibilidade ao suporte | roles.support_assignable.manage |
| Consultar auditoria contextual | audit.read |
| Consultar histórico de acesso contextual | logs.access.read |

Suporte recebe somente capacidades de atendimento e perfis elegíveis. Criar/editar
TenantRole e alterar support_assignable são exclusivos da Administração HiAtlas.
A interface usa capabilities do contexto e allowed_actions do vínculo. Isso representa
as decisões do servidor e não substitui sua validação nas chamadas diretas.

## Identidade e vínculo

Nome/e-mail são identificação global mínima. Perfil, active, blocked e situação de
convite pertencem ao vínculo do contrato atual. Os outros vínculos não são consultados
pela UI. Inativação e bloqueio são independentes; cada confirmação explicita a flag
alterada e a consequência conhecida. Não há exclusão definitiva de usuário, perfil
ou auditoria.

Convite e recuperação mantêm os tokens/outbox da Fase 5. O operador nunca estabelece
senha para o destinatário, recebe token ou link secreto. Uma solicitação accepted é
exibida como solicitação registrada; a situação de entrega vem da projeção persistida.
A ausência de SMTP não é apresentada como e-mail enviado.

## Perfis e concorrência

Perfis usam capacidades do catálogo tenant, descrição e versão. support_assignable
começa false. Sensibilidade histórica não é removida por renomear/remover capacidade.
Suporte só pode selecionar itens fornecidos pelo endpoint assignable; a atribuição
reavalia estado, classificação, permissões e sensitivity_locked no servidor.

Edição de membership e TenantRole envia expected_version. Um 409 exige atualização
antes de novo envio; nenhum registro é sobrescrito silenciosamente. A quantidade de
vínculos mostrada para impacto é contagem do servidor no contrato, sem estimativa.

## Auditoria e histórico

Auditoria é paginada e filtrada pelo contrato antes da projeção. Cursor não autoriza
consulta fora do contexto. Suporte recebe uma allowlist sem before/after, motivo livre,
conteúdo operacional, credenciais ou segredos de entrega. Admin recebe somente detalhes
permitidos para o domínio; Financeiro/Fiscal não é liberado por esta fase.

Histórico de usuário é do membership atual. Um login global sem evidência de contrato
não é apresentado como último acesso ao contrato nem atribuído a seus históricos.
Ausência de registro é exibida claramente. Não existe diagnóstico completo nesta fase.

## Teste e operação

O harness scripts/phase06_browser_fixture.py é exclusivo de PostgreSQL descartável
atestado, com papéis owner/runtime distintos. Usa FakeEmailTransport e nunca SMTP real.
Node frontend/e2e/phase06.mjs executa Admin, Suporte, aceite real e isolamento A/A2/B
com FastAPI/React/PostgreSQL e Chrome reais. Os segredos de teste ficam fora do Git,
sem traces ou logs de payloads e URLs de convite.

Nenhum serviço, integração externa, módulo, estrutura organizacional, sessão de suporte,
MFA, Financeiro temporário ou manutenção foi incluído. O encerramento preserva branch
para revisão e remove serviços/segredos temporários; não publica nem faz merge.
