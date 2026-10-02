import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { calls, node, open, response, setup, state } from './test-support';
setup();
it('admin menus include structure and modules while context and official theme remain visible', async () => {
 await open('Estrutura'); await screen.findByText('Canteiro Norte');
 for (const name of ['Usuários','Perfis','Estrutura','Módulos','Auditoria']) expect(screen.getByRole('button',{name})).toBeVisible();
 expect(screen.getByTestId('contract-context')).toHaveTextContent('Empresa A'); expect(screen.getByTestId('contract-context')).toHaveTextContent('CTR-A');
 expect(screen.getByRole('img',{name:'HiAtlas — Supply Chain Intelligence'})).toBeVisible(); fireEvent.click(screen.getByRole('button',{name:'Tema escuro'})); expect(screen.getByRole('main')).toHaveAttribute('data-theme','dark');
});
it('physical hierarchy shows Portuguese kind, explicit parent and level with bounded filters', async () => {
 state.total=22; await open('Estrutura'); await screen.findByText('Canteiro Norte');
 expect(screen.getByText('Pai: Matriz (MATRIZ)')).toBeVisible(); expect(screen.getByText('Nível 1')).toBeVisible();
 fireEvent.change(screen.getByRole('combobox',{name:'Tipo do filtro'}),{target:{value:'WORKSITE'}});
 fireEvent.change(screen.getByLabelText('Nome ou código'),{target:{value:'Norte'}}); fireEvent.click(screen.getByRole('button',{name:'Pesquisar estrutura'}));
 await waitFor(()=>expect(calls.some(c=>c.path.includes('kind=WORKSITE')&&c.path.includes('search=Norte')&&c.path.includes('limit=20'))).toBe(true));
 fireEvent.click(screen.getByRole('button',{name:'Próxima página'})); await waitFor(()=>expect(calls.some(c=>c.path.includes('offset=20')&&!c.path.includes('parent_for_kind'))).toBe(true));
});
it('create reviews physical worksite with server kinds and paged permitted parents before posting', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Nova unidade'}));
 const dialog=screen.getByRole('dialog'); await within(dialog).findByRole('option',{name:'Canteiro'});
 expect(within(dialog).getAllByRole('option').some(o=>o.textContent==='Obra'||o.getAttribute('value')==='PROJECT')).toBe(false);
 expect(within(dialog).getByRole('combobox',{name:'Tipo de unidade'})).toHaveAttribute('aria-label','Tipo de unidade');
 fireEvent.change(within(dialog).getByRole('combobox',{name:'Tipo de unidade'}),{target:{value:'WORKSITE'}});
 fireEvent.change(within(dialog).getByLabelText('Nome da unidade'),{target:{value:'Canteiro Leste'}}); fireEvent.change(within(dialog).getByLabelText('Código'),{target:{value:'LESTE'}});
 await within(dialog).findByRole('option',{name:'Matriz (MATRIZ)'}); fireEvent.click(within(dialog).getByRole('button',{name:'Próximos pais'}));
 await within(dialog).findByRole('option',{name:'Filial Sul (MATRIZ)'}); fireEvent.change(within(dialog).getByRole('combobox',{name:'Unidade pai'}),{target:{value:'parent-b'}});
 fireEvent.click(within(dialog).getByRole('button',{name:'Revisar unidade'})); expect(dialog).toHaveTextContent('Empresa A'); expect(dialog).toHaveTextContent('Canteiro'); expect(dialog).toHaveTextContent('Pai: Filial Sul (MATRIZ)');
 expect(calls.some(c=>c.init.method==='POST'&&c.path==='/organization/nodes')).toBe(false);
 fireEvent.click(within(dialog).getByRole('button',{name:'Confirmar'})); await screen.findByText('Unidade salva.');
 expect(JSON.parse(String(calls.find(c=>c.init.method==='POST'&&c.path==='/organization/nodes')?.init.body))).toEqual({kind:'WORKSITE',name:'Canteiro Leste',code:'LESTE',parent_id:'parent-b',active:true});
});
it('edit reads current detail, locks kind/code and sends expected version after impact review', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'}));
 fireEvent.click(await screen.findByRole('button',{name:'Editar unidade'})); await waitFor(()=>expect(screen.getByRole('button',{name:'Revisar unidade'})).toBeEnabled()); expect(screen.getByLabelText('Código')).toBeDisabled(); expect(screen.getByRole('combobox',{name:'Tipo de unidade'})).toBeDisabled();
 await screen.findByRole('option',{name:'Matriz (MATRIZ)'}); fireEvent.change(screen.getByLabelText('Nome da unidade'),{target:{value:'Canteiro Atualizado'}}); fireEvent.click(screen.getByRole('button',{name:'Revisar unidade'}));
 expect(screen.getByRole('dialog')).toHaveTextContent('2 filhos'); expect(screen.getByRole('dialog')).toHaveTextContent('0 escopos de vínculo ativos');
 fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await screen.findByText('Unidade salva.');
 expect(JSON.parse(String(calls.find(c=>c.init.method==='PATCH')?.init.body))).toEqual({name:'Canteiro Atualizado',parent_id:'parent-a',active:true,expected_version:3});
 expect(calls.some(c=>c.path.includes('exclude_descendants_of=node-a')&&c.path.includes('parent_for_kind=WORKSITE')&&c.path.includes('limit=20'))).toBe(true);
});
it('inactive unit can be activated with server decision and no permanent deletion', async () => {
 state.node={...node,active:false,allowed_actions:['edit','activate']}; state.nodes=[state.node]; await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'}));
 fireEvent.click(await screen.findByRole('button',{name:'Ativar unidade'})); await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeEnabled()); expect(screen.getByRole('dialog')).toHaveTextContent('Ativo'); expect(screen.queryByRole('button',{name:/excluir/i})).not.toBeInTheDocument();
 fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await screen.findByText('Unidade salva.'); expect(JSON.parse(String(calls.find(c=>c.init.method==='PATCH')?.init.body))).toEqual({active:true,expected_version:3});
});
it('409 then failed detail refresh cannot reuse stale version and cancellation restores focus', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'})); const trigger=await screen.findByRole('button',{name:'Inativar unidade'}); trigger.focus(); fireEvent.click(trigger); await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeEnabled());
 state.mutationStatus=409; state.detailStatus=503; fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'}));
 await within(screen.getByRole('dialog')).findByText(/Os dados foram alterados/); fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Atualizar dados'}));
 await waitFor(()=>expect(calls.filter(c=>c.path==='/organization/nodes/node-a').length).toBeGreaterThanOrEqual(2));
 expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeDisabled(); expect(screen.queryByText('Unidade salva.')).not.toBeInTheDocument();
 fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'}); expect(screen.queryByRole('dialog')).not.toBeInTheDocument(); expect(screen.getByRole('region',{name:'Detalhes da unidade'})).toHaveFocus();
});
it('structure handles loading, empty and safe error with retry', async () => {
 state.listStatus=503; await open('Estrutura'); expect(screen.getByText('Carregando estrutura…')).toBeVisible(); expect(await screen.findByRole('alert')).toHaveTextContent('Serviço temporariamente indisponível'); state.listStatus=200; state.nodes=[]; state.total=0;
 fireEvent.click(screen.getByRole('button',{name:'Tentar novamente'})); await screen.findByText('Nenhuma unidade encontrada neste contrato.');
});
it.each([403,404])('detail status %s discards old data and closes unsafe review', async status => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'})); fireEvent.click(await screen.findByRole('button',{name:'Inativar unidade'})); await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeEnabled());
 state.mutationStatus=409; state.detailStatus=status; fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'}));
 await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument()); expect(screen.queryByRole('button',{name:'Editar unidade'})).not.toBeInTheDocument();
});

