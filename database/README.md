# Atlas Database

O banco transacional principal do Atlas é PostgreSQL.

## Desenvolvimento local

- Container: `atlas-postgres`
- Porta do host: `5433`
- Porta interna: `5432`
- Banco padrão: `atlas`

Credenciais locais devem ficar em `.env` e nunca devem ser versionadas.

O Atlas não deve compartilhar banco, schema, volume ou porta de aplicação com outros projetos.
