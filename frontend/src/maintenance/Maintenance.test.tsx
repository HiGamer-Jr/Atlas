import {fireEvent,render,screen,cleanup} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import App from '../App';
const calls:string[]=[];
let role='PLATFORM_ADMIN',caps=['maintenance.authorize','memberships.read'];
beforeEach(()=>{sessionStorage.clear();sessionStorage.setItem('hiatlas.access-context.v1','parent-a');calls.length=0;role='PLATFORM_ADMIN';caps=['maintenance.authorize','memberships.read'];vi.stubGlobal('fetch',vi.fn(async(url:string)=>{const p=url.replace('/api','');calls.push(p);return new Response(JSON.stringify(p==='/auth/me'?{user_id:'admin',display_name:'Admin',platform_role:role}:p==='/context'?{id:'parent-a',tenant_name:'Empresa A',contract_id:'contract-a',contract_code:'CTR-A',environment:'TEST',expires_at:'2099-01-01T00:00:00Z',capabilities:caps}:p.startsWith('/memberships?')?{items:[],total:0}:p==='/maintenance'?{items:[]}:p.startsWith('/processings?')?{items:[],total:0,limit:20,offset:0}:{}),{status:200});}));});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('admin maintenance capability opens exact empty production catalog',async()=>{render(<App/>);fireEvent.click(await screen.findByRole('button',{name:'Manutenção'}));expect(await screen.findByText('Nenhuma operação de manutenção está disponível para este contrato.')).toBeVisible();expect(calls).toContain('/maintenance');expect(screen.queryByRole('button',{name:'Solicitar acesso de manutenção'})).not.toBeInTheDocument();});
it('support has no maintenance menu even with capability',async()=>{role='PLATFORM_SUPPORT';render(<App/>);await screen.findByRole('heading',{name:'Suporte HiAtlas'});expect(screen.queryByRole('button',{name:'Manutenção'})).not.toBeInTheDocument();expect(calls).not.toContain('/maintenance');});
it('admin without maintenance capability has no menu',async()=>{caps=['memberships.read'];render(<App/>);await screen.findByRole('heading',{name:'Administração HiAtlas'});expect(screen.queryByRole('button',{name:'Manutenção'})).not.toBeInTheDocument();});

it('normal admin reads recent diagnostics with empty action registry and cannot reprocess',async()=>{render(<App/>);fireEvent.click(await screen.findByRole('button',{name:'Manutenção'}));expect(await screen.findByText('Nenhum processamento disponível neste contrato.')).toBeVisible();expect(screen.queryByRole('button',{name:'Reprocessar'})).not.toBeInTheDocument();});
