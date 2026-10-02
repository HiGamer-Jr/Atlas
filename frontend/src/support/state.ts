import {createContext,useContext} from 'react';
import type {SupportSession} from './types';
export type SupportState={session:SupportSession|null;revision:number;busy:boolean;restoring:boolean;error:unknown;start:(membership:string,reason:string,reference:string|null)=>Promise<void>;end:()=>Promise<void>;retry:()=>void;invalidate:()=>void};
export const SupportContext=createContext<SupportState|null>(null);
export function useSupport(){return useContext(SupportContext);}
