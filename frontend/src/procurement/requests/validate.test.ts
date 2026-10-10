import {expect,it} from 'vitest';
import {parseRequest,parseRequestPage,parseRequestHistory} from './validate';
import {request} from './fixtures';
const expected={tenantId:'tenant',contractId:'contract'};
it('keeps exact decimals and server provenance',()=>{expect(parseRequest(request(),expected).items[0].requested_quantity).toBe('0.000001');});
it.each([ {status:'UNKNOWN'}, {tenant_id:'other'}, {contract_id:'other'}, {version:0}, {approval_mode:'UNKNOWN'}, {approval_decision_kind:'FAKE'}, {items:[{...request().items[0],requested_quantity:0.000001}]}, {items:[{...request().items[0],uom_code:'FAKE'}]} ])('unknown_state_module_contradiction_closes_controls %s',patch=>{expect(()=>parseRequest({...request(),...patch},expected)).toThrow();});
it('validates all list entries and private history evidence',()=>{expect(parseRequestPage({items:[request()],total:1,limit:50,next_cursor:null},expected).total).toBe(1);expect(()=>parseRequestPage({items:[{...request(),contract_id:'other'}],total:1,limit:50,next_cursor:null},expected)).toThrow();expect(()=>parseRequestHistory({items:[{action:'fake'}],total:1,limit:50,next_cursor:null},expected)).toThrow();});