it('cancel restores the available action trigger and traps keyboard focus', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'}));
 const trigger=await screen.findByRole('button',{name:'Inativar unidade'}); trigger.focus(); fireEvent.click(trigger);
 await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeEnabled());
 const dialog=screen.getByRole('dialog'), cancel=within(dialog).getByRole('button',{name:'Cancelar'}); cancel.focus(); fireEvent.keyDown(dialog,{key:'Tab'});
 expect(within(dialog).getByRole('button',{name:'Voltar aos campos'})).toHaveFocus();
 fireEvent.keyDown(dialog,{key:'Escape'}); expect(trigger).toHaveFocus(); expect(calls.some(c=>c.init.method==='PATCH')).toBe(false);
});
it('forbidden node mutation discards detail even if its follow-up read fails', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'})); fireEvent.click(await screen.findByRole('button',{name:'Inativar unidade'}));
 await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeEnabled());
 state.mutationStatus=403; state.detailStatus=503; fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'}));
 await screen.findByText('Serviço temporariamente indisponível. Tente novamente mais tarde.');
 expect(screen.queryByRole('button',{name:'Editar unidade'})).not.toBeInTheDocument(); expect(screen.queryByRole('heading',{name:'Canteiro Norte (NORTE)'})).not.toBeInTheDocument();
});
it('successful conflict recovery replaces node version and requires renewed review', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'})); fireEvent.click(await screen.findByRole('button',{name:'Inativar unidade'}));
 await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeEnabled()); state.mutationStatus=409;
 fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await within(screen.getByRole('dialog')).findByText(/Os dados foram alterados/);
 await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Atualizar dados'})).toBeEnabled()); state.node={...node,version:4,name:'Canteiro Revisado'}; state.mutationStatus=200;
 fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Atualizar dados'})); await screen.findByRole('button',{name:'Revisar unidade'});
 expect(screen.getByLabelText('Nome da unidade')).toHaveValue('Canteiro Revisado'); fireEvent.click(screen.getByRole('button',{name:'Revisar unidade'})); fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await screen.findByText('Unidade salva.');
 expect(JSON.parse(String(calls.filter(c=>c.init.method==='PATCH').at(-1)?.init.body)).expected_version).toBe(4);
});
it('inactivation review exposes server-proven active impact without hard-delete controls', async () => {
 state.node={...node,child_count:3,active_child_count:2,scope_membership_count:4}; state.nodes=[state.node];
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'})); fireEvent.click(await screen.findByRole('button',{name:'Inativar unidade'}));
 await waitFor(()=>expect(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})).toBeEnabled());
 expect(screen.getByRole('dialog')).toHaveTextContent('3 filhos diretos · 2 filhos ativos · 4 escopos de vínculo ativos');
 expect(screen.getByRole('dialog')).toHaveTextContent('Filhos ou escopos ativos impedem'); expect(screen.queryByRole('button',{name:/excluir/i})).not.toBeInTheDocument();
});
it('context-invalid structure read removes protected data through the real provider', async () => {
 await open('Estrutura'); await screen.findByText('Canteiro Norte'); const original=fetch;
 vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>url.startsWith('/api/organization/nodes?')?Promise.resolve(response({code:'CONTEXT_INVALID'},403)):original(url,init)));
 fireEvent.click(screen.getByRole('button',{name:'Pesquisar estrutura'}));
 await screen.findByRole('heading',{name:'Selecionar ambiente'}); expect(screen.queryByText('Canteiro Norte')).not.toBeInTheDocument(); expect(screen.queryByTestId('contract-context')).not.toBeInTheDocument(); expect(sessionStorage.getItem('hiatlas.access-context.v1')).toBeNull();
});
it('ending context aborts delayed detail and removes a reviewed structure form', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'})); fireEvent.click(await screen.findByRole('button',{name:'Editar unidade'}));
 await waitFor(()=>expect(screen.getByRole('button',{name:'Revisar unidade'})).toBeEnabled()); fireEvent.click(screen.getByRole('button',{name:'Revisar unidade'}));
 fireEvent.click(screen.getByRole('button',{name:'Trocar empresa/contrato'})); await screen.findByRole('heading',{name:'Selecionar ambiente'});
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument(); expect(calls.some(c=>c.init.method==='PATCH')).toBe(false);
 const original=fetch; let finish:((value:Response)=>void)|undefined; let signal:AbortSignal|null|undefined;
 // Restore only the opaque context ID, then defer the scoped detail request.
 sessionStorage.setItem('hiatlas.access-context.v1','scope-a');
 vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>url==='/api/organization/nodes/node-a'?new Promise<Response>(resolve=>{finish=resolve;signal=init?.signal;}):original(url,init)));
 const view=await import('@testing-library/react'); view.cleanup(); await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'})); await screen.findByText('Carregando unidade…');
 fireEvent.click(screen.getByRole('button',{name:'Trocar empresa/contrato'})); await screen.findByRole('heading',{name:'Selecionar ambiente'}); expect(signal?.aborted).toBe(true);
 await act(async()=>{finish!(response({...node,name:'Detalhe tardio A'}));}); expect(screen.queryByText('Detalhe tardio A')).not.toBeInTheDocument();
});
it('duplicate-code create conflict preserves draft and permits correction without an impossible detail refresh', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Nova unidade'}));
 fireEvent.change(screen.getByRole('combobox',{name:'Tipo de unidade'}),{target:{value:'WORKSITE'}}); fireEvent.change(screen.getByLabelText('Nome da unidade'),{target:{value:'Canteiro Leste'}}); fireEvent.change(screen.getByLabelText('Código'),{target:{value:'NORTE'}});
 fireEvent.click(screen.getByRole('button',{name:'Revisar unidade'})); state.mutationStatus=409; fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await within(screen.getByRole('dialog')).findByText(/Os dados foram alterados/);
 expect(await screen.findByLabelText('Código')).toHaveValue('NORTE'); expect(screen.getByLabelText('Nome da unidade')).toHaveValue('Canteiro Leste'); expect(screen.queryByRole('button',{name:'Atualizar dados'})).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText('Código'),{target:{value:'LESTE'}}); state.mutationStatus=200; fireEvent.click(screen.getByRole('button',{name:'Revisar unidade'})); fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'})); await screen.findByText('Unidade salva.');
 expect(JSON.parse(String(calls.filter(c=>c.path==='/organization/nodes'&&c.init.method==='POST').at(-1)?.init.body)).code).toBe('LESTE');
});
it('parent controls stay disabled until the initial editor detail is validated', async () => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Canteiro Norte'})); await screen.findByRole('button',{name:'Editar unidade'});
 const original=fetch; let finish:((value:Response)=>void)|undefined;
 vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>url==='/api/organization/nodes/node-a'?new Promise<Response>(resolve=>{finish=resolve;}):original(url,init)));
 fireEvent.click(screen.getByRole('button',{name:'Editar unidade'})); await within(screen.getByRole('dialog')).findByRole('option',{name:'Matriz (MATRIZ)'});
 // The parent lookup can finish before the independent current-detail query.
 await waitFor(()=>expect(calls.some(c=>c.path.includes('parent_for_kind=WORKSITE'))).toBe(true));
 expect(screen.getByRole('combobox',{name:'Unidade pai'})).toBeDisabled(); expect(screen.getByLabelText('Buscar unidade pai')).toBeDisabled(); expect(screen.getByRole('button',{name:'Pesquisar pais'})).toBeDisabled();
 await act(async()=>{finish!(response({...node,parent_id:null,parent_name:null,parent_code:null}));}); await waitFor(()=>expect(screen.getByRole('combobox',{name:'Unidade pai'})).toBeEnabled());
 fireEvent.change(screen.getByRole('combobox',{name:'Unidade pai'}),{target:{value:'parent-a'}}); expect(screen.getByRole('combobox',{name:'Unidade pai'})).toHaveValue('parent-a');
});
it.each(['CD-CWB','LOJA-BAURU','WS-OBRA-001'])('native creation input accepts stable approved hyphenated code %s', async code => {
 await open('Estrutura'); fireEvent.click(await screen.findByRole('button',{name:'Nova unidade'}));
 const field=screen.getByLabelText('Código') as HTMLInputElement; fireEvent.change(field,{target:{value:code}}); expect(field.checkValidity()).toBe(true);
});
