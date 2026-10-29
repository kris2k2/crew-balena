# AWS Platform Standard

Defaults for every AWS project. Detail lives in the linked standards:
[CI bootstrap](../security/aws-ci-bootstrap.md),
[cost](../efficiency/aws-cost.md),
[runtime versions](../sdlc/runtime-versions.md).

## Regions: Canada first

| Region | Use |
|---|---|
| **`ca-central-1`** (Montréal) | **Default home region.** Every stack, data store, and compute resource goes here unless something below applies. |
| **`us-east-1`** (N. Virginia) | **Alternate.** Only for what must live there or isn't offered in Canada, and as a backup: CloudFront certificates (ACM) and CloudFront-scoped WAF, global-service control planes, and services or models not yet available in `ca-central-1` (for Bedrock models, see [Amazon Bedrock inference](#amazon-bedrock-inference)). |
| Anything else | Not allowed by default; the CI bootstrap's boundary blocks it. Needs an ADR. |

- **Personal data stays in Canada by default.** Store and process it in
  `ca-central-1`. Sending personal data to `us-east-1` (including to a model
  hosted there) needs a privacy assessment first: Québec's Law 25 requires
  one before personal information leaves Québec, and the privacy notice must
  say so (see [PII standard](../privacy/pii.md)).
- **Static and edge content** can mix regions: an S3 origin in `ca-central-1`
  with its CloudFront certificate in `us-east-1` (with CDK, two stacks and
  `crossRegionReferences: true`).
- For disaster recovery that keeps data in Canada, consider `ca-west-1`
  (Calgary). Using it is an ADR-level decision; add it to `AllowedRegions`
  and deploy the bootstrap's regional assets there.
- Region is set in code (`env.region` in CDK, or the deploy command), never
  left to a developer's or runner's default profile.

### Amazon Bedrock inference

A model call made in `ca-central-1` doesn't always run there:

| How the model is called | Where inference runs |
|---|---|
| In-Region (a model ID, no inference profile) | The Region you call. The default. |
| Geographic cross-Region profile (`us.…`, or a Canada geography) | Several Regions; from `ca-central-1` they include US Regions other than `us-east-1`. The list is fixed. |
| Global cross-Region profile (`global.…`) | Any commercial Region, including opt-in Regions where AWS may store prompts and outputs for abuse detection. The list grows as AWS adds Regions. |
| Bedrock features that route on their own | From `ca-central-1`, AgentCore Memory and Evaluations use AWS's "Canada" geography, which includes `us-east-1`, `us-east-2`, and `us-west-2`; Policy in AgentCore uses global inference. |

- Use a model offered in-Region in `ca-central-1` when one does the job.
- Cross-Region inference is a Region decision like any other: it needs an
  ADR, plus the privacy assessment above whenever prompts can contain
  personal data (they usually can). Global profiles are only for data that
  may be processed anywhere, never for personal data.
- Check where a profile routes with `aws bedrock get-inference-profile`,
  called from the Region you'll use it in; don't go by the prefix. CloudWatch
  and CloudTrail don't record where inference ran, so the ADR is the record.
- Read a Bedrock feature's cross-Region inference notes before using it.
- The bootstrap's boundary only allows `AllowedRegions`, and Bedrock needs
  permission in every destination Region of a profile, so cross-Region
  profiles are refused until the project allows them; features that route
  on their own may not be. Don't add Regions to `AllowedRegions` for this,
  since that opens every service there: a Bedrock-only exception is a
  bootstrap change for the administrator.

## Infrastructure as code: AWS CDK first

**New infrastructure is written with the AWS CDK in TypeScript.**

- It's real code: types, tests, reuse, and review like any other code.
- Higher-level constructs bring secure defaults (encryption, least-privilege
  grants such as `bucket.grantRead(fn)`), so fewer things to get wrong.
- It's still CloudFormation underneath, so deploys go through the same
  execution role, boundary, change sets, and rollbacks.

Rules:

- Use [`templates/aws/cdk/project-guardrails.ts`](../../templates/aws/cdk/project-guardrails.ts):
  `projectStackProps(PROJECT, …)` for every stack and
  `applyProjectGovernance(app, PROJECT)` once. It deploys with the CI role's
  credentials and the bootstrap's execution role (no `cdk bootstrap`, no
  `cdk-*` roles), defaults the region to `ca-central-1`, publishes assets to
  the bootstrap's asset bucket, and gives every IAM role (including CDK's
  internal ones) the project path and permissions boundary.
- Prefer L2/L3 constructs and `grant*` methods over hand-written IAM policies.
- Commit `package-lock.json` and `cdk.json`. Commit `cdk.context.json` too, so
  context lookups (`fromLookup`) are resolved once by a person and CI never
  needs lookup permissions.
- Pin `aws-cdk-lib`, `constructs`, and the `aws-cdk` CLI exactly, and update
  them with Dependabot/Renovate. Run the CLI from the project (`npx cdk`), not
  a global install.
- Test stacks with `aws-cdk-lib/assertions` (e.g. "the bucket blocks public
  access", "the function has a log retention period").
- Consider [cdk-nag](https://github.com/cdklabs/cdk-nag) (AwsSolutions rules)
  for automatic misconfiguration checks (OWASP A02).
- CI runs `npx cdk deploy --all --require-approval never --role-arn <execution role>`
  on the protected environment; pull requests run `cdk synth` and `cdk diff`.

Plain CloudFormation or SAM is acceptable for small, stable stacks and for
the bootstrap itself. Don't introduce Terraform or Pulumi without an ADR.

## Accounts, tags, and naming

- One AWS account per project and environment, under AWS Organizations.
- Every resource is tagged `project` (lowercase key; AWS treats `Project` as
  a different key). With CDK, set it once with `Tags.of(app).add(...)`.
- Stacks are named `<project>` or `<project>-<part>` (the bootstrap enforces
  this).
