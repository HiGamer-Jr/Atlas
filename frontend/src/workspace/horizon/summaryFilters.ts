export type SummaryFilter = 'ATTENTION' | 'FOLLOW_UP' | 'ON_TRACK' | 'HORIZON'
export const summaryLabels: Record<SummaryFilter, string> = {
 ATTENTION: 'Exigem atenção', FOLLOW_UP: 'Para acompanhar', ON_TRACK: 'Em dia', HORIZON: 'No horizonte',
}
