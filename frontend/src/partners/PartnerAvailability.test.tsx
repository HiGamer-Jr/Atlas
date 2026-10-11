import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,expect,it} from 'vitest';
import {PartnerAvailability} from './PartnerAvailability';
afterEach(cleanup);
it.each(['loading','unavailable','invalid','unauthenticated'] as const)('blocks all controls in %s',state=>{render(<PartnerAvailability state={state}/>);expect(screen.queryByRole('button')).not.toBeInTheDocument();expect(screen.queryByRole('combobox')).not.toBeInTheDocument();expect(screen.queryByRole('link')).not.toBeInTheDocument();expect(screen.getByRole(state==='loading'||state==='unavailable'?'status':'alert')).toBeInTheDocument();});
it('explains unavailable domain without synthetic organization or finance controls',()=>{render(<PartnerAvailability state="unavailable"/>);expect(screen.getByRole('status')).toHaveTextContent('O domínio de parceiros está indisponível');expect(document.body).not.toHaveTextContent(/Aprovar|Executar pagamento|Empresa demonstrativa/);});
