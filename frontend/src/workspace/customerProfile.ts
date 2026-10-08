import { profiles } from './catalog'

const tenantRoleToProfile = {
  COORDENACAO: 'coordenacao',
  SUPERVISAO: 'supervisao',
  COMPRADOR_NACIONAL: 'comprador-nacional',
  COMPRADOR_INTERNACIONAL: 'comprador-internacional',
  DIRETORIA: 'diretoria',
  LOJA: 'loja',
  CENTRO_DISTRIBUICAO: 'cd',
} as const

export function profileForTenantRole(roleCode: string | null | undefined) {
  if (!roleCode) return null

  const profileId =
    tenantRoleToProfile[roleCode as keyof typeof tenantRoleToProfile]

  if (!profileId) return null

  return profiles.find(profile => profile.id === profileId) ?? null
}
