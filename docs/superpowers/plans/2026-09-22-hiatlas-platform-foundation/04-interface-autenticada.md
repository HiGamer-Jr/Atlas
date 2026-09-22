# Fase 4 — Interface autenticada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [Especificação aprovada](../../specs/2026-09-22-hiatlas-platform-access-foundation-design.md).
**Global Constraints:** Aplicam-se integralmente as restrições, interfaces, fixtures e protocolo TDD do [plano principal](README.md). support_assignable começa false; perfis sensíveis são inelegíveis. OrganizationNode usa WORKSITE, não Project. Financeiro exige concessão temporária auditada. Correções só por handlers tipados. Flags/parâmetros/integrações não recebem CRUD genérico.
**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest/Ruff; React, TypeScript, Vite, Vitest e Testing Library.
**Status:** não executado. Não marcar checkbox por existir apenas o código de exemplo neste plano.

**Goal:** Entrar por login real e selecionar explicitamente contrato antes de qualquer tela de cliente.
**Architecture:** Cliente HTTP único, AuthProvider e shell separado do protótipo.
**Depende de:** fase 3. **Não inclui:** formulários de gestão ainda indisponíveis.

## Review Focus

- Perfil escolhido no navegador não pode autenticar ou elevar privilégio (4.1).
- Cookie expirado limpa a tela sem reutilizar dados (4.1).
- Modo demo não chama APIs reais nem entra no build de produção (4.1).
- Resposta atrasada de A não aparece depois de selecionar B (4.2).
- Dois contratos do mesmo tenant têm cabeçalhos e caches distintos (4.2).

## Tarefa 4.1 — Login e shell reais, demo isolado

**Arquivos**
- Criar: frontend/src/api/client.ts, errors.ts.
- Criar: frontend/src/auth/AuthProvider.tsx, LoginForm.tsx, types.ts,
  LoginForm.test.tsx, AuthProvider.test.tsx.
- Criar: frontend/src/demo/DemoApp.tsx.
- Modificar: frontend/src/App.tsx, App.test.tsx, vite.config.ts,
  frontend/.env.example e Workspace.test.tsx.

**Interfaces:** ApiClient.request<T>(path, {method, body, contextId, signal}).
AuthProvider fornece user/status, login(email,password), logout().
LoginForm recebe onLogin: (email:string,password:string)=>Promise<void>.
Apenas a senha digitada pelo próprio titular pode ser revelada por toggle local;
nenhuma tela administrativa recebe senha de outro usuário.

- [ ] **RED:**
```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import LoginForm from './LoginForm'

it('does not offer a role selector', () => {
  render(<LoginForm onLogin={vi.fn()} />)
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.getByLabelText('E-mail')).not.toHaveAttribute('readonly')
  expect(screen.getByLabelText('Senha')).toHaveValue('')
  fireEvent.change(screen.getByLabelText('E-mail'), { target: {value: 'user@example.test'} })
  expect(screen.getByLabelText('E-mail')).toHaveValue('user@example.test')
})
```
AuthProvider.test.tsx usa respostas HTTP controladas na fronteira fetch para
testar login, CSRF, logout, 401 e falha de rede, verificando UI e requisição;
nenhum teste usa role local para estabelecer autenticação.
- [ ] Rodar em frontend: `npm test -- src/auth/LoginForm.test.tsx src/auth/AuthProvider.test.tsx`.
- [ ] **GREEN:** fetch com credentials: 'include', CSRF nas mutações e
AbortSignal; nunca serializar senha em logs nem guardar tokens no localStorage.
```ts
const response = await fetch('/api/auth/me', {
  credentials: 'include',
  signal,
})
if (response.status === 401) return null
if (!response.ok) throw new Error('Não foi possível consultar a sessão.')
return response.json()
```
Vite faz proxy /api para backend local, configurado sem abrir CORS amplo.
App real espera /auth/me. A entrada demo é arquivo/rota separada ativada apenas
em desenvolvimento por configuração explícita e não possui transporte real.
Mover montagem antiga para DemoApp; testes de Workspace importam DemoApp para
preservar regressão demonstrativa sem afirmar segurança de dados fictícios.
Não reescrever módulos de obras ou dashboards.
- [ ] Atualizar App.test.tsx para login real; preservar testes visuais do
LoginScreen demonstrativo sob arquivo de teste explicitamente demo.
- [ ] Commit: `feat: separate authenticated app from demonstration workspace`.

