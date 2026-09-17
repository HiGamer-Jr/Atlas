import { expect, it } from 'vitest'
import { getExecutiveOverview } from './overviewData'

it('consolidates the reference panorama from the selected company units', () => {
  expect(getExecutiveOverview('Aurora Distribuição', 'Todas as unidades')).toEqual({
    excessCapital: 486000, potentialSavings: 124000, criticalProcesses: 3, attentionProcesses: 6,
    activePurchases: 128, pendingApprovals: 24, inventoryUnits: 42580, importsInTransit: 18,
    coverageDays: 47, leadTimeDays: 32, outsidePlanPercent: 14,
    monthlyPurchases: [320000, 410000, 390000, 520000, 550000, 650000],
    purchaseValue: 2840000, stockHealth: [84, 12, 4],
  })
})
it('recalculates amounts, rates and monthly purchases for a single unit', () => {
  const data = getExecutiveOverview('Aurora Distribuição', 'Matriz')!
  expect(data.purchaseValue).toBe(1420000)
  expect(data.monthlyPurchases).toEqual([160000,205000,195000,260000,275000,325000])
  expect(data.activePurchases).toBe(64)
  expect(data.excessCapital).toBe(243000)
  expect(data.coverageDays).toBe(44)
  expect(data.leadTimeDays).toBe(30)
  expect(data.outsidePlanPercent).toBe(12)
})
it('keeps another company separate from the Aurora reference', () => {
  const data = getExecutiveOverview('Horizonte Industrial', 'Todas as unidades')!
  expect(data.purchaseValue).toBe(1800000)
  expect(data.inventoryUnits).toBe(20000)
  expect(data.stockHealth).toEqual([90,8,2])
})
it.each([
  ['Horizonte Industrial', 'Loja Centro'],
  ['Empresa inexistente', 'Todas as unidades'],
  ['Aurora Distribuição', 'Unidade inexistente'],
])('returns no demonstration data for %s / %s', (company, unit) => {
  expect(getExecutiveOverview(company, unit)).toBeNull()
})
