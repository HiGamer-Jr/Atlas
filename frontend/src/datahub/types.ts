export type Template = {id:string;version:number;label:string;available:boolean;can_download:boolean;can_import:boolean;can_export:boolean;datasets:string[]};
export type Catalog = {items:Template[];profile:string;units:{id:string;code:string;name:string}[]};
export type ImportSummary={unit_scope:string[];id:string;status:'RECEIVED'|'VALIDATING'|'READY_FOR_CONFIRMATION'|'REJECTED'|'EXPIRED'|'COMMITTED'|'FAILED';version:number;template_id:string;template_version:number;row_count:number;error_count:number;warning_count:number;inserted_count:number;skipped_count:number;preview_expires_at:string;result_code:string};
export type ImportDetail=ImportSummary&{filename:string;created_at:string;committed_at:string|null;actor_user_id:string};
export type Page<T>={items:T[];total:number;page:number;page_size:number};
export type ImportRow={id:string;dataset:string;sheet:string;source_row:number;validation_status:string;payload:Record<string,string|boolean|number|null>};
export type Issue={sheet:string|null;source_row:number|null;column:string|null;severity:'ERROR'|'WARNING';code:string;message:string};
