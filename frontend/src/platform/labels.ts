export const environmentLabel = (value: string) => ({ PRODUCTION: 'Produção', STAGING: 'Homologação', TEST: 'Teste' }[value] ?? value);
