# Acceptance Checklist

Use this checklist before marking an agent task complete.

## Boundary Safety

- [ ] Did not read raw survey DB directly.
- [ ] Did not read canonical map/place DB directly unless explicitly approved.
- [ ] Did not accept trusted `user_id` from public request body.
- [ ] Did not issue or refresh JWTs.
- [ ] Did not move recommendation ranking into the LLM.
- [ ] Did not store canonical place/menu/inventory data in assistant-service.

## LLM / RAG Safety

- [ ] LLM receives only retrieved/approved facts.
- [ ] No-evidence path returns insufficient-data/no-answer response.
- [ ] Out-of-scope questions are refused.
- [ ] Output schema includes confidence/refusal metadata where applicable.
- [ ] Used sources are traceable internally.
- [ ] Prompt does not allow invented alcohols, venues, prices, or inventory.

## API Safety

- [ ] gRPC request/response changes are documented.
- [ ] Auth metadata expectations are documented.
- [ ] Backward compatibility is considered.
- [ ] Error/status responses are explicit.

## Storage Safety

- [ ] New storage is assistant-owned only.
- [ ] Migrations are documented if added.
- [ ] No secrets are stored in code or committed files.
- [ ] Retention/training implications are documented.

## Python Quality

- [ ] Code is typed where practical.
- [ ] Config is read from environment or safe config layer.
- [ ] Provider adapters are abstracted.
- [ ] Tests or at least compile checks run.

## Documentation

- [ ] Relevant docs updated.
- [ ] README or docs index updated if new docs were added.
- [ ] Examples are realistic and do not contain real secrets.

## Completion Report

- [ ] Summary provided.
- [ ] Files changed listed.
- [ ] Tests/checks listed.
- [ ] Risks and next steps listed.
