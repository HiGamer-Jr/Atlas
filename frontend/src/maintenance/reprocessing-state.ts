import {createContext,useContext} from 'react';
import type {ProcessingRun} from './types';
export type ReprocessingCommand={reason:string;reference:string|null;idempotency_key:string;expected_version:number};
export type ReprocessingIntent={source:ProcessingRun;command:ReprocessingCommand;submitted:boolean};
export const IntentContext=createContext<{intent:ReprocessingIntent|null;setIntent:(intent:ReprocessingIntent|null)=>void}|null>(null);
export function useReprocessingIntent(){const state=useContext(IntentContext);if(!state)throw new Error('ReprocessingIntentProvider required');return state;}
