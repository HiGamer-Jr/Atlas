import {createContext,useContext} from 'react';
import type {OperationalScope} from './types';
export type OperationalScopeState = {status:'idle'|'loading';scope:null}|{status:'unavailable';scope:null;errorCode:string}|{status:'ready';scope:OperationalScope};
export const OperationalContext=createContext<OperationalScopeState|null>(null);
export function useOperationalScope():OperationalScopeState{const state=useContext(OperationalContext);if(!state)throw new Error('OperationalScopeProvider required');return state;}
