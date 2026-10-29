# Agent instructions: crew-balena

This repository follows the governance baseline in
[`.governance/AGENTS.md`](.governance/AGENTS.md). Read it first. It applies
unless a human working with you says otherwise. Paths it mentions
(`standards/`, `templates/`, `tools/`) are under `.governance/`.

`.governance/` is managed: never edit it. It's updated by pull requests from
the `governance-sync` workflow (or `python3 .governance/tools/governance.py sync`).

## Project specifics

This repository releases balenaCloud fleets: see [README.md](README.md) for
the layout and [ADR-0001](docs/adr/0001-composable-fleet-deployment.md) for
why. **A merge to main that changes a fleet deploys it to devices** nobody can
reach in person, so:

- Never edit a vendored fragment (`services/<name>/<version>/docker-compose.yml`).
  It is a byte-for-byte copy of the project's release; fix the project and
  vendor its next release instead.
- Never rename a service or volume that has run on a device, and never flip a
  fleet's `deploy` to true outside the cutover in
  [docs/migration-crew-printcapture.md](docs/migration-crew-printcapture.md).
- Raise a fleet's `version` in the same change as anything that alters its
  render; CI enforces it.
- Never run `tools/deploy.sh` without `--dry-run`, or the deploy workflow by
  hand, unless the human asked for that deploy in the conversation.

Commands:

```sh
python3 -m unittest discover -s tests   # unit tests (< 1 s)
python3 tools/fleet.py check            # every fleet renders; add --base-root DIR to check version bumps
shellcheck tools/*.sh
```
<!-- Build, test and run commands; the layout; rules specific to this project. -->
