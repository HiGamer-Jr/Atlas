import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import LoginForm from './LoginForm';
afterEach(cleanup);
it('uses real credentials without a profile selector', () => {
    render(<LoginForm onLogin={vi.fn()}/>);
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.getByLabelText('E-mail')).not.toHaveAttribute('readonly');
    expect(screen.getByLabelText('Senha')).toHaveValue('');
});
it('identifies login fields after a sanitized validation error', async () => {
    const { fireEvent } = await import('@testing-library/react');
    const { ApiError } = await import('../api/errors');
    render(<LoginForm onLogin={vi.fn().mockRejectedValue(new ApiError(422))}/>);
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'user@example.test' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'input' } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar no HiAtlas' }));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('E-mail')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Senha')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('Confira os campos E-mail e Senha.')).toBeInTheDocument();
});
