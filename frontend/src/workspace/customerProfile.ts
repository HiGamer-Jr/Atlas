/** Presentation metadata only. Backend capabilities remain authoritative. */
const customerProfiles = [
  { code: 'COORDENACAO', name: 'Coordenação' },
  { code: 'SUPERVISAO', name: 'Supervisão' },
  { code: 'COMPRADOR_NACIONAL', name: 'Comprador nacional' },
  { code: 'COMPRADOR_INTERNACIONAL', name: 'Comprador internacional' },
  { code: 'DIRETORIA', name: 'Diretoria' },
  { code: 'LOJA', name: 'Loja' },
  { code: 'CENTRO_DISTRIBUICAO', name: 'Centro de distribuição' },
] as const;

export function profileForTenantRole(roleCode: string | null | undefined) {
  return customerProfiles.find(profile => profile.code === roleCode) ?? null;
}