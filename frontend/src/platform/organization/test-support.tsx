import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';
import App from '../../App';
export const kinds = [
 ['COMPANY', 'Empresa'], ['BRANCH', 'Filial'], ['UNIT', 'Unidade'], ['STORE', 'Loja'],
 ['DISTRIBUTION_CENTER', 'Centro de distribuição'], ['WAREHOUSE', 'Depósito'], ['OFFICE', 'Escritório'], ['WORKSITE', 'Canteiro'],
].map(([kind, label]) => ({ kind, label, allowed_parent_kinds: kind === 'COMPANY' ? [] : ['COMPANY', 'UNIT'] }));
export const node = { id: 'node-a', tenant_id: 'tenant-a', contract_id: 'contract-a', kind: 'WORKSITE', name: 'Canteiro Norte', code: 'NORTE', parent_id: 'parent-a', parent_name: 'Matriz', parent_code: 'MATRIZ', active: true, version: 3, depth: 1, child_count: 2, active_child_count: 0, scope_membership_count: 0, created_at: '2026-10-01T10:00:00Z', updated_at: '2026-10-01T10:00:00Z', allowed_actions: ['edit', 'inactivate'] };
export const modules = [['PROCUREMENT','Compras'],['COMEX','Comércio exterior'],['INVENTORY','Estoque'],['FINANCE','Financeiro'],['PROJECTS','Obras e projetos'],['DATAHUB','Data Hub']].map(([code,label]) => ({ id: code === 'PROCUREMENT' ? 'module-a' : null, code, label, contracted: code === 'PROCUREMENT', active: false, enabled: false, operational_available: false, version: code === 'PROCUREMENT' ? 2 : 0, allowed_actions: ['edit'] }));
export const calls: { path: string; init: RequestInit }[] = [];
export const state = { actor: 'PLATFORM_ADMIN', grants: ['memberships.read','roles.read','organization.manage','modules.read','modules.manage','audit.read'], nodes: [node], node, modules, listStatus: 200, detailStatus: 200, modulesStatus: 200, mutationStatus: 200, total: 1, parentTotal: 21 };
export function response(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status }); }
export function setup() {
 beforeEach(() => {
  Object.assign(state, { actor: 'PLATFORM_ADMIN', grants: ['memberships.read','roles.read','organization.manage','modules.read','modules.manage','audit.read'], nodes: [node], node: { ...node }, modules: modules.map(m => ({ ...m })), listStatus: 200, detailStatus: 200, modulesStatus: 200, mutationStatus: 200, total: 1, parentTotal: 21 });
  calls.length = 0; localStorage.clear(); sessionStorage.clear();
  // Context storage is the only opaque identifier restored by the real provider.
  sessionStorage.setItem('hiatlas.access-context.v1', 'scope-a');
  history.replaceState(null, '', '/');
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
   const path = url.replace('/api', ''); calls.push({ path, init });
   if(path === '/auth/me') return response({user_id:'operator',display_name:'Operador',platform_role:state.actor});
   if(path === '/auth/csrf') return response({token:'csrf'});
   if(path === '/context') return response({id:'scope-a',tenant_name:'Empresa A',contract_id:'contract-a',contract_code:'CTR-A',environment:'TEST',expires_at:'2099-01-01T00:00:00Z',capabilities:state.grants});
   if(path === '/contracts') return response({items:[]});
   if(init.method && init.method !== 'GET') return response(path.startsWith('/contract/modules') ? state.modules.find(m => path.endsWith(m.code)) : state.node, state.mutationStatus);
   if(path.startsWith('/memberships?')) return response({items:[],total:0,limit:20,offset:0});
   if(path === '/organization/node-types') return response({items:kinds});
   if(path.startsWith('/organization/nodes?')) {
    const query = new URL(url,'http://localhost').searchParams;
    if(query.has('parent_for_kind')) return response({items:[{...node,id:query.get('offset') === '20'?'parent-b':'parent-a',name:query.get('offset') === '20'?'Filial Sul':'Matriz',code:'MATRIZ',kind:'COMPANY'}],total:state.parentTotal,limit:20,offset:Number(query.get('offset'))});
    return response({items:state.nodes,total:state.total,limit:20,offset:Number(query.get('offset'))},state.listStatus);
   }
   if(path === '/organization/nodes/node-a') return response(state.node,state.detailStatus);
   if(path === '/contract/modules') return response({items:state.modules},state.modulesStatus);
   return response({},404);
  }));
 });
 afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
}
export async function open(page: 'Estrutura'|'Módulos') { render(<App/>); fireEvent.click(await screen.findByRole('button',{name:page})); }
