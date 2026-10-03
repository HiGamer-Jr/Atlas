import {createContext,useContext,type ComponentType} from 'react';
export type MaintenanceAction={action_code:string;label:string;entity_type:'organization_node';can_correct:boolean;can_reprocess:boolean};
export type MaintenanceAdapter={actionCode:string;entityType:'organization_node';Form:ComponentType<{action:MaintenanceAction;entityId:string}>};
// Only explicit code adapters expose forms. Production has no adapters.
export const MaintenanceAdapters=createContext<readonly MaintenanceAdapter[]>(Object.freeze([]));
export const useMaintenanceAdapters=()=>useContext(MaintenanceAdapters);
