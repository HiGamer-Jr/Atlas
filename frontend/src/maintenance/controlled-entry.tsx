// Isolated controlled factory entry. The normal main.tsx never imports this module.
import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import '../index.css';
import App from '../App';
import FixtureRenameForm from './FixtureRenameForm';
import {MaintenanceAdapters,type MaintenanceAdapter} from './registry';
const adapters:readonly MaintenanceAdapter[]=Object.freeze([{actionCode:'FIXTURE_NODE_RENAME',entityType:'organization_node',Form:FixtureRenameForm}]);
createRoot(document.getElementById('root')!).render(<StrictMode><MaintenanceAdapters.Provider value={adapters}><App/></MaintenanceAdapters.Provider></StrictMode>);
