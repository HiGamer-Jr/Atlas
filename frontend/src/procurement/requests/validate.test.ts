import {expect,it} from 'vitest';
import {parseRequest,parseRequestPage,parseRequestHistory} from './validate';
import {request} from './fixtures';
const expected={tenantId:'tenant',contractId:'contract'};
it('keeps exact decimals and server provenance',()=>{expect(parseRequest(request(),expected).items[0].requested_quantity).toBe('0.000001');});
it.each([ {status:'UNKNOWN'}, {tenant_id:'other'}, {contract_id:'other'}, {version:0}, {approval_mode:'UNKNOWN'}, {approval_decision_kind:'FAKE'}, {items:[{...request().items[0],requested_quantity:0.000001}]}, {items:[{...request().items[0],uom_code:'FAKE'}]} ])('unknown_state_module_contradiction_closes_controls %s',patch=>{expect(()=>parseRequest({...request(),...patch},expected)).toThrow();});
it('validates all list entries and private history evidence',()=>{expect(parseRequestPage({items:[request()],total:1,limit:50,next_cursor:null},expected).total).toBe(1);expect(()=>parseRequestPage({items:[{...request(),contract_id:'other'}],total:1,limit:50,next_cursor:null},expected)).toThrow();expect(()=>parseRequestHistory({items:[{action:'fake'}],total:1,limit:50,next_cursor:null},expected)).toThrow();});


// Serialized from the actual Python command and public response schemas.
import unicodeWire from './unicode-wire.json';
const unicodeScope = {tenantId: unicodeWire.request.tenant_id, contractId: unicodeWire.request.contract_id};
it('accepts backend-valid supplementary title and private note at codepoint limits', () => {
 expect(parseRequestPage({items:[unicodeWire.request],total:1,limit:50,next_cursor:null},unicodeScope).items[0].title).toBe('😀'.repeat(200));
});
it('accepts backend-valid supplementary private note at codepoint limit', () => {
 expect(parseRequestHistory(unicodeWire.history,unicodeScope).items[0].payload.text).toBe('🚀'.repeat(4000));
});
it.each(['😀'.repeat(201), 123, null, '\ud800'])('rejects overlimit and malformed Unicode title %s', title => {
 expect(() => parseRequest({...unicodeWire.request,notes:"",title},unicodeScope)).toThrow('PURCHASE_REQUEST_INVALID');
});
it.each(['🚀'.repeat(4001), 123, null, '\udc00'])('rejects overlimit and malformed private note %s', text => {
 const history = structuredClone(unicodeWire.history);
 Object.assign(history.items[0].payload,{text});
 expect(() => parseRequestHistory(history,unicodeScope)).toThrow('PURCHASE_REQUEST_INVALID');
});
