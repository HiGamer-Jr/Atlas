# Interface autenticada HiAtlas — operação da Fase 4

## Execução local segura

O React usa a mesma origem HTTPS para páginas e `/api`. O Vite encaminha `/api`
para o backend local preservando Origin. Cookies de sessão, pré-autenticação e
CSRF continuam Secure, HttpOnly, SameSite=Strict e prefixados por `__Host-`.
Não há CORS amplo, token Bearer, sessão em localStorage ou CSRF desabilitado.

No processo do backend, configurar o DATABASE_URL de runtime já provisionado e
PUBLIC_ORIGIN com a origem HTTPS exata do navegador (sem barra final), por exemplo
`https://localhost:5174`. Não fornecer a credencial de migração ao servidor.

No processo do Vite, configurar:

```powershell
$env:HIATLAS_API_TARGET = 'http://127.0.0.1:8000'
$env:HIATLAS_TLS_CERT = 'C:/certificados/localhost.crt'
$env:HIATLAS_TLS_KEY = 'C:/certificados/localhost.key'
npm run dev
```

Os arquivos de certificado/chave devem existir e ser confiáveis no navegador.
Nunca versionar a chave. Sem os dois parâmetros TLS o Vite permite inspecionar
páginas por HTTP, mas o login seguro requer HTTPS. A configuração de proxy/TLS
lê variáveis do processo; `.env.example` apenas documenta os nomes. O frontend
não provisiona usuários, empresas ou contratos: isso continua sob os mecanismos
operacionais das Fases 2–3. Nenhuma infraestrutura de produção foi configurada.

## Fluxo e persistência

- A montagem e o retorno de foco consultam `/api/auth/me`. Ausência/expiração da
  sessão limpa a identidade, o contexto da aba e requisições pendentes.
- Login solicita `/api/auth/csrf`, envia POST `/api/auth/login` com X-CSRF-Token
  e consulta `/api/auth/me`. A senha existe somente no formulário/requisição;
  seu campo é limpo após a tentativa. Não há seletor de papel no caminho real.
- Cada mutação obtém CSRF atual, inclusive após a rotação no login. Falhas exibem
  mensagens locais sanitizadas e request_id válido como código de atendimento.
- Somente PLATFORM_ADMIN/PLATFORM_SUPPORT entram nesta interface interna. A
  apresentação usa o papel recebido de `/me`; cada permissão segue no backend.
- `/api/contracts` lista somente metadados autorizados, com pesquisa e páginas
  de 50 resultados. O backend lista somente contratos/tenants ativos, por isso
  o cartão indica Ativo. Não existem módulos contratados na projeção atual;
  a interface só os mostrará quando fornecidos pela API.
- POST `/api/contexts` retorna apenas `{id}`. GET `/api/context`, com o header
  X-HiAtlas-Context, valida e fornece os detalhes atuais do cabeçalho.
- Apenas o identificador é salvo em `sessionStorage`, chave
  `hiatlas.access-context.v1`. O reload valida o id no servidor antes de mostrar
  o portal. Sem armazenamento disponível, a seleção funciona somente em memória.
- Não existe sincronização de contexto entre abas. Cada cliente HTTP e estado
  React pertencem à própria montagem. Logout revoga a sessão compartilhada;
  outra aba reconhece isso ao voltar ao foco ou ao receber 401 de uma requisição.
- Trocar contrato encerra o contexto no servidor e cancela requisições antigas.
  Falha de rede/CSRF no encerramento mantém o contexto e permite nova tentativa;
  não há troca aparente com revogação não confirmada.
- AbortController e gerações de sessão/contexto impedem aceitar respostas
  antigas, inclusive quando um transporte ignora o cancelamento.
- O cabeçalho de empresa/contrato/ambiente é sticky. Os portais são shells sem
  ações administrativas ou de suporte antecipadas.

Não fazemos polling de `/me`/`context`: renovaria artificialmente uma sessão
ociosa. Há revalidação no foco, no reload e nas operações, além do temporizador
local da expiração absoluta do contexto. Inativação/revogação continua sendo
verificada pelo backend em cada operação.

## Demonstração

`VITE_ENABLE_DEMO=true` habilita `/demo` **somente em desenvolvimento**. O padrão
é desabilitado. O banner DEMONSTRAÇÃO permanece visível no protótipo. DemoApp
preserva os módulos atuais, não monta AuthProvider e não chama APIs reais.
Builds de produção excluem a entrada e o código do protótipo, mesmo com a flag
habilitada. localStorage é usado pelo aplicativo real apenas para o tema.

## Verificação reproduzível

O gate obrigatório está em `scripts/check-platform-foundation.ps1`. Siga
`database/README.md` para as duas URLs de teste, marcador descartável e consentimento
de reset. Não executar testes em banco de aplicação. Não executar pytest e
cenários de navegador simultaneamente no mesmo banco descartável.

Para o navegador, usar Chrome e Playwright disponível no ambiente de ferramentas.
A suíte não adiciona dependências ao produto. `HIATLAS_PLAYWRIGHT_MODULE` pode
apontar para o diretório absoluto do pacote Playwright; sem essa variável, o
Node tenta resolver `playwright` normalmente.

1. Rodar pytest no PostgreSQL descartável vazio/marcado, aplicando as migrações.
2. A partir de backend, com as variáveis de teste já presentes:
   `uv run --frozen python ../scripts/phase04-browser-fixture.py seed`.
   O utilitário recusa banco não atestado e seed em base não vazia.
3. Iniciar backend com DATABASE_URL igual ao runtime de teste e PUBLIC_ORIGIN
   igual à origem HTTPS do navegador; iniciar Vite com proxy e TLS correspondentes.
4. No processo do navegador, fornecer TEST_DATABASE_OWNER_URL,
   TEST_DATABASE_RUNTIME_URL, HIATLAS_TEST_DATABASE_RESET=1,
   HIATLAS_E2E_ORIGIN e HIATLAS_E2E_PASSWORD correspondente às fixtures
   `tests/identity_helpers.py`. Executar, em frontend: `node e2e/phase04.mjs`.
5. O script grava capturas no diretório de validação ou em HIATLAS_E2E_OUTPUT.
   Ele revoga contextos e expira sessões **somente no banco descartável atestado**.
6. Encerrar processos locais e destruir o cluster descartável ao terminar.

O navegador de teste aceita certificado localhost autoassinado em seu próprio
contexto isolado; isso não altera TLS, cookies ou validação de origem do produto.
A execução foi validada em Windows/Chrome. Não foi feita matriz multibrowser.

Para validar a entrada demo explicitamente habilitada, iniciar outro Vite com
VITE_ENABLE_DEMO=true e executar `node e2e/demo.mjs` em frontend. A origem pode
ser informada por HIATLAS_DEMO_ORIGIN. Esse teste abre o seletor demonstrativo,
entra no workspace e verifica zero requisições para `/api`.
