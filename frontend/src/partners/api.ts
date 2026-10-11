import type {ApiClient} from '../api/client';
import type {PartnerAvailabilityDTO,PartnerAccessOptionsDTO} from './types';
import {parsePartnerAvailability,parsePartnerAccessOptions} from './validate';
export async function fetchPartnerAvailability(client: ApiClient, signal: AbortSignal): Promise<PartnerAvailabilityDTO> {
 const result=parsePartnerAvailability(await client.request<unknown>('/partner/availability',{contextId:null,signal}));
 if(!result)throw new Error('Invalid partner availability contract');
 return result;
}
export async function fetchPartnerAccessOptions(client: ApiClient, signal: AbortSignal): Promise<PartnerAccessOptionsDTO> {
 const result=parsePartnerAccessOptions(await client.request<unknown>('/partner/access-options',{contextId:null,signal}));
 if(!result)throw new Error('Invalid partner access options contract');
 return result;
}
