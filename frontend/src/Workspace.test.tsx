import { render, screen, fireEvent, cleanup, within } from "@testing-library/react"
import { afterEach, expect, it } from "vitest"
import App from "./App"
afterEach(() => { cleanup(); localStorage.clear() })
function enter(profile = "administrador") {
 render(<App />)
 fireEvent.change(screen.getByLabelText(/perfil de acesso/i), {target:{value:profile}})
 fireEvent.click(screen.getByRole("button", {name:/entrar no hiatlas/i}))
}
it("navigates to a submodule and filters records by search", () => {
 enter()
 fireEvent.click(screen.getByRole("button", {name:"Compras"}))
 fireEvent.click(within(screen.getByRole("navigation")).getByRole("button", {name:"Cotações"}))
 expect(screen.getByRole("heading", {name:"Cotações"})).toBeInTheDocument()
 fireEvent.change(screen.getByLabelText("Buscar registros"),{target:{value:"zzzinexistente"}})
 expect(screen.getByText("Nenhum registro encontrado.")).toBeInTheDocument()
})
it("restricts financial profile navigation and preserves theme after logout", () => {
 enter("financeiro")
 expect(screen.queryByRole("button",{name:"Administração"})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole("button",{name:"Tema claro"}))
 fireEvent.click(screen.getByRole("button",{name:"Sair"}))
 expect(screen.getByRole("main")).toHaveAttribute("data-theme","light")
})
it("changes company and unit context without retaining a stale detail", () => {
 enter()
 fireEvent.change(screen.getByLabelText("Empresa"),{target:{value:"Horizonte Industrial"}})
 expect(screen.getByLabelText("Empresa")).toHaveValue("Horizonte Industrial")
 fireEvent.change(screen.getByLabelText("Unidade"),{target:{value:"CD Sul"}})
 expect(screen.getByLabelText("Unidade")).toHaveValue("CD Sul")
})


it("filters visible operational records by company and unit", () => {
 enter()
 fireEvent.click(screen.getByRole('button',{name:'Compras'}))
 expect(screen.getByText('Repor luvas de proteção')).toBeInTheDocument()
 fireEvent.change(screen.getByLabelText('Empresa'),{target:{value:'Horizonte Industrial'}})
 expect(screen.queryByText('Repor luvas de proteção')).not.toBeInTheDocument()
 fireEvent.change(screen.getByLabelText('Empresa'),{target:{value:'Aurora Distribuição'}})
 fireEvent.change(screen.getByLabelText('Unidade'),{target:{value:'CD Sul'}})
 expect(screen.queryByText('Repor luvas de proteção')).not.toBeInTheDocument()
})
it("opens and closes a record detail", () => {
 enter()
 fireEvent.click(screen.getByRole('button',{name:/Repor luvas de proteção/}))
 expect(screen.getByRole('dialog')).toBeInTheDocument()
 expect(within(screen.getByRole('dialog')).getByText('Aurora Distribuição')).toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Fechar detalhes'}))
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
it("limits store profile to its unit", () => {
 enter('loja')
 expect(screen.getByLabelText('Unidade')).toHaveValue('Loja Centro')
 expect(within(screen.getByLabelText('Unidade')).queryByRole('option',{name:'Matriz'})).not.toBeInTheDocument()
})
it("does not show international purchasing to the national buyer", () => {
 enter('comprador-nacional')
 fireEvent.click(screen.getByRole('button',{name:'Compras'}))
 expect(within(screen.getByRole('navigation')).queryByRole('button',{name:'Internacional'})).not.toBeInTheDocument()
 expect(within(screen.getByRole('navigation')).getByRole('button',{name:'Nacional'})).toBeInTheDocument()
})

it('shows the international container scenario only to its buyer', () => {
 enter('comprador-internacional')
 expect(screen.getByText(/Free Time crítico/)).toBeInTheDocument()
 expect(screen.getByText(/MSCU1234567/)).toBeInTheDocument()
 expect(screen.queryByText(/NAC-2026-01842/)).not.toBeInTheDocument()
})
it('shows the national cargo scenario only to its buyer', () => {
 enter('comprador-nacional')
 expect(screen.getByText(/CD Bauru.*Aço/)).toBeInTheDocument()
 expect(screen.getByText(/NAC-2026-01842/)).toBeInTheDocument()
 expect(screen.getByText(/perfis, juntas e cantoneiras/i)).toBeInTheDocument()
 expect(screen.queryByText(/MSCU1234567/)).not.toBeInTheDocument()
})
it('filters the attention center with toggleable summary cards', () => {
 enter('comprador-internacional')
 const attention = screen.getByRole('button', {name: /^Exigem atenção/})
 for (const name of [/^Para acompanhar/, /^Em dia/, /^No horizonte/]) expect(screen.getByRole('button', {name})).toHaveAttribute('aria-pressed','false')
 expect(screen.queryByText('Áreas disponíveis')).not.toBeInTheDocument()
 const center = screen.getByRole('region', {name:'Central de atenção'})
 expect(within(center).getByText('Free Time crítico')).toBeInTheDocument()
 fireEvent.click(screen.getByRole('button', {name:/^Em dia/}))
 expect(within(center).queryByText('Free Time crítico')).not.toBeInTheDocument()
 fireEvent.click(attention)
 expect(attention).toHaveAttribute('aria-pressed','true')
 expect(within(center).getByText('Free Time crítico')).toBeInTheDocument()
 fireEvent.click(attention)
 expect(attention).toHaveAttribute('aria-pressed','false')
 fireEvent.click(attention)
 fireEvent.click(screen.getByRole('button', {name:'Limpar filtro'}))
 expect(attention).toHaveAttribute('aria-pressed','false')
 expect(within(center).getByText('Free Time crítico')).toBeInTheDocument()
})
for (const [profile, risk, opportunity, evidence] of [
 ['comprador-internacional', 'Rolamentos: estoque antes do ETA', 'Reprogramar compra de válvulas', 'Free Time termina amanhã às 18h; tarifa demonstrativa de US$ 150/dia.'],
 ['comprador-nacional', 'Aço: ruptura antes da chegada', 'Revisar ponto de pedido do Aço', 'Estoque disponível: 300 peças; consumo médio: 100 peças/dia.'],
]) it(`explains three time windows for ${profile}`, () => {
 enter(profile)
 const center = screen.getByRole('region', {name:'Central de atenção'})
 for (const name of ['Hoje','Próximos 1–7 dias','Horizonte 7–30 dias']) expect(within(center).getByRole('heading',{name})).toBeInTheDocument()
 expect(within(center).getByText(risk)).toBeInTheDocument()
 expect(within(center).getByText(opportunity)).toBeInTheDocument()
 expect(screen.queryByText(evidence)).not.toBeInTheDocument()
 fireEvent.click(within(center).getAllByRole('button',{name:/Por quê/})[0])
 expect(screen.getByText(evidence)).toBeVisible()
 const why = within(center).getAllByRole('button',{name:/Por quê/})[0]
 expect(why).toHaveAttribute('aria-expanded','true')
 const explanation = document.getElementById(why.getAttribute('aria-controls')!)!
 expect(within(explanation).getAllByRole('listitem')).toHaveLength(2)
 fireEvent.click(screen.getByRole('button',{name:/^No horizonte/}))
 expect(within(center).queryByText(evidence)).not.toBeInTheDocument()
 expect(within(center).getByText(risk)).toBeInTheDocument()
 expect(within(center).getByText(opportunity)).toBeInTheDocument()
 expect(screen.getByRole('button',{name:/^No horizonte/})).toHaveTextContent('2')
})
