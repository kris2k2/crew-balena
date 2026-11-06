# Adding crew-sitetunnel to 360 St-Jacques

`services/crew-sitetunnel/service.yml` registers the project. It is **not**
in `fleets/360stjacques.yml` yet, because there is nothing to pin: no release
of kris2k2/crew-sitetunnel has been tagged with a balena block. Merging a pin
deploys it (the fleet has `deploy: true`), so it waits for these steps, in
order. How the project is packaged: its
[docs/BALENA.md](https://github.com/kris2k2/crew-sitetunnel/blob/main/docs/BALENA.md).

## 1. The project publishes a block (no effect on the device)

- [ ] `balena block create crew-sitetunnel-aarch64 --organization syneo --type raspberrypi5`
- [ ] crew-sitetunnel: repository secret `BALENA_API_TOKEN`; its packaging
      pull request merged; then its `chore(main): release X.Y.Z` pull request
      merged. That tags `vX.Y.Z` and publishes
      `bh.cr/syneo/crew-sitetunnel-aarch64/X.Y.Z`. Check the Releases tab of the
      block shows that version.

## 2. Configure the device first (no effect on the tunnel)

An unconfigured agent idles and logs what is missing, so this is not required
for safety, but setting the **service variables** for service `sitetunnel`
before the release lands means the tunnel comes up with it:
`SITETUNNEL_GATEWAY`, `SITETUNNEL_CERT_PEM`, `SITETUNNEL_KEY_PEM`,
`SITETUNNEL_ALLOW`, and `SITETUNNEL_CA_PEM` / `SITETUNNEL_CRL_URL` as the
gateway needs. Service variables, not fleet variables: the private key must
not reach printcapture. Service variables attach to a service
that exists in the fleet's release, so they can only be set once step 3 has
landed; the agent idles until then.

## 3. Pin it (production)

From a checkout of crew-sitetunnel at the tag (`X.Y.Z` below):

```sh
mkdir services/crew-sitetunnel/X.Y.Z
cp <crew-sitetunnel>/deploy/balena/fleet/docker-compose.yml services/crew-sitetunnel/X.Y.Z/
sha256sum services/crew-sitetunnel/X.Y.Z/docker-compose.yml
git -C <crew-sitetunnel> rev-parse vX.Y.Z^{commit}
```

Write `services/crew-sitetunnel/X.Y.Z/source.yml` (`tag: vX.Y.Z`, that commit,
that sha256; copy the shape from another service's), add `crew-sitetunnel: X.Y.Z`
under `services:` in `fleets/360stjacques.yml`, and raise the fleet `version`
(2.2.0: a new service). `python3 tools/fleet.py check --base-root <main checkout>`
and the CI summary show the rendered diff the merge would deploy: it must add
only the `sitetunnel` service, and leave `printcapture`, `syslog-collector` and
their volumes byte for byte as they were.

The supervisor should start the new container and leave the other two running,
as it does for any release that does not change them. Merge when the site is
quiet anyway, with the dashboard open. Rollback is a merge that removes the pin.

## 4. Verify

```sh
balena logs <uuid> --service sitetunnel
balena ssh <uuid> sitetunnel      # then: sitetunnel-entrypoint --check
```
