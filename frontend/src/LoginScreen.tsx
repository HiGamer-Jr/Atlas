import { useEffect, useState, type FormEvent } from "react"
import lightLogo from "./assets/hiatlas-light.png"
import darkLogo from "./assets/hiatlas-dark.png"
import "./LoginScreen.css"

type Props = {
  profiles: { id: string; name: string }[]
  selectedProfileId: string
  email: string
  onProfileChange: (id: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

export default function LoginScreen({ profiles, selectedProfileId, email, onProfileChange, onSubmit }: Props) {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const saved = localStorage.getItem("hiatlas-theme")
      if (saved === "light" || saved === "dark") return saved
    } catch { /* The theme still works when browser storage is unavailable. */ }
    return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark"
  })

  useEffect(() => { try { localStorage.setItem('hiatlas-theme', theme) } catch { /* Storage is optional. */ } }, [theme])

  function changeTheme(next: "light" | "dark") {
    setTheme(next)
    try { localStorage.setItem("hiatlas-theme", next) } catch { /* Keep the choice for this visit. */ }
  }

  const [showPassword, setShowPassword] = useState(false)
  const [recoveryInfo, setRecoveryInfo] = useState(false)

  return (
    <main className="hiatlas-access" data-theme={theme}>
      <header className="access-top">
        <div className="theme-picker" role="group" aria-label="Aparência">
          <button type="button" aria-label="Tema claro" aria-pressed={theme === "light"} onClick={() => changeTheme("light")}><span aria-hidden="true">☼</span> Claro</button>
          <button type="button" aria-label="Tema escuro" aria-pressed={theme === "dark"} onClick={() => changeTheme("dark")}><span aria-hidden="true">☾</span> Escuro</button>
        </div>
      </header>
      <section className="access-content" aria-labelledby="access-title">
        <img className="hiatlas-logo" src={theme === "light" ? lightLogo : darkLogo} alt="HiAtlas — Supply Chain Intelligence" width="1254" height="1254" />
        <div className="access-welcome">
          <h1 id="access-title">Bem-vindo à HiAtlas</h1>
          <p>Um novo horizonte para o seu negócio</p>
        </div>
        <form className="access-form" onSubmit={onSubmit} aria-describedby="demo-note">
          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" readOnly value={email} autoComplete="off" />
          <label htmlFor="password">Senha</label>
          <div className="password-field">
            <input id="password" type={showPassword ? "text" : "password"} readOnly value="atlas-demo" autoComplete="off" />
            <button className="password-toggle" type="button" aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>{showPassword && <path d="m3 3 18 18"/>}</svg>
            </button>
          </div>
          <button className="access-submit" type="submit" aria-label="Entrar no HiAtlas">ENTRAR</button>
        </form>
        <button className="forgot-password" type="button" aria-expanded={recoveryInfo} aria-controls="recovery-info" onClick={() => setRecoveryInfo(!recoveryInfo)}>Esqueceu sua senha?</button>
        {recoveryInfo && <p id="recovery-info" className="recovery-info" role="status">A recuperação de senha será disponibilizada com os acessos individuais. Este ambiente utiliza credenciais demonstrativas.</p>}
        <details className="demo-options">
          <summary>Opções de demonstração</summary>
          <label htmlFor="profile">Perfil de acesso</label>
          <select id="profile" value={selectedProfileId} onChange={event => onProfileChange(event.target.value)}>
            {profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
          </select>
        </details>
        <p id="demo-note" className="access-note">Acesso demonstrativo. Os logins por setor serão disponibilizados em breve.</p>
      </section>
      <footer className="access-footer">© HiGamer</footer>
    </main>
  )
}
