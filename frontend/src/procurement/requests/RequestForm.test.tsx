import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {AuthContext,type Auth} from '../../auth/state';
import {Context,type ContextState} from '../../platform/state';
import {OperationalContext} from '../../operational/state';
import {ApiClient} from '../../api/client';
import {scope,request} from './fixtures';
import {parseRequest} from './validate';
import {RequestForm} from './RequestForm';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function mount(lost=false){const bodies:Record<string,unknown>[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{if(url==='/api/auth/csrf')return new Response(JSON.stringify({token:'csrf'}));bodies.push(JSON.parse(init.body as string));if(lost)throw new TypeError('lost response');return new Response(JSON.stringify(request()));}));const auth:Auth={api:new ApiClient(),user:{user_id:'user',display_name:'User',platform_role:null},loading:false,busy:false,error:null,login:async()=>{},logout:async()=>{},retry:()=>{}};const context:ContextState={selected:{id:'ctx',tenant_name:'Tenant',contract_id:'contract',contract_code:'CTR',environment:'TEST',expires_at:'2099-01-01',capabilities:[]},loading:false,busy:false,error:null,recovering:false,select:async()=>{},clear:async()=>{},retry:()=>{}};render(<AuthContext.Provider value={auth}><Context.Provider value={context}><OperationalContext.Provider value={{status:'ready',scope}}><RequestForm draft={parseRequest(request(),{tenantId:'tenant',contractId:'contract'})} onSaved={()=>{}}/></OperationalContext.Provider></Context.Provider></AuthContext.Provider>);return bodies;}
it('draft edits preserve existing item IDs and keep new items without server IDs',async()=>{const bodies=mount();fireEvent.change(screen.getByLabelText('Quantidade do item 1'),{target:{value:'1.000001'}});fireEvent.click(screen.getByRole('button',{name:'Adicionar item'}));fireEvent.change(screen.getByLabelText('Descrição do item 2'),{target:{value:'Second actual need'}});fireEvent.change(screen.getByLabelText('Quantidade do item 2'),{target:{value:'2.5'}});fireEvent.click(screen.getByRole('button',{name:'Salvar rascunho'}));await waitFor(()=>expect(bodies).toHaveLength(1));expect(bodies[0].expected_version).toBe(1);expect(bodies[0].items).toEqual([{id:'item',description:'Concrete need',specification:'',requested_quantity:'1.000001',uom_code:'UN'},{description:'Second actual need',specification:'',requested_quantity:'2.5',uom_code:'UN'}]);});
it('package UOM requires real content specification before saving',async()=>{const bodies=mount();fireEvent.change(screen.getByLabelText('Unidade de medida do item 1'),{target:{value:'CX'}});fireEvent.click(screen.getByRole('button',{name:'Salvar rascunho'}));expect(await screen.findByRole('alert')).toHaveTextContent(/conteúdo de embalagem/);expect(bodies).toHaveLength(0);});


it('lost server response reports connectivity and permits the same draft retry',async()=>{mount(true);fireEvent.click(screen.getByRole('button',{name:'Salvar rascunho'}));expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar ao serviço');expect(screen.getByRole('button',{name:'Salvar rascunho'})).toBeEnabled();});


it('form allows server-valid supplementary Unicode without a UTF16 maxlength cap',async()=>{
 const bodies=mount();
 const title=screen.getByLabelText('Título') as HTMLInputElement;
 const notes=screen.getByLabelText('Observações') as HTMLTextAreaElement;
 expect(title.maxLength).toBe(-1);
 expect(notes.maxLength).toBe(-1);
 fireEvent.change(title,{target:{value:'😀'.repeat(200)}});
 fireEvent.change(notes,{target:{value:'🚀'.repeat(4000)}});
 expect(title.checkValidity()).toBe(true);
 expect(notes.checkValidity()).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Salvar rascunho'}));
 await waitFor(()=>expect(bodies).toHaveLength(1));
 expect(bodies[0].title).toBe('😀'.repeat(200));
 expect(bodies[0].notes).toBe('🚀'.repeat(4000));
});
it.each([['Título','😀'.repeat(201)],['Observações','🚀'.repeat(4001)],['Descrição do item 1','😀'.repeat(2001)],['Especificação do item 1','🚀'.repeat(4001)]])('form rejects above codepoint bound for %s before transport',async(label,text)=>{
 const bodies=mount();
 const input=screen.getByLabelText(label) as HTMLInputElement;
 fireEvent.change(input,{target:{value:text}});
 expect(input.checkValidity()).toBe(false);
 // Even direct submission bypassing browser constraints must remain bounded.
 fireEvent.submit(screen.getByRole('button',{name:'Salvar rascunho'}).closest('form')!);
 expect(await screen.findByRole('alert')).toHaveTextContent(/caracteres/);
 expect(bodies).toHaveLength(0);
});


it('removing an invalid unsaved item clears browser validity on a reused input',async()=>{
 const bodies=mount();
 fireEvent.click(screen.getByRole('button',{name:'Adicionar item'}));
 fireEvent.click(screen.getByRole('button',{name:'Adicionar item'}));
 fireEvent.change(screen.getByLabelText('Descrição do item 2'),{target:{value:'x'.repeat(2001)}});
 fireEvent.change(screen.getByLabelText('Descrição do item 3'),{target:{value:'Remaining actual need'}});
 fireEvent.change(screen.getByLabelText('Quantidade do item 3'),{target:{value:'1'}});
 fireEvent.click(screen.getByRole('button',{name:'Remover item 2'}));
 expect((screen.getByLabelText('Descrição do item 2') as HTMLTextAreaElement).checkValidity()).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Salvar rascunho'}));
 await waitFor(()=>expect(bodies).toHaveLength(1));
});
