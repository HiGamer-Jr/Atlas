/** Fictional first-semester 2026 snapshots. No live operational integration. */
type UnitSnapshot = {
  company: string
  unit: string
  excessCapital: number
  potentialSavings: number
  criticalProcesses: number
  attentionProcesses: number
  activePurchases: number
  pendingApprovals: number
  importsInTransit: number
  coverageDays: number
  leadTimeDays: number
  outsidePlanValue: number
  monthlyPurchases: number[]
  stockUnits: [balanced: number, attention: number, critical: number]
}

const snapshots: UnitSnapshot[] = [
  {
    company: 'Aurora Distribuição', unit: 'Matriz',
    excessCapital: 243000, potentialSavings: 62000, criticalProcesses: 1, attentionProcesses: 3,
    activePurchases: 64, pendingApprovals: 12, importsInTransit: 9,
    coverageDays: 44, leadTimeDays: 30, outsidePlanValue: 170400,
    monthlyPurchases: [160000,205000,195000,260000,275000,325000], stockUnits: [17884,2555,851],
  },
  {
    company: 'Aurora Distribuição', unit: 'CD Sul',
    excessCapital: 145800, potentialSavings: 37200, criticalProcesses: 1, attentionProcesses: 2,
    activePurchases: 38, pendingApprovals: 7, importsInTransit: 5,
    coverageDays: 54, leadTimeDays: 36, outsidePlanValue: 153360,
    monthlyPurchases: [96000,123000,117000,156000,165000,195000], stockUnits: [10730,1533,511],
  },
  {
    company: 'Aurora Distribuição', unit: 'Loja Centro',
    excessCapital: 97200, potentialSavings: 24800, criticalProcesses: 1, attentionProcesses: 1,
    activePurchases: 26, pendingApprovals: 5, importsInTransit: 4,
    coverageDays: 44, leadTimeDays: 31, outsidePlanValue: 73840,
    monthlyPurchases: [64000,82000,78000,104000,110000,130000], stockUnits: [7153,1022,341],
  },
  {
    company: 'Horizonte Industrial', unit: 'Matriz',
    excessCapital: 180000, potentialSavings: 56000, criticalProcesses: 1, attentionProcesses: 2,
    activePurchases: 72, pendingApprovals: 8, importsInTransit: 6,
    coverageDays: 38, leadTimeDays: 28, outsidePlanValue: 180000,
    monthlyPurchases: [220000,260000,280000,310000,350000,380000], stockUnits: [18000,1600,400],
  },
]

const inventory = (snapshot: UnitSnapshot) => snapshot.stockUnits.reduce((sum, value) => sum + value, 0)

export function getExecutiveOverview(company: string, unit: string) {
  const selected = snapshots.filter(snapshot => snapshot.company === company &&
    (unit === 'Todas as unidades' || snapshot.unit === unit))
  if (!selected.length) return null

  const sum = (value: (snapshot: UnitSnapshot) => number) => selected.reduce((total, snapshot) => total + value(snapshot), 0)
  const inventoryUnits = sum(inventory)
  const activePurchases = sum(snapshot => snapshot.activePurchases)
  const monthlyPurchases = Array.from({length: 6}, (_, month) => sum(snapshot => snapshot.monthlyPurchases[month]))
  const purchaseValue = monthlyPurchases.reduce((total, value) => total + value, 0)
  const balanced = Math.round(sum(snapshot => snapshot.stockUnits[0]) / inventoryUnits * 100)
  const attention = Math.round(sum(snapshot => snapshot.stockUnits[1]) / inventoryUnits * 100)

  return {
    excessCapital: sum(snapshot => snapshot.excessCapital),
    potentialSavings: sum(snapshot => snapshot.potentialSavings),
    criticalProcesses: sum(snapshot => snapshot.criticalProcesses),
    attentionProcesses: sum(snapshot => snapshot.attentionProcesses),
    activePurchases,
    pendingApprovals: sum(snapshot => snapshot.pendingApprovals),
    inventoryUnits,
    importsInTransit: sum(snapshot => snapshot.importsInTransit),
    // Weight coverage by stock units, lead time by purchases, and unplanned share by spend.
    coverageDays: Math.round(sum(snapshot => snapshot.coverageDays * inventory(snapshot)) / inventoryUnits),
    leadTimeDays: Math.round(sum(snapshot => snapshot.leadTimeDays * snapshot.activePurchases) / activePurchases),
    outsidePlanPercent: Math.round(sum(snapshot => snapshot.outsidePlanValue) / purchaseValue * 100),
    monthlyPurchases,
    purchaseValue,
    stockHealth: [balanced, attention, 100 - balanced - attention],
  }
}
