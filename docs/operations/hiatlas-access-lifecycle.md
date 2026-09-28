# Operação de convites e recuperação — Fase 5

## Configuração

A API e o worker usam o mesmo banco runtime, a mesma origem HTTPS e a mesma
chave da outbox. Credenciais de owner continuam exclusivas das migrações.
Fornecer as variáveis por um gerenciador de segredos/ambiente do processo;
não versionar chaves, senhas, e-mails de teste com links ou dumps da fila.

| Variável | Finalidade / padrão inicial |
|---|---|
| PUBLIC_ORIGIN | Origem HTTPS explícita, sem caminho; usada para os links. Não deriva do Host da requisição. |
| OUTBOX_KEY | Chave Fernet válida, protegida fora do banco. Obrigatória para enfileirar acesso. |
| SMTP_HOST / SMTP_PORT | Servidor SMTP e porta (587). |
| SMTP_SENDER | Remetente configurado. |
| SMTP_USERNAME / SMTP_PASSWORD | Autenticação do provedor, quando necessária. |
| SMTP_TIMEOUT_SECONDS | Timeout do transporte (15 s). |
| INVITE_SECONDS | Validade do convite: 86400 s (24 h). |
| PASSWORD_RESET_SECONDS | Validade da recuperação: 1800 s (30 min). |
| PASSWORD_MIN_LENGTH / PASSWORD_MAX_LENGTH | Política central: 12 a 1024 caracteres; sem truncamento. |
| EMAIL_MAX_ATTEMPTS | Limite de tentativas: 5. |
| EMAIL_RETRY_SECONDS | Intervalo inicial de retry: 60 s. |
| EMAIL_RETRY_MAX_SECONDS | Teto do intervalo de retry: 3600 s. |
| EMAIL_LEASE_SECONDS | Prazo do claim: 120 s. |
| ACCESS_REQUEST_LIMIT / ACCESS_SOURCE_LIMIT | Limites persistentes por finalidade/destinatário e origem: 5 / 100. |
| ACCESS_WINDOW_SECONDS | Janela dos limites: 900 s. |
| REAUTHENTICATION_SECONDS | Autenticação recente para identidade existente: 300 s. |
| RECOVERY_RESPONSE_FLOOR_SECONDS | Piso de resposta neutra: 0,25 s. |

SMTP usa STARTTLS com validação do certificado. Ausência de transporte/chave
produz indisponibilidade; a aplicação nunca apresenta solicitação enfileirada
como entrega confirmada. Não ativar logs de debug SMTP, corpos HTTP ou valores
SQL. Nenhum endpoint público fornece o token ou conteúdo da outbox.

A chave cifra o segredo necessário à entrega; SecurityToken mantém somente seu
hash. Proteger e fazer backup da chave separadamente do banco. A troca de chave
precisa considerar mensagens pendentes: não substituir silenciosamente a chave
de uma fila ainda cifrada; mensagens indecifráveis são canceladas. Rotação com
múltiplas chaves não faz parte desta fase.

## Banco e worker

Executar as migrações pelo procedimento de `database/README.md`. A migração 0004
adiciona tokens/outbox e o estado pendente de convite ao vínculo. O runtime tem
somente os privilégios definidos pela migração; auditoria permanece append-only.

Após o commit da solicitação HTTP, executar o worker em processo separado:

```powershell
uv run --frozen python -m app.identity.delivery --once --limit 20
```

A execução pode ser chamada periodicamente pelo operador. Não requer Redis,
serviço distribuído ou envio dentro da transação HTTP. O resumo contém contagens,
sem destinatários, links ou conteúdo. Não há scheduler de produção configurado
por esta entrega.

O worker persiste o claim antes do SMTP e revalida o token antes de entregar.
`SENT` significa aceitação pelo transporte, não leitura ou entrega final na
caixa postal. Falhas certas podem ser tentadas novamente com atraso e limite;
resultado incerto é `UNKNOWN`, sem reenvio automático. Um crash entre aceitação
SMTP e commit não permite comprovar entrega exatamente uma vez. O operador deve
investigar o provedor por Message-ID, sem expor segredos, e emitir nova solicitação
quando necessário; o novo token invalida o anterior.

## Fluxos públicos e identidade existente

