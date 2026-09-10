import { useState } from 'react'
import LoginScreen from './LoginScreen'
import Workspace from './workspace/Workspace'
import { profiles } from './workspace/catalog'
export default function App() {
 const [selected,setSelected] = useState('coordenacao')
 const [active,setActive] = useState<string|null>(null)
 const profile = profiles.find(p=>p.id===active)
 return profile ? <Workspace profile={profile} onLogout={()=>setActive(null)}/> : <LoginScreen profiles={profiles} selectedProfileId={selected} email={`${selected}@hiatlas.demo`} onProfileChange={setSelected} onSubmit={event=>{event.preventDefault();setActive(selected)}}/>
}
