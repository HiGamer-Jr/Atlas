export function PartnerAvailability({state}:{state:'loading'|'unavailable'|'invalid'|'unauthenticated'}) {
 const messages={loading:'Verificando disponibilidade de parceiros…',unavailable:'O domínio de parceiros está indisponível. Não há operações de parceiros disponíveis neste momento.',invalid:'Não foi possível validar a disponibilidade de parceiros. O acesso permanece bloqueado.',unauthenticated:'Entre novamente para verificar a disponibilidade de parceiros.'};
 return <section aria-label="Disponibilidade de parceiros"><p role={state==='loading'||state==='unavailable'?'status':'alert'}>{messages[state]}</p></section>;
}
