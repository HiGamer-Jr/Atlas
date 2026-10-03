# Fase 9 — Revisão independente frontend

Status: APROVADA na revisão independente estática do frontend após correções. Nenhum P2 aberto encontrado no snapshot final. A aprovação é limitada à revisão de código; E2E, inspeção visual e quality gate integrado pertencem à validação do coordenador.

Revisor independente; não implementou esta fase. Base: d360d30f51d76a5256a19095f0f00a401979b792; branch feat/hiatlas-platform-phase-9. Escopo: snapshot snapshot frontend preliminar (temporário) e leitura dos arquivos correspondentes, especificação aprovada e adendo da Fase 9. Nenhum teste, serviço, banco ou inspeção visual foi executado pelo revisor. As reproduções abaixo são reproduções por fluxo de controle estático, a confirmar pelo implementador.

## Achados P2 iniciais — encerrados após reavaliação

### FE-09-01 — Senha incorreta na reautenticação encerra a sessão válida

Local: frontend/src/privileged/RequestGrantDialog.tsx:11; integração com frontend/src/api/client.ts:74–75 e backend/app/identity/routes.py:233–244. No snapshot original, a chamada está na linha 8 do diálogo compacto.

A API real responde 401 AUTH_INVALID à senha incorreta em POST /auth/reauthenticate, sem revogar a sessão autenticada. ApiClient aciona onUnauthorized em qualquer 401 exceto /auth/login. AuthProvider.clear remove identidade e referências de contexto; o diálogo desaparece antes que possa apresentar a falha de reautenticação. O teste existente de reautenticação negada usa 403, não o contrato real.

Reprodução: autenticar Admin, selecionar contrato, solicitar acesso financeiro, fornecer senha incorreta e enviar. Esperado: senha limpa, erro de credenciais no diálogo, identidade/contexto válidos preservados e nenhuma criação de grant. Observado por leitura: logout local e retorno à tela de login. Distinguir especificamente AUTH_INVALID na rota de reautenticação de SESSION_INVALID, que deve continuar limpando sessão/contextos.

### FE-09-02 — Criação ambígua sem reconciliação disponível volta às ferramentas normais

Local: frontend/src/privileged/PrivilegedProvider.tsx:73–78 (catch de start; linha 24 no snapshot compacto), frontend/src/platform/ContractShell.tsx:33 e ContextProvider.restore.

O catch de start dispara refreshParent somente para falhas que não sejam AbortError; não estabelece modo de recuperação pendente. Se o servidor confirmar a criação e a resposta falhar, seguido de falha na descoberta GET /context, grant e discovered continuam nulos e restoring continua falso. O diálogo pode ser fechado e as ferramentas normais permanecem disponíveis sem informar uma concessão ativa ainda não reconciliada. O teste atual cobre apenas descoberta bem-sucedida após resposta ambígua.

Reprodução A: POST /grants confirma no servidor, mas cliente recebe 503; recuperação GET /context também recebe 503. Fechar diálogo. Esperado: estado de recuperação explícito com tentativa de reconciliação; nenhuma declaração implícita de encerramento ou retorno confirmado ao modo normal. Observado por leitura: portal normal, sem banner nem estado privilegiado recuperável nesse fluxo.

Reprodução B: enquanto POST /grants aguarda resposta após commit do servidor, clicar Sair (cabeçalho global permanece habilitado). api.cancelAll cancela a resposta; POST /auth/logout falha 503. start ignora reconciliação em AbortError, authBusy volta a false e a identidade/contexto permanecem ativos sem descoberta do grant. Reconciliar a operação ambígua enquanto o mesmo operador/contexto continuar montado; nunca ressuscitar dados depois de logout confirmado, revogação ou troca de contexto.

## Observação P3 opcional

PrivilegedBanner.tsx:7 e PrivilegedPage.tsx:22 usam toLocaleString('pt-BR') sem fuso visível. A especificação §11 pede horário local com fuso explícito para a interface de auditoria; sua aplicação aos horários de grants é uma melhoria de clareza, não um bloqueio adicional declarado nesta revisão.

## Cobertura de leitura

O menu depende de Admin e grants.request. Requisições privilegiadas usam contexto derivado explícito; contexto normal não recebe capacidades do filho. Persistência privilegiada contém somente identificador opaco em sessionStorage, com tema como preferência localStorage. READ_ONLY não oferece transição implícita. Registro de manutenção vazio não gera ações fictícias; Financeiro/Fiscal continua operacionalmente indisponível. Encerramento envia expected_version e mantém estado até resposta bem-sucedida; falhas transitórias mantêm o modo. Geração/AbortSignal bloqueiam respostas tardias; expiração do pai conserva referência do filho e observação terminal. Essas conclusões são de inspeção estática, não substituem testes e E2E.



## Reavaliação final — 2026-10-03

Fontes reavaliadas: diff frontend final contra a base aprovada, arquivos finais correspondentes e relatório consolidado phase-09.md. O coordenador declarou o código congelado para E2E. Não houve execução de testes pelo revisor nem alteração de produto durante a revisão.