## Tarefa 4.2 — Seleção explícita e shell de contrato

**Arquivos**
- Criar: frontend/src/platform/ContractPicker.tsx, ContractShell.tsx,
  ContextProvider.tsx, ContractContext.test.tsx, Platform.css.
- Criar: frontend/src/api/client.test.ts.
- Modificar: frontend/src/App.tsx.

**Interfaces:** ContractPicker lista GET /contracts e chama POST /contexts.
ContextProvider: selected: {id,tenantId,contractId,company,code,environment}|null,
select(contractId): Promise<void>, clear(): Promise<void>.
ContractShell mostra nome interno Administrador HiAtlas ou Suporte HiAtlas,
empresa, contrato, ambiente, sair/trocar contexto e apenas áreas entregues.

- [ ] **RED:** criar `renderContextFlow` em
frontend/src/test/platformHarness.tsx. A fixture renderiza App com fetch
roteado por method/path; retorna `resolveContractA` para concluir uma resposta
adiada. Respostas vêm de constantes fictícias de /me, /contracts e /contexts.
```tsx
it('ignores an old response after switching contracts', async () => {
  const flow = renderContextFlow()
  await flow.selectContract('Contrato A')
  await flow.selectContract('Contrato B')
  flow.resolveContractA()
  expect(await screen.findByTestId('contract-context')).toHaveTextContent('Contrato B')
  expect(screen.queryByText('Detalhe exclusivo A')).not.toBeInTheDocument()
})
```
Harness usa clicks/findBy* da Testing Library, sem setState direto.
Adicionar testes de reload sem contrato, 403/contexto expirado e dois contextos.
- [ ] Rodar `npm test -- src/platform/ContractContext.test.tsx src/api/client.test.ts`.
- [ ] **GREEN:** contrato é seleção explícita por aba; estado em memória, sem
reabrir automaticamente outro contrato. Cancelar requests e incrementar geração
ao selecionar/limpar; aceitar resposta somente da geração atual:
```ts
const generation = ++generationRef.current
const result = await api.request<ContractContext>('/contexts', options)
if (generation !== generationRef.current) return
setSelected(result)
```
Tipos ContractContext definidos em ContextProvider.tsx com os campos do contrato.
Na troca, limpar dados antes da nova busca, encerrar contexto anterior e não
exibir métricas/demo como fallback. Módulos sem backend mostram indisponibilidade.
- [ ] Inspecionar fluxo admin e suporte nos dois temas, teclado, tela estreita,
estado vazio e mensagens de erro. Contexto permanece visível no scroll.
- [ ] Commit: `feat: add explicit contract selection to platform portal`.

## Quality gate e parada

- [ ] Gate completo e inspeção UI, sem validar segurança apenas por menus.
- [ ] Build de produção sem seletor demo ou credenciais fixas; teste prova
entrada demo indisponível, não apenas um texto escondido.
- [ ] Registrar phase-04.md e parar.

## Ajuste aprovado: contexto por aba

AccessContext fica em memória da aba; sessionStorage é permitido quando houver
necessidade de recuperar a seleção naquela aba, com revalidação pelo servidor.
Nunca usar localStorage para autenticação/contexto nem sincronizar contexto
entre abas via evento storage. Token de autenticação permanece em cookie HttpOnly.
Adicionar teste com dois ambientes de aba: selecionar B na segunda preserva A
na primeira; contexto restaurado/expirado não libera consulta sem validação.
