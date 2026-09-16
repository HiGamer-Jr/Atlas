import { describe, expect, it } from 'vitest'
import { demoProjects, getProjectMetrics } from './projectCatalog'

describe('project catalog', () => {
  it('calculates portfolio metrics from all projects, including planned budgets', () => {
    expect(getProjectMetrics(demoProjects)).toEqual({
      active: 4,
      atRisk: 2,
      delayed: 1,
      totalRevisedBudget: 12370000,
      totalProjectedCost: 12610000,
    })
  })
  it('returns zero metrics for an empty context', () => {
    expect(getProjectMetrics([])).toEqual({active: 0, atRisk: 0, delayed: 0, totalRevisedBudget: 0, totalProjectedCost: 0})
  })
  it('does not count completed projects as active', () => {
    expect(getProjectMetrics([{...demoProjects[0], status: 'Concluída'}]).active).toBe(0)
  })
})
