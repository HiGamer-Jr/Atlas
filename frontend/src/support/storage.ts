export const SUPPORT_KEY='hiatlas.support-session.v1';
export function readSupport(){try{return sessionStorage.getItem(SUPPORT_KEY);}catch{return null;}}
export function storeSupport(id:string|null){try{if(id)sessionStorage.setItem(SUPPORT_KEY,id);else sessionStorage.removeItem(SUPPORT_KEY);}catch{/* Opaque reference is optional; parent server discovery also restores. */}}
