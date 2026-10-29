# ADR-0001: crew-balena owns fleet deployment; projects publish blocks

- **Status:** accepted
- **Date:** 2026-10-29
- **Deciders:** @kris2k2

## Context

crew-printcapture deploys itself to balenaCloud end to end. On each release it
publishes its image as a balena block (`syneo/crew-printcapture-aarch64`) and
then pushes a fleet composition referencing that block to every fleet in its
own `deploy/balena/deploy.conf`, currently `syneo/crew` (one Raspberry Pi 5 at
360 St-Jacques).

crew-videocapture, and later crew-eventcapture, will run on the same devices.
If every project pushes its own fleet release, each push replaces the others'
services, so a fleet composed of several projects needs one place that
decides what the fleet runs. The migration must not disturb printcapture on
the one production device, and there is no spare device for staging.

## Decision

1. **Projects publish blocks; crew-balena releases fleets.** A project keeps
   its image, its block publish on release, and its compose fragment (the
   service-level settings its container needs). crew-balena owns which fleets
   exist, which service versions each runs, and the push to balenaCloud.
2. **One fleet per site.** The first is `360StJacques`, composed of
   crew-printcapture now and crew-videocapture later, on the same device. The
   existing fleet `syneo/crew` becomes it by a rename, not by moving the
   device (which risks the fleet-scoped volume and service variables).
3. **Fragments are vendored, verbatim, per release.** crew-balena holds a copy
   of each project's fragment at each release tag it deploys, with the tag,
   commit and sha256 it came from. CI rejects an edited copy. The project
   stays the author of its fragment and keeps checking it against its own
   entrypoint.
4. **Merge deploys.** A merge to main that changes a fleet's rendered
   composition pushes it, if its manifest says `deploy: true`. Version-bump
   pull requests from project releases auto-merge on green CI.
5. **Fleet releases have their own version**, starting at 2.0.0 so the first
   crew-balena release sorts above the 1.x releases crew-printcapture pushed.
   Each release is tagged with the version of every service it runs.
6. **One writer per fleet.** A fleet is pushed by crew-balena only once its
   manifest says `deploy: true`, and that flips in the same change that
   removes the project's own fleet push.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Keep per-project fleet pushes | No migration | Projects overwrite each other's services in a shared fleet |
| One fleet per service repository | No composition needed | A device belongs to exactly one fleet, so a site running two services on one device cannot be two fleets |
| **One fleet per site, composed here (chosen)** | One release history per site; projects stay independent | A second repository in the release path |
| Fetch fragments from the project at deploy time | No copies | Cross-repository token at deploy time; deploy depends on GitHub; this repository cannot render on its own |
| **Vendor fragments per release (chosen)** | Self-contained; each bump PR shows the compose diff it deploys | Copies to keep honest, which CI's hash check does |

## Consequences

- **Auto-merge means a project release reaches devices with no second human
  step.** That is how crew-printcapture releases worked before this change,
  so the human gate stays where it was: the project's release pull request.
  Major version bumps are not auto-merged.
- **No staging device.** The first crew-balena push to `syneo/crew` lands on
  production. It renders a composition equal to the one crew-printcapture
  pushes (a unit test holds that), which the supervisor should apply without
  restarting the container; the cutover runbook schedules it in a quiet window
  with the rollback ready.
- **Generic `CREW_*` variable names collide in a multi-service fleet**: a
  fleet-wide variable reaches every service. They must be service-scoped
  before crew-videocapture joins, and new services use their own prefix
  (docs/service-contract.md).
- **balenaCloud still holds state git does not**: variables, secrets and
  device pins. crew-balena is the source of truth for what each fleet runs,
  not for everything in the dashboard.
- **Security:** `BALENA_API_TOKEN` can push to every fleet the account can
  see; it lives in a GitHub environment limited to main, not as a repository
  secret. The bump automation needs a GitHub App token to open pull requests
  that trigger CI; it gets contents and pull-request write on this repository
  only.
