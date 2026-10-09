import {moduleCodes, nodeKinds, type OperationalScope} from './types';
const invalid = (): never => { throw new Error('OPERATIONAL_SCOPE_INVALID'); };
function object(value: unknown): Record<string, unknown> {
 if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
 return value as Record<string, unknown>;
}
function text(value: unknown): string {
 if (typeof value !== 'string' || !value.trim()) return invalid();
 return value;
}
function array(value: unknown): unknown[] {
 if (!Array.isArray(value)) return invalid();
 return value;
}
const capabilities = new Set(['memberships.read','roles.read','roles.manage','finance.read','fiscal.read','datahub.read','datahub.template.download','datahub.import','datahub.export', ...['products','partners','demands','stock_positions','comex_references','financial_forecasts'].flatMap(dataset => ['read','import','export'].map(operation => `datahub.${dataset}.${operation}`))]);
// Wire validation only: mirrors the physical schema, never grants access.
const children: Record<string, readonly string[]> = {
 COMPANY: nodeKinds.filter(kind => kind !== 'COMPANY'),
 BRANCH: ['UNIT','STORE','DISTRIBUTION_CENTER','WAREHOUSE','OFFICE','WORKSITE'],
 UNIT: ['UNIT','STORE','DISTRIBUTION_CENTER','WAREHOUSE','OFFICE','WORKSITE'],
 STORE: ['WAREHOUSE','OFFICE'], DISTRIBUTION_CENTER: ['WAREHOUSE','OFFICE'],
 WAREHOUSE: ['OFFICE'], WORKSITE: ['OFFICE'], OFFICE: [],
};
/** Validates wire shape for UX; this function grants no backend authority. */
export function parseOperationalScope(value: unknown, expectedContextId: string): OperationalScope {
 const root = object(value);
 if (root.schema_version !== 1 || root.context_id !== expectedContextId || !expectedContextId) return invalid();
 const tenant = object(root.tenant), contract = object(root.contract);
 text(tenant.id); text(tenant.name);
 for (const key of ['id','code','name','environment']) text(contract[key]);
 if (!['TEST','PRODUCTION','STAGING'].includes(text(contract.environment))) return invalid();
 if (root.actor_kind === 'INTERNAL') {
  if (root.customer_scope !== null) return invalid();
  return structuredClone(value) as OperationalScope;
 }
 if (root.actor_kind !== 'TENANT') return invalid();
 const customer = object(root.customer_scope), role = object(customer.role), policy = object(customer.unit_scope);
 for (const key of ['id','code','name']) text(role[key]);
 if (!['ALL','RESTRICTED'].includes(text(policy.mode))) return invalid();
 const nodes = array(customer.organization_nodes);
 if (nodes.length > 1000) return invalid();
 const graph = new Map<string, Record<string, unknown>>();
 for (const value of nodes) {
  const node = object(value), id = text(node.id);
  text(node.code); text(node.name);
  if (graph.has(id) || !nodeKinds.includes(node.kind as typeof nodeKinds[number]) || (node.parent_id !== null && typeof node.parent_id !== 'string')) return invalid();
  graph.set(id, node);
 }
 for (const node of graph.values()) {
  let current: Record<string, unknown> | undefined = node;
  const visited = new Set<string>();
  while (current) {
   const id = text(current.id);
   if (visited.has(id)) return invalid();
   visited.add(id);
   if (current.parent_id === null) break;
   const parent = graph.get(text(current.parent_id));
   if (!parent || !children[text(parent.kind)]?.includes(text(current.kind))) return invalid();
   current = parent;
  }
 }
 const seen = new Set(), enabled = new Set<string>();
 for (const value of array(customer.modules)) {
  const module = object(value);
  if (!moduleCodes.includes(module.code as typeof moduleCodes[number]) || seen.has(module.code) || module.contracted !== true || typeof module.active !== 'boolean' || typeof module.operational_available !== 'boolean') return invalid();
  seen.add(module.code); text(module.label);
  if (module.operational_available && (!module.active || module.code !== 'DATAHUB')) return invalid();
  if (module.active) enabled.add(text(module.code));
 }
 const caps = array(customer.capabilities);
 if (new Set(caps).size !== caps.length || caps.some(code => !capabilities.has(text(code)))) return invalid();
 const datahubAvailable = array(customer.modules).some(value => { const module = object(value); return module.code === 'DATAHUB' && module.operational_available === true; });
 const datasetModules: Record<string, string> = {demands:'PROCUREMENT',stock_positions:'INVENTORY',comex_references:'COMEX',financial_forecasts:'FINANCE'};
 for (const value of caps) {
  const code = text(value);
  if (code.startsWith('datahub.') && !datahubAvailable) return invalid();
  const dataset = code.split('.')[1];
  if (code.startsWith('datahub.') && datasetModules[dataset] && !enabled.has(datasetModules[dataset])) return invalid();
  if (code.startsWith('datahub.') && ['demands','stock_positions','financial_forecasts'].includes(dataset) && nodes.length === 0) return invalid();
  // These sensitive domains have no implemented operational module in V1.
  if (code === 'finance.read' || code === 'fiscal.read' || code.startsWith('datahub.financial_forecasts.')) return invalid();
 }
 return structuredClone(value) as OperationalScope;
}
