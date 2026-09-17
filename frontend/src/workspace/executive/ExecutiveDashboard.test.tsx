import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import ExecutiveDashboard from './ExecutiveDashboard'

afterEach(cleanup)
const props = {company: 'Aurora Distribuição', unit: 'Todas as unidades', profileName: 'Diretoria'}

it('presents the reference indicators with explicit demonstration and period labels', () => {
  render(<ExecutiveDashboard {...props} />)
  expect(screen.getByRole('heading', {name: 'Panorama executivo.'})).toBeInTheDocument()
  expect(screen.getByText('Diretoria')).toBeInTheDocument()
  expect(screen.getByText(/1º semestre de 2026/)).toBeInTheDocument()
  expect(screen.getByText(/Dados fictícios.*sem atualização ao vivo/)).toBeInTheDocument()
  const cards = screen.getByRole('region', {name: 'Indicadores executivos'})
  for (const [label, value] of [
    ['Capital em excesso de estoque', 'R$ 486 mil'], ['Processos em risco', '9'],
    ['Economia/ganho identificado', 'R$ 124 mil'], ['Cobertura média', '47 dias'],
    ['Compras em andamento', '128'], ['Valor em compras', 'R$ 2,84 mi'],
    ['Estoque consolidado', '42.580 un.'], ['Importações em trânsito', '18'],
    ['Lead time', '32 dias'], ['Compras fora do planejado', '14%'],
  ]) expect(within(within(cards).getByRole('article', {name:label})).getByText(value)).toBeInTheDocument()
})
it('shows readable monthly purchases and stock health, without relying on color alone', () => {
  render(<ExecutiveDashboard {...props} />)
  const chart = screen.getByRole('list', {name:'Compras realizadas por mês em milhares de reais'})
  expect(within(chart).getAllByRole('listitem')).toHaveLength(6)
  expect(within(chart).getByText('Jan')).toBeInTheDocument()
  expect(within(chart).getByText('650')).toBeInTheDocument()
  const health = screen.getByRole('region', {name:'Saúde do estoque'})
  expect(health).toHaveTextContent('84% equilibrado')
  expect(health).toHaveTextContent('12% atenção')
  expect(health).toHaveTextContent('4% crítico')
})
it('explains current priorities and next steps for coordination', () => {
  render(<ExecutiveDashboard {...props} profileName="Coordenação" />)
  expect(screen.getByText('Coordenação')).toBeInTheDocument()
  const priorities = screen.getByRole('region', {name:'O que precisa da sua atenção'})
  expect(priorities).toHaveTextContent('3 processos críticos')
  expect(priorities).toHaveTextContent('R$ 486 mil acima da cobertura de referência')
  expect(priorities).toHaveTextContent('84% do estoque em equilíbrio')
  expect(within(priorities).getAllByText('Próximo passo:')).toHaveLength(3)
})
it('updates indicators and priorities when unit or company changes, and clears missing contexts', () => {
  const {rerender} = render(<ExecutiveDashboard {...props} />)
  rerender(<ExecutiveDashboard {...props} unit="Matriz" />)
  expect(screen.queryByText('R$ 486 mil')).not.toBeInTheDocument()
  expect(screen.getByText('R$ 243 mil')).toBeInTheDocument()
  rerender(<ExecutiveDashboard {...props} company="Horizonte Industrial" />)
  expect(screen.getByText('R$ 180 mil')).toBeInTheDocument()
  expect(screen.getByRole('region', {name:'Saúde do estoque'})).toHaveTextContent('90% equilibrado')
  rerender(<ExecutiveDashboard {...props} company="Horizonte Industrial" unit="Loja Centro" />)
  expect(screen.getByText('Sem dados demonstrativos neste contexto.')).toBeInTheDocument()
  expect(screen.queryByRole('region', {name:'Indicadores executivos'})).not.toBeInTheDocument()
  expect(screen.queryByRole('region', {name:'O que precisa da sua atenção'})).not.toBeInTheDocument()
})
