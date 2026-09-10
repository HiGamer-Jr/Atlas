import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import App from "./App"

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})

describe("App", () => {
  it("starts with the Atlas profile login", () => {
    render(<App />)

    expect(
      screen.getByRole("heading", { name: /atlas/i }),
    ).toBeInTheDocument()

    expect(screen.getByRole("img", { name: /hiatlas/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/perfil de acesso/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /entrar no hiatlas/i })).toBeInTheDocument()
    expect(screen.getAllByText(/coordenação/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/administrador/i).length).toBeGreaterThan(0)
  })

})

it("switches the logo and theme and restores the preference on a new visit", () => {
  const { unmount } = render(<App />)
  fireEvent.click(screen.getByRole("button", { name: /tema claro/i }))
  expect(screen.getByRole("main")).toHaveAttribute("data-theme", "light")
  expect(screen.getByRole("img", { name: /hiatlas/i }).getAttribute("src")).toContain("hiatlas-light")
  unmount()
  render(<App />)
  expect(screen.getByRole("main")).toHaveAttribute("data-theme", "light")
  fireEvent.click(screen.getByRole("button", { name: /tema escuro/i }))
  expect(screen.getByRole("main")).toHaveAttribute("data-theme", "dark")
  expect(screen.getByRole("img", { name: /hiatlas/i }).getAttribute("src")).toContain("hiatlas-dark")
})


it('reveals the password and explains demo password recovery', () => {
 render(<App />)
 const password = screen.getByLabelText('Senha', {exact:true})
 expect(password).toHaveAttribute('type','password')
 fireEvent.click(screen.getByRole('button',{name:'Mostrar senha'}))
 expect(password).toHaveAttribute('type','text')
 fireEvent.click(screen.getByRole('button',{name:'Ocultar senha'}))
 expect(password).toHaveAttribute('type','password')
 fireEvent.click(screen.getByRole('button',{name:'Esqueceu sua senha?'}))
 expect(screen.getByRole('status')).toHaveTextContent('recuperação de senha')
})
