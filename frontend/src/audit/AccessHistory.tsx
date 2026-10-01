import AuditPage from './AuditPage';
export default function AccessHistory({ memberId }: {
    memberId: string;
}) { return <AuditPage memberId={memberId}/>; }
