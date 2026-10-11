/** V1 deliberately exposes no operational catalog or authority. */
export type PartnerAvailabilityDTO = {schema_version: 1; status: 'DOMAIN_UNAVAILABLE'; code: 'PARTNER_DOMAIN_UNAVAILABLE'};
export type PartnerAccessOptionsDTO = [];
export type InviteTargetKind = 'INTERNAL' | 'TENANT' | 'PARTNER';
export type TokenInspectionDTO = {target_kind: InviteTargetKind | 'USER'; requires_authentication: boolean};