Login oferece `/password/forgot`. A solicitação usa resposta neutra para contas
existentes, ausentes e inelegíveis. Os links usam fragmento (`#token=...`), que não
é enviado ao servidor HTTP na navegação. As páginas `/invite/accept` e
`/password/reset` capturam o segredo em memória e removem o fragmento antes das
requisições de validação. Não usam armazenamento do navegador para tokens.

O backend valida finalidade, validade, destinatário e estado atual, e consome o
token uma única vez. A troca de senha atualiza Argon2id e revoga todas as sessões
e contextos daquele usuário na mesma transação da auditoria. Exige novo login.

Um convite de novo usuário permite definir senha própria. Para identidade que
já tem senha, o destinatário faz autenticação recente e confirma o vínculo;
a senha e os demais contratos são preservados. O operador não recebe informação
sobre outros contratos e não define senha pelo destinatário.

O vínculo pendente não concede acesso. Ativo e bloqueado são flags independentes:
ativar não desbloqueia; desbloquear não ativa. Mudanças no contrato A não alteram
o vínculo em B. A API revalida acesso no servidor.

## Publicação futura e páginas com token

Ao servir o build, configurar fallback das rotas públicas para `index.html` e
servir recursos a partir da raiz. Manter HTTPS, `Referrer-Policy: no-referrer` e
`Cache-Control: no-store`. O HTML contém a meta de referrer e o preview local
aplica esses headers. Não adicionar analytics, scripts de terceiros, captura de
corpos HTTP ou error tracking com payloads nessas páginas. Não colocar o token
em query string. Não registrar URLs secretas em tickets ou evidências.

Esta fase não publica o site e não configura SMTP ou identidades de produção.

## Reprodução do E2E controlado

1. Provisionar PostgreSQL descartável atestado conforme `database/README.md`.
2. Rodar o pytest completo; não rodar testes simultâneos no mesmo banco.
3. Fornecer URLs owner/runtime de teste, consentimento de reset, OUTBOX_KEY,
   HIATLAS_E2E_ORIGIN (HTTPS), HIATLAS_E2E_STATE (diretório temporário exclusivo)
   e HIATLAS_E2E_PASSWORD correspondente à fixture de testes.
4. Iniciar `uvicorn phase05_browser_fixture:create_browser_app --factory
   --app-dir ../scripts --host 127.0.0.1 --port 8015 --no-access-log` a partir
   de backend, e o preview Vite HTTPS com proxy correspondente.
5. Com Chrome e Playwright disponíveis, em frontend executar
   `node e2e/phase05.mjs`. HIATLAS_PLAYWRIGHT_MODULE pode indicar o pacote
   instalado no ambiente de ferramentas; não é dependência do produto.
6. O script semeia uma base vazia, usa FakeEmailTransport e coleta mensagens
   somente por pipe em memória. Não envia e-mail real. Capturas não contêm
   tokens, senhas ou links. Encerrar processos e remover segredos e cluster
   temporários ao terminar.

O harness recusa banco sem marcador descartável e não fornece endpoints de teste
na aplicação do produto. Nunca usá-lo em produção.

## Limitação de concorrência desta etapa

O worker usa um lock transacional de ciclo de acesso durante a revalidação e o
envio SMTP para impedir que uma invalidação seja confirmada entre essas duas
etapas. Isso serializa operações de ciclo de acesso, inclusive de destinatários
diferentes. Com o piso padrão da recuperação, a capacidade desse caminho fica
em torno de quatro solicitações por segundo antes de considerar outras operações;
latência SMTP também aumenta a espera. Login normal não toma esse lock.
Essa solução prioriza consistência no worker simples desta fase e não equivale
a uma fila distribuída ou dimensionada para alto volume. Medir carga antes de
produção; eventual particionamento de locks exigirá preservar a ordem de locks
e repetir os testes de concorrência e invalidação.

## Convite de operador interno

O endpoint de convite interno é exclusivo de PLATFORM_ADMIN e exige a senha
atual do administrador com confirmação explícita do destinatário e papel.
Essa senha autentica o solicitante; nunca define a senha do convidado. Suporte
não usa esse caminho. Um administrador pendente não pode substituir o último
administrador utilizável. O destinatário estabelece sua própria senha pelo
mesmo mecanismo de token/outbox. Não existe tela de gestão de operadores nesta
fase.
