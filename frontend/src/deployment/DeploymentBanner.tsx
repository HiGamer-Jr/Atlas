export default function DeploymentBanner() {
  if (import.meta.env.VITE_DEPLOYMENT_VARIANT !== 'demo') {
    return null;
  }

  return (
    <aside
      className="deployment-demo-banner"
      role="status"
      aria-label="Ambiente de demonstração"
    >
      <strong>AMBIENTE DE DEMONSTRAÇÃO</strong>
      <span>Todos os dados apresentados são fictícios.</span>
    </aside>
  );
}