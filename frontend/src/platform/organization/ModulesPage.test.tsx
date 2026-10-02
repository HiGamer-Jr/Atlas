import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';
import { calls, modules, open, setup, state } from './test-support';
setup();
async function configure(label: string) { fireEvent.click(await screen.findByRole('button',{name:'Configurar '+label})); await waitFor(()=>expect(screen.getByRole('button',{name:'Revisar módulo'})).toBeEnabled()); }
it('shows six server catalog modules and independent contracted/active state with real operational unavailability', async () => {
 await open('Módulos'); await screen.findByRole('heading',{name:'Compras'}); expect(screen.getByText('Contratado: Sim')).toBeVisible(); expect(screen.getAllByText('Ativo: Não')).toHaveLength(6);
 expect(screen.getAllByText('Operação indisponível nesta fase.')).toHaveLength(6); expect(screen.queryByRole('button',{name:/parâmetro|integração|flag/i})).not.toBeInTheDocument();
});
it('support menu has read-only modules and history without structure or mutation actions', async () => {
 state.actor='PLATFORM_SUPPORT'; await open('Módulos'); await screen.findByRole('heading',{name:'Compras'});
 expect(screen.queryByRole('button',{name:'Estrutura'})).not.toBeInTheDocument(); expect(screen.queryByRole('button',{name:'Perfis'})).not.toBeInTheDocument(); expect(screen.getByRole('button',{name:'Histórico'})).toBeVisible(); expect(screen.queryByRole('button',{name:/Configurar /})).not.toBeInTheDocument();
 expect(screen.getByText('Consulta de módulos. Alterações disponíveis somente para administradores autorizados.')).toBeVisible();
});
it('module contextual review submits scoped id and version, separates contracted and active', async () => {
 await open('Módulos'); await configure('Compras'); expect(screen.getByLabelText('Módulo contratado')).toBeChecked(); expect(screen.getByLabelText('Módulo ativo')).not.toBeChecked();
 fireEvent.click(screen.getByLabelText('Módulo ativo')); fireEvent.click(screen.getByRole('button',{name:'Revisar módulo'})); expect(screen.getByRole('dialog')).toHaveTextContent('CTR-A'); expect(screen.getByRole('dialog')).toHaveTextContent('Operação indisponível');
 expect(calls.some(c=>c.init.method==='PATCH')).toBe(false); fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await screen.findByText('Módulo salvo.');
 expect(JSON.parse(String(calls.find(c=>c.init.method==='PATCH')?.init.body))).toEqual({contracted:true,active:true,expected_version:2,module_id:'module-a'}); expect(new Headers(calls.find(c=>c.init.method==='PATCH')?.init.headers).get('X-HiAtlas-Context')).toBe('scope-a');
});
it('absent module starts version zero and cannot activate without contracting', async () => {
 await open('Módulos'); await configure('Financeiro'); expect(screen.getByLabelText('Módulo ativo')).toBeDisabled();
 fireEvent.click(screen.getByLabelText('Módulo contratado')); expect(screen.getByLabelText('Módulo ativo')).toBeEnabled(); fireEvent.click(screen.getByLabelText('Módulo ativo')); fireEvent.click(screen.getByLabelText('Módulo contratado')); expect(screen.getByLabelText('Módulo ativo')).not.toBeChecked();
 fireEvent.click(screen.getByLabelText('Módulo contratado')); fireEvent.click(screen.getByRole('button',{name:'Revisar módulo'})); fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await screen.findByText('Módulo salvo.');
 expect(JSON.parse(String(calls.find(c=>c.path.endsWith('FINANCE')&&c.init.method==='PATCH')?.init.body))).toEqual({contracted:true,active:false,expected_version:0,module_id:null});
});
it('failed module conflict refresh blocks stale confirmation until successful data is reviewed again', async () => {
 await open('Módulos'); await configure('Compras'); fireEvent.click(screen.getByRole('button',{name:'Revisar módulo'}));
 state.mutationStatus=409; state.modulesStatus=503; fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await within(screen.getByRole('dialog')).findByText(/Os dados foram alterados/);
 fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Atualizar dados'})); await waitFor(()=>expect(calls.filter(c=>c.path==='/contract/modules'&&c.init.method==='GET').length).toBeGreaterThanOrEqual(2)); expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeDisabled();
 state.modulesStatus=200; state.mutationStatus=200; state.modules=modules.map(m=>({...m,version:m.code==='PROCUREMENT'?3:m.version})); fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Atualizar dados'}));
 await screen.findByRole('button',{name:'Revisar módulo'}); fireEvent.click(screen.getByRole('button',{name:'Revisar módulo'})); fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await screen.findByText('Módulo salvo.'); expect(JSON.parse(String(calls.filter(c=>c.init.method==='PATCH').at(-1)?.init.body)).expected_version).toBe(3);
});
it('module error retries into empty server state', async () => {
 state.modulesStatus=503; await open('Módulos'); expect(screen.getByText('Carregando módulos…')).toBeVisible(); await screen.findByRole('alert'); state.modulesStatus=200; state.modules=[];
 fireEvent.click(screen.getByRole('button',{name:'Tentar novamente'})); await screen.findByText('Nenhum módulo disponível neste contexto.');
});
it.each([401,403])('real providers remove context or protected module data on %s', async status => {
 await open('Módulos'); await configure('Compras'); fireEvent.click(screen.getByRole('button',{name:'Revisar módulo'}));
 state.mutationStatus=status; state.modulesStatus=status; fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'}));
 await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument()); await waitFor(()=>expect(screen.queryByRole('heading',{name:'Compras'})).not.toBeInTheDocument());
 if(status===401) { await screen.findByLabelText('E-mail'); expect(screen.queryByTestId('contract-context')).not.toBeInTheDocument(); expect(sessionStorage.getItem('hiatlas.access-context.v1')).toBeNull(); }
});

it('forbidden module mutation discards cached metadata even when refresh fails transiently', async () => {
 await open('Módulos'); await configure('Compras'); fireEvent.click(screen.getByRole('button',{name:'Revisar módulo'}));
 state.mutationStatus=403; state.modulesStatus=503; fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'}));
 await screen.findByText('Serviço temporariamente indisponível. Tente novamente mais tarde.');
 expect(screen.queryByRole('heading',{name:'Compras'})).not.toBeInTheDocument(); expect(screen.queryByRole('button',{name:'Configurar Compras'})).not.toBeInTheDocument();
});
