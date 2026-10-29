# crew-balena

What every crew site's balenaCloud fleet runs, and the pipeline that releases
it. Each project (crew-printcapture today, crew-videocapture and
crew-eventcapture later) builds and publishes its own image as a balena
block; this repository decides which version of which block each site's
fleet runs, and pushes the fleet release when that changes.

Why it is split this way: [ADR-0001](docs/adr/0001-composable-fleet-deployment.md).

## Layout

| Path | What it is |
| --- | --- |
| `fleets/<id>.yml` | a site's fleet: balenaCloud slug, fleet release version, `deploy` on or off, and each service's pinned version |
| `services/<name>/service.yml` | a project: its repository, the path of its compose fragment, its block |
| `services/<name>/<version>/` | that project's fragment at release `v<version>`, copied verbatim, with `source.yml` recording where from |
| `tools/fleet.py` | renders and checks fleets |
| `tools/deploy.sh` | pushes one rendered fleet to balenaCloud |
| `.github/workflows/ci.yml` | on every pull request: tests, checks, and the rendered diff the merge would deploy |
| `.github/workflows/deploy.yml` | on merge to main: pushes every fleet whose render changed and whose `deploy` is on |
| [`docs/service-contract.md`](docs/service-contract.md) | what a project must provide, and the naming rules a shared fleet needs |
| [`docs/migration-crew-printcapture.md`](docs/migration-crew-printcapture.md) | the cutover runbook for 360 St-Jacques |

## Fleets

| Fleet | balenaCloud | Services | Deploying |
| --- | --- | --- | --- |
| [`360stjacques`](fleets/360stjacques.yml) | `syneo/crew` (to be renamed `syneo/360stjacques`) | crew-printcapture | yes |

## Releasing

A merge to `main` that changes what a fleet renders to is a release of that
fleet. CI refuses the change unless the fleet's `version` went up with it.

```sh
python3 -m pip install --require-hashes -r tools/requirements.txt
python3 -m unittest discover -s tests              # unit tests
python3 tools/fleet.py check                       # every fleet renders
python3 tools/fleet.py render --out /tmp/render    # what balena would build
tools/deploy.sh /tmp/render/360stjacques --dry-run # what a push would do
```

Pushing by hand (Actions → deploy → Run workflow) takes a fleet id and only
works for fleets with `deploy: true`.