- FE-09-01 ENCERRADO: ApiClient agora preserva a autenticação somente para /auth/reauthenticate com AUTH_INVALID. Outros 401, inclusive SESSION_INVALID nessa mesma rota, ainda acionam limpeza. Os novos testes usam os códigos e status reais, verificam senha vazia, contexto preservado e ausência de criação no primeiro caso; login obrigatório e contexto limpo no segundo. O implementador relata reprodução RED e GREEN.
- FE-09-02 ENCERRADO: start classifica resposta ambígua, falha de rede e cancelamento como resultado desconhecido enquanto a mesma geração permanece ativa. unresolved/restoring bloqueiam ferramentas normais. reconcile consulta o contexto pai exato, verifica id/contrato e valida o filho por GET /grants/context; falha transitória conserva recuperação e retry. A retomada após logout malsucedido é condicionada a authBusy=false. Invalidação e desmontagem incrementam geração/cancelam requisições, impedindo restauração tardia depois de logout confirmado ou perda de contexto. Os dois novos casos cobrem descoberta indisponível e resposta cancelada após commit com logout falho; o implementador relata RED/GREEN em ambos.
- P3 temporal atendido: banner e histórico usam timeZoneName:'short'. Não houve ampliação funcional.
- Revalidação de grant já exibido mantém banner/operador/contexto e fecha conteúdo enquanto houver restauração pendente ou indisponível, com erro e retry. Nenhuma nova quebra P2 foi identificada no escopo estático das correções.

Evidências atribuídas ao implementador, não ao revisor: relatório final registra npm.cmd test com 249 testes, 14 arquivos e zero skips, incluindo 33 casos Privileged.test.tsx; oxlint sem avisos/erros e TypeScript/Vite com 68 módulos aprovados. O relatório informa diff --check anterior e requer repetição pelo gate integrado.

Conclusão de revisão: os dois P2 iniciais estão tratados no código e nas reproduções relatadas. Aprovação independente do frontend no escopo do snapshot final, sem afirmar execução própria de runtime, geometria sticky/mobile, backend ou PostgreSQL. E2E real, screenshots, gate final integrado e limpeza continuam sob responsabilidade do coordenador e não recebem PASS deste relatório.


## Complemento da revisão — FE-09-03 (F09-03), lifecycle do StrictMode

Achado P2 identificado pelo E2E real do coordenador depois do primeiro snapshot final: o efeito de RequestGrantDialog reutilizava um AbortController cuja instância havia sido abortada pelo replay de efeitos do React StrictMode. main.tsx monta App em StrictMode. O coordenador relatou que enviar a reautenticação limpava a senha, mas nenhuma chamada HTTP de autenticação ocorria e a tentativa não prosseguia ao diálogo de revisão. Este RED de browser é atribuído ao coordenador; não foi executado pelo revisor.

Reavaliação limitada a RequestGrantDialog.tsx, novo teste StrictMode em Privileged.test.tsx e complemento de relatório consolidado phase-09.md. FE-09-03 ENCERRADO na revisão estática: cada setup cria mountedController novo e atribui abort.current; cleanup captura e aborta somente essa instância. Cada reauth captura requestController antes do await e usa a mesma instância tanto no signal da API quanto na verificação de resposta. Assim, o segundo setup do replay usa signal ativo, e a resposta de uma instância já encerrada não pode abrir revisão por observar acidentalmente o signal da nova instância. A limpeza imediata da senha permanece. Cancelamento/desmontagem continua propagando o AbortSignal ao ApiClient, que rejeita respostas tardias antes de consumi-las. Não foi identificado novo P2 nessa correção limitada.

O implementador relata RED efetivo de 34 testes com uma falha antes da correção e GREEN dos 34 depois; o novo caso percorre senha incorreta/401 AUTH_INVALID, erro no diálogo com operador ainda autenticado, correção da senha, revisão e banner. O complemento registra gate completo posterior: 250 testes em 14 arquivos, zero skips (04:15:19 local, 13,79 s), oxlint sem erros/avisos e TypeScript/Vite aprovados com 68 módulos. Essas execuções pertencem ao implementador; o revisor somente leu fonte, teste e relatório.

A aprovação independente estática do frontend abrange agora a correção FE-09-03, sem P2 aberto encontrado no escopo reavaliado. Reexecução do E2E real e gate integrado permanecem com o coordenador; este complemento não antecipa PASS de browser ou banco.

## Complemento — revisão restrita da sincronização do teste discovery

Reavaliado Privileged.test.tsx:83–109 em comparação com o caso no snapshot final anterior. A alteração usa act assíncrono para completar efeitos após render, para disparar foco e para resolver a resposta controlada do filho. A promessa GET /grants/context permanece explicitamente pendente até depois das asserções de segurança. A ausência de Usuários e Trocar empresa/contrato continua obrigatória durante essa pendência, e o banner continua obrigatório depois da resolução.

Nenhuma regressão foi enfraquecida: a versão nova acrescenta confirmação de consulta adicional GET /context após foco e header X-HiAtlas-Context=privileged-a na consulta do filho. Não introduz sleeps, repetição do evento de foco, timeout ampliado ou sucesso antecipado da resposta do filho. A alteração trata a sincronização do teste com instalação do efeito, sem modificar código de produto. Aprovação estática limitada ao teste; nenhuma nova questão P2 encontrada.

Evidências atribuídas: o coordenador relatou gate RED intermitente 249/250; o complemento do implementador relata suite antiga passando em repetição, depois teste sincronizado com 34 casos focados e suite completa de 250 testes em 14 arquivos, zero skips (04:26:46 local, 15,61 s), oxlint sem erros/avisos e TypeScript/Vite aprovados. O revisor não executou testes. A aprovação independente do frontend permanece válida nesse escopo adicional; gate integrado e E2E continuam registrados pelo coordenador.
