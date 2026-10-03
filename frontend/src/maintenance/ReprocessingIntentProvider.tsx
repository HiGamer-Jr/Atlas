import {useState,type ReactNode} from 'react';
import {IntentContext,type ReprocessingIntent} from './reprocessing-state';
/** Memory only. Shell revalidation may unmount its workspace but never this grant-scoped provider. */
export default function ReprocessingIntentProvider({children}:{children:ReactNode}){
 const [intent,setIntent]=useState<ReprocessingIntent|null>(null);
 return <IntentContext.Provider value={{intent,setIntent}}>{children}</IntentContext.Provider>;
}
