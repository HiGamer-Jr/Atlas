export const nodeKinds = ['COMPANY','BRANCH','UNIT','STORE','DISTRIBUTION_CENTER','WAREHOUSE','OFFICE','WORKSITE'] as const;
export const moduleCodes = ['PROCUREMENT','COMEX','INVENTORY','FINANCE','PROJECTS','DATAHUB'] as const;
export type ScopeNode = {id:string;code:string;name:string;kind:typeof nodeKinds[number];parent_id:string|null};
export type ScopeModule = {code:typeof moduleCodes[number];label:string;contracted:true;active:boolean;operational_available:boolean};
export type CustomerScope = {role:{id:string;code:string;name:string};unit_scope:{mode:'ALL'|'RESTRICTED'};organization_nodes:ScopeNode[];modules:ScopeModule[];capabilities:string[]};
type Base = {schema_version:1;context_id:string;tenant:{id:string;name:string};contract:{id:string;code:string;name:string;environment:string}};
export type OperationalScope = Base & ({actor_kind:'TENANT';customer_scope:CustomerScope}|{actor_kind:'INTERNAL';customer_scope:null});
