# Migrating 360 St-Jacques from crew-printcapture to crew-balena

The runbook for moving fleet `syneo/crew` (one Raspberry Pi 5, the
360 St-Jacques device) from crew-printcapture's own fleet push to crew-balena,
then renaming it `360StJacques`. Why: [ADR-0001](adr/0001-composable-fleet-deployment.md).

What must hold throughout: printcapture keeps running on the device with the
same service name (`printcapture`), the same volume (`printcapture-data`), the
same variables, and the same block version, and at every moment exactly one
repository can push to the fleet.

There is no staging device, so step 3 is done on production. Do it when the
site is closed, with the dashboard open.

## 1. Scaffold (this repository, no effect on the device)

Merged when `fleets/360stjacques.yml` exists with `deploy: false`. CI renders
it and a unit test holds that the render equals what crew-printcapture's
`deploy.sh` pushes for 1.15.0.

## 2. Prepare (settings, no effect on the device)

- [ ] GitHub, crew-balena: environment `balena`, deployment branches limited
      to `main`, holding the secret `BALENA_API_TOKEN`
      (`balena api-key generate "crew-balena deploy"`).
- [ ] GitHub, crew-balena: ruleset on `main`: pull requests required, the `fleets`
      status check required, no force-push; "Allow auto-merge" on.
- [ ] GitHub, crew-printcapture: Settings → Secrets and variables → Actions →
      Variables. If `BALENA_FLEETS` is set, note it; it overrides
      `deploy.conf` and is cleared in step 3.
- [ ] balenaCloud: the device runs the newest crew-printcapture release
      (1.15.0) and is not pinned to an older one. If it isn't, vendor that
      version here first and pin it in the manifest instead.
- [ ] Compare the live composition with this repository's render. Commands
      as of balena CLI 25; check spelling with `balena help release`:

      ```sh
      balena release list syneo/crew            # newest release first; note its commit
      balena release <commit> --composition     # the composition devices run
      python3 tools/fleet.py render 360stjacques --out /tmp/render
      ```

      The two must match apart from comments and key order: same image
      (`bh.cr/syneo/crew-printcapture-aarch64/1.15.0`), service, volume,
      `network_mode`, capabilities, `stop_grace_period` and environment
      names. If anything else differs, stop.

## 3. Cutover (production)

Freeze crew-printcapture releases for the duration: don't merge its
`chore(main): release X.Y.Z` pull request until this step is done.

1. **crew-printcapture pull request**, merged first. After it, nothing pushes
   to the fleet:
   - `deploy/balena/deploy.conf`: `BALENA_FLEETS=""`, with a comment pointing
     at this repository. Releases still publish the block.
   - Delete the repository variable `BALENA_FLEETS` if step 2 found one.
   - `.github/workflows/balena.yml`: remove the `fleets` dispatch input and
     its use, so a manual run cannot push to a fleet either.
2. **crew-balena pull request**: `deploy: true` in `fleets/360stjacques.yml`.
   Merging it runs the deploy workflow, which pushes fleet release 2.0.0 to
   `syneo/crew`, tagged `crew-printcapture 1.15.0`.
3. **Verify**, in the dashboard:
   - [ ] the device reports release 2.0.0, with service `printcapture`
         running;
   - [ ] the container was not restarted (its "running since" time is from
         before the push). If it was, check the next points before deciding
         anything; a restart is a 30-second blip, not a failure;
   - [ ] the device's service variables are all still set;
   - [ ] a test print from the POS is captured and reaches the dashboard.

**Rollback:** in the dashboard, pin the fleet to the last crew-printcapture
release (1.15.0). That is immediate and independent of git. Then revert the
crew-balena pull request so the next merge doesn't undo the pin, and work out
what differed.

## 4. Rename the fleet

1. Rename `syneo/crew` to `360StJacques`
   (`balena fleet rename syneo/crew 360StJacques`, or the dashboard). Its slug
   becomes `syneo/360stjacques`. A rename keeps the fleet's id, so the device,
   its volume and its variables stay put. balena may not accept a name that
   starts with a digit; if it refuses, pick the name here and use it
   everywhere below.
2. crew-balena pull request: `slug: syneo/360stjacques`. This alone pushes
   nothing (the composition is unchanged), and until it merges a deploy would
   fail with "fleet not found" rather than reach the wrong fleet.

## 5. Remove the old path from crew-printcapture

After the first crew-printcapture release has reached the device through
crew-balena:

- remove the fleet push (step 2 of `deploy.sh`) and `BALENA_FLEETS` from
  `deploy.conf` and `.github/workflows/balena.yml`;
- keep `deploy/balena/fleet/docker-compose.yml` where it is: it is the
  fragment this repository vendors (`services/crew-printcapture/service.yml`),
  and its path is part of the contract. Its comments should say so;
- update `docs/deploy-balena.md` and `docs/releasing.md` to describe the new
  release path.

## Releasing printcapture in the meantime

Until the bump automation exists, a crew-printcapture release reaches the
device by a crew-balena pull request that:

1. vendors the release: `services/crew-printcapture/<version>/`, with
   `docker-compose.yml` copied byte for byte from
   `deploy/balena/fleet/docker-compose.yml` at tag `v<version>`, and
   `source.yml` (tag, commit, sha256);
2. pins it in `fleets/360stjacques.yml` and raises the fleet version by the
   same kind of bump (patch for patch, minor for minor, major for major).
