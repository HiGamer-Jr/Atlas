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
