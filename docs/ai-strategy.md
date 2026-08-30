# AI strategy: govern the data boundary, not the person

Grounded's claim is deliberately narrow. It governs the path from a model's proposed data request to an answer; it does not pretend that a data platform is an identity system, an application sandbox, or a general-purpose agent runtime.

## What the platform governs

- **Definitions:** only declared metrics, dimensions, filters, and entity reads are executable.
- **Policy:** declared row and column rules are applied server-side for an asserted role.
- **Execution scope:** malformed plans, raw SQL, and undeclared arguments become safe refusals.
- **Verification:** declared checks run over the computed result before return.
- **Audit:** each governed action records its inputs, policy decisions, and verification status.
- **Lineage:** the response carries a Contract-B citation, with graph verification from Marquez when the service is available.

## What it does not govern

- Authenticating a person or proving that an asserted role is genuine.
- Application authorization outside the data request.
- Sandboxing tool execution, network egress, model-host isolation, or secret delivery.
- Human approval workflows and out-of-band actions such as sending an email or changing a record.

Those concerns belong to an identity provider, application gateway, sandbox, and the surrounding agent product. Treating them as a property of a semantic layer would make an unsafe claim.

## The operating consequence

The harness reduces the model's authority: it can propose a governed request, not issue arbitrary commands. Identity-aware systems must supply the trusted role before that request enters the harness, and applications must separately authorize every action beyond the read-only data boundary. This separation lets model upgrades improve routing coverage without weakening the safety floor.
