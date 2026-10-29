# Service contract

What a project has to provide for crew-balena to run it in a fleet. The
reasoning is in [ADR-0001](adr/0001-composable-fleet-deployment.md).

## The project provides

1. **A balena block per release.** A `balena.yml` with `type: sw.block` and a
   3-digit semver `version`, published on every release tag `vX.Y.Z` to
   `<organization>/<block>`. The block must finish building before
   crew-balena is told about the release.
2. **A compose fragment**, kept in the project's repository and released with
   it, that crew-balena copies verbatim. It may use only the top-level keys
   `version`, `services` and `volumes`, and every service in it must have
   exactly

   ```yaml
   image: bh.cr/BALENA_BLOCK_SLUG/BALENA_BLOCK_VERSION
   ```

   which crew-balena replaces with the block and the version the fleet pins.
   Everything else the container needs from its host (networking,
   capabilities, volumes, the variables the dashboard shows) is declared here.

## Names

Every service and volume a fragment declares shares one namespace with every
other project in the fleet, and balenaCloud keys state to these names:

- **Service names** scope dashboard service variables, secrets included.
  Renaming a service drops them.
- **Volume names** hold the data that survives releases. Renaming a volume
  starts the device on an empty one.

So: prefix service and volume names with the project's short name
(`printcapture`, `printcapture-data`), and never rename one after it has run
on a device. `tools/fleet.py` rejects a fleet where two projects declare the
same name.

**Environment variables** set fleet-wide in the dashboard reach every service
in the fleet. Use a project prefix (`PRINTCAPTURE_*`, `VIDEOCAPTURE_*`). Set
anything secret, and anything with a generic name, as a *service* variable.
crew-printcapture's `CREW_*` variables predate this rule and must be
service-scoped before a second service joins its fleet.

**Host networking** (`network_mode: host`) puts every port a service listens on
straight onto the device. Ports and LAN alias IPs in use:

| Service | Ports | LAN alias IPs |
|---|---|---|
| crew-printcapture | 9100 (print), 8080 (web UI) | from `PRINTCAPTURE_DOC_TYPES` |

A new service adds its row here in the pull request that first vendors it.

## Rollback

Rolling a fleet back is a merge that pins an older service version. That is
only safe if the older version can still read what the newer one left on its
volume, so a release that changes an on-volume format must say so in its
changelog, and its bump is not auto-merged (make it a major version).

## Adding a project

1. Create its directory under `services/`, with `service.yml` (repository,
   fragment path, block).
2. Vendor a release: `services/<name>/<version>/docker-compose.yml`, copied
   byte for byte from the fragment at tag `v<version>`, and `source.yml` with
   that tag, its commit, and the file's sha256.
3. Add it to a fleet's `services:` and raise the fleet's version.
