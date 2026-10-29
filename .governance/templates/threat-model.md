# Threat Model: <feature name>

> Copy into the project's `docs/threat-models/` and fill in. Required for
> features touching authentication, authorization, payments, personal data,
> file upload, external integrations, or LLM/agent capabilities.
> Method: [OWASP Threat Modeling](https://owasp.org/www-community/Threat_Modeling)
> four questions with STRIDE.

| | |
|---|---|
| Author | |
| Date | |
| Reviewers | |
| Related PR / ADR | |

## 1. What are we building?

Short description, plus a data-flow sketch: actors, components, data stores,
and the **trust boundaries** between them.

```
[User browser] --HTTPS--> [API] --SQL--> [DB]
                   |
                   +--HTTPS--> [Third-party / LLM provider]
```

### Data handled

| Data | Classification (public / internal / confidential / personal / sensitive personal) | Stored where | Retention |
|---|---|---|---|
| | | | |

### AI components (if the feature calls a model)

| AI asset | This feature | Where it lives | Who can change it |
|---|---|---|---|
| Model ID(s), provider, and where inference runs | | | |
| System prompt and agent instructions | | | |
| Tools the model can call, and their permissions | | | |
| Retrieval sources (knowledge bases, vector indexes) | | | |
| Guardrail settings | | | |
| Evaluation suite | | | |
| Model-call logging (metadata only, or full text and its retention) | | | |

## 2. What can go wrong? (STRIDE)

| Threat | Applies? | Scenario | Mitigation | Status |
|---|---|---|---|---|
| **S**poofing identity | | | | |
| **T**ampering with data | | | | |
| **R**epudiation | | | | |
| **I**nformation disclosure | | | | |
| **D**enial of service | | | | |
| **E**levation of privilege | | | | |

For LLM/agent features, also walk the
[agentic & LLM risks](../standards/security/owasp-agentic-llm.md)
(prompt injection, excessive agency, output handling, unbounded consumption)
and the life-cycle controls in its Part C.

## 3. Privacy

- What personal data is collected, and why is each field necessary?
- Who can access it (roles), and how is that enforced?
- Is it sent to any third party (including LLM APIs), or processed outside
  Canada (e.g. Bedrock cross-Region inference)? Under what agreement?
- Does the feature make a decision about a person based only on automated
  processing, such as a model's output? Québec's Law 25 requires telling
  them, explaining the main factors on request, and letting them ask a
  person to review it.
- Retention and deletion: how does a user's deletion request reach this data?
- Is a privacy impact assessment required?

## 4. What are we doing about it?

List the mitigations with owners and links to the code or tickets. Note any
accepted risks and who accepted them.

## 5. Did we do a good job?

- [ ] Abuse cases have tests
- [ ] AI features: the evals include the abuse cases, and someone other than
  the author tried to break the feature before its first release
- [ ] Reviewed by someone outside the implementing team
- [ ] Revisit trigger defined (e.g. new data type, new integration)
