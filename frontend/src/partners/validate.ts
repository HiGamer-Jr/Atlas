import type {PartnerAvailabilityDTO,PartnerAccessOptionsDTO,TokenInspectionDTO} from './types';
function closed(value: unknown, keys: string[]): value is Record<string,unknown> {
 return value !== null && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === keys.length && keys.every(key=>Object.hasOwn(value,key));
}
export function parsePartnerAvailability(value: unknown): PartnerAvailabilityDTO | null {
 if (!closed(value,['schema_version','status','code']) || value.schema_version!==1 || value.status!=='DOMAIN_UNAVAILABLE' || value.code!=='PARTNER_DOMAIN_UNAVAILABLE') return null;
 return {schema_version:1,status:'DOMAIN_UNAVAILABLE',code:'PARTNER_DOMAIN_UNAVAILABLE'};
}
export function parsePartnerAccessOptions(value: unknown): PartnerAccessOptionsDTO | null {
 return Array.isArray(value) && value.length===0 && Object.keys(value).length===0 ? [] : null;
}
export function parseTokenInspection(value: unknown, invite: boolean): TokenInspectionDTO | null {
 if(!closed(value,['target_kind','requires_authentication']) || typeof value.requires_authentication!=='boolean')return null;
 const target=value.target_kind;
 if(invite ? target!=='INTERNAL' && target!=='TENANT' && target!=='PARTNER' : target!=='USER')return null;
 return {target_kind:target as TokenInspectionDTO['target_kind'],requires_authentication:value.requires_authentication};
}
