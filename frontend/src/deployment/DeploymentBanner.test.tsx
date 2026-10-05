import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import DeploymentBanner from './DeploymentBanner';

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe('DeploymentBanner', () => {
  it('does not render in a normal deployment', () => {
    vi.stubEnv('VITE_DEPLOYMENT_VARIANT', '');

    render(<DeploymentBanner />);

    expect(
      screen.queryByRole('status', { name: 'Ambiente de demonstração' }),
    ).not.toBeInTheDocument();
  });

  it('identifies the demo deployment and synthetic data', () => {
    vi.stubEnv('VITE_DEPLOYMENT_VARIANT', 'demo');

    render(<DeploymentBanner />);

    expect(
      screen.getByRole('status', { name: 'Ambiente de demonstração' }),
    ).toHaveTextContent('AMBIENTE DE DEMONSTRAÇÃO');

    expect(
      screen.getByRole('status', { name: 'Ambiente de demonstração' }),
    ).toHaveTextContent('Todos os dados apresentados são fictícios.');
  });
});