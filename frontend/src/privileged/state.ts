import { createContext, useContext } from 'react';
import type { Grant, MaintenanceScope } from './types';
export type PrivilegedState = {
    grant: Grant | null;
    restoring: boolean;
    busy: boolean;
    error: unknown;
    start: (reason: string, reference: string | null) => Promise<void>;
    startMaintenance: (reason:string, reference:string, scopes:MaintenanceScope[]) => Promise<void>;
    end: () => Promise<void>;
    retry: () => void;
};
export const PrivilegedContext = createContext<PrivilegedState | null>(null);
export const usePrivileged = () => useContext(PrivilegedContext);
