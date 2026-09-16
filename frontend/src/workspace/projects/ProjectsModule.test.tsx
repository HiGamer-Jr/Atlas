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

import { afterEach } from 'vitest'
import { cleanup, render, screen, within, fireEvent } from '@testing-library/react'
import ProjectsModule from './ProjectsModule'

afterEach(cleanup)
const context = {company: 'Aurora Distribuição', unit: 'Todas as unidades', section: 'Visão Geral'}

it('shows only projects for the selected company with demonstration identification', () => {
  render(<ProjectsModule {...context} />)
  expect(screen.getByRole('heading', {name: 'Obras & Projetos'})).toBeInTheDocument()
  expect(screen.getByText('Ampliação CD Bauru')).toBeInTheDocument()
  expect(screen.queryByText('Implantação Centro Logístico')).not.toBeInTheDocument()
  expect(screen.getByText(/Foundation.*dados demonstrativos/i)).toBeInTheDocument()
})
it('shows health indicators calculated for the current company', () => {
  render(<ProjectsModule {...context} />)
  for (const [label, value] of [['Obras ativas', '3'], ['Em risco', '2'], ['Atrasadas', '0'], ['Projeção financeira', 'R$ 7.130.000']]) {
    const card = screen.getAllByText(label).find(element => element.parentElement?.tagName === 'ARTICLE')!.parentElement!
    expect(within(card).getByText(value)).toBeInTheDocument()
  }
})
it('prioritizes the portfolio list when its section is selected', () => {
  render(<ProjectsModule {...context} section="Portfólio de Obras" />)
  expect(screen.getByRole('heading', {name: 'Portfólio de Obras'})).toBeInTheDocument()
  expect(screen.queryByText('Obras ativas')).not.toBeInTheDocument()
  expect(screen.getByRole('button', {name: /Ampliação CD Bauru/})).toBeInTheDocument()
})
it('shows zero metrics and an empty state for a unit without projects', () => {
  render(<ProjectsModule {...context} unit="Matriz" />)
  expect(screen.getByText('Nenhuma obra encontrada neste contexto.')).toBeInTheDocument()
  expect(screen.queryByRole('button', {name: /Ampliação CD Bauru/})).not.toBeInTheDocument()
  expect(screen.getByText('R$ 0')).toBeInTheDocument()
})
it('opens project detail and returns to the portfolio', () => {
  render(<ProjectsModule {...context} />)
  fireEvent.click(screen.getByRole('button', {name: /Ampliação CD Bauru/}))
  expect(screen.getByRole('heading', {name: 'Ampliação CD Bauru'})).toBeInTheDocument()
  for (const name of ['Cronograma', 'Orçamento', 'Gestão']) {
    expect(screen.getByRole('heading', {name})).toBeInTheDocument()
  }
  expect(screen.getByText('+8 dias')).toBeInTheDocument()
  expect(screen.getAllByText('R$ 2.780.000')).toHaveLength(2)
  expect(screen.getByText('42%')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', {name: /Voltar ao portfólio/}))
  expect(screen.getByRole('button', {name: /Ampliação CD Bauru/})).toBeInTheDocument()
})
