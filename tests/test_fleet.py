"""tools/fleet.py: rendering, the checks that keep a bad composition off devices,
and which fleets a merge pushes."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import fleet  # noqa: E402

FRAGMENT = textwrap.dedent(
    """\
    version: '2.1'
    volumes:
      {volume}: {{}}
    services:
      {service}:
        image: bh.cr/BALENA_BLOCK_SLUG/BALENA_BLOCK_VERSION
        network_mode: host
        volumes:
          - {volume}:/data
    """
)


class Tree:
    """A throwaway repository tree with fleets/ and services/."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "fleets").mkdir()

    def cleanup(self):
        shutil.rmtree(self.root)

    def service(self, name, version, fragment=None, block=None, tamper=False):
        directory = self.root / "services" / name
        (directory / version).mkdir(parents=True, exist_ok=True)
        (directory / "service.yml").write_text(
            yaml.safe_dump(
                {
                    "repository": f"example/{name}",
                    "fragment": "deploy/balena/fleet/docker-compose.yml",
                    "block": block or f"example/{name}-aarch64",
                }
            )
        )
        text = fragment if fragment is not None else FRAGMENT.format(service=name, volume=f"{name}-data")
        raw = text.encode()
        (directory / version / "docker-compose.yml").write_bytes(raw + (b"# edited\n" if tamper else b""))
        (directory / version / "source.yml").write_text(
            yaml.safe_dump(
                {"tag": f"v{version}", "commit": "a" * 40, "sha256": hashlib.sha256(raw).hexdigest()}
            )
        )

    def fleet(self, fleet_id="site", version="2.0.0", deploy=True, services=None, **extra):
        data = {
            "name": "Site",
            "slug": "example/site",
            "version": version,
            "deploy": deploy,
            "services": services if services is not None else {"svc": "1.0.0"},
        }
        data.update(extra)
        (self.root / "fleets" / f"{fleet_id}.yml").write_text(yaml.safe_dump(data))

    def copy(self):
        other = Tree()
        shutil.rmtree(other.root)
        shutil.copytree(self.root, other.root)
        return other


class TreeCase(unittest.TestCase):
    def tree(self):
        tree = Tree()
        self.addCleanup(tree.cleanup)
        return tree

    def copy(self, tree):
        other = tree.copy()
        self.addCleanup(other.cleanup)
        return other

    def assertProblem(self, tree, fragment, base=None):
        problems = fleet.check(tree.root, base.root if base else None)
        self.assertTrue(
            any(fragment in p for p in problems), f"expected a problem containing {fragment!r}, got {problems}"
        )


class TheRealFleet(unittest.TestCase):
    """The fleets actually committed here."""

    def test_check_is_clean(self):
        self.assertEqual(fleet.check(REPO), [])

    def test_360stjacques_runs_printcapture_as_crew_printcapture_pushes_it(self):
        # crew-printcapture's deploy.sh pushed its fragment with the two
        # placeholders sed-substituted and nothing else. Rendering through
        # this repository must give devices the same composition, or the
        # cutover restarts (or reconfigures) the running service.
        manifest = fleet.load_fleet(REPO, "360stjacques")
        version = manifest["services"]["crew-printcapture"]
        block = fleet.load_service(REPO, "crew-printcapture")["block"]
        fragment = (REPO / "services" / "crew-printcapture" / version / "docker-compose.yml").read_text()
        as_printcapture_pushes = yaml.safe_load(
            fragment.replace("BALENA_BLOCK_SLUG", block).replace("BALENA_BLOCK_VERSION", version)
        )
        rendered = yaml.safe_load(fleet.render(REPO, manifest)["docker-compose.yml"])
        # Other services joining the fleet must leave printcapture's own service and volume exactly as
        # crew-printcapture pushed them: a changed service config is a restart, mid-service.
        self.assertEqual(rendered["version"], as_printcapture_pushes["version"])
        for kind in ("services", "volumes"):
            for name, value in as_printcapture_pushes[kind].items():
                self.assertEqual(rendered[kind][name], value, f"{kind[:-1]} {name}")

    def test_360stjacques_keeps_the_names_balena_keys_state_to(self):
        # Service variables are scoped to the service name, and the volume
        # holds the undelivered spool and the operator's config.yaml.
        rendered = yaml.safe_load(fleet.render(REPO, fleet.load_fleet(REPO, "360stjacques"))["docker-compose.yml"])
        self.assertIn("printcapture", rendered["services"])
        self.assertIn("printcapture-data", rendered["volumes"])


class Render(TreeCase):
    def test_substitutes_block_and_version(self):
        tree = self.tree()
        tree.service("svc", "1.0.0", block="example/svc-aarch64")
        tree.fleet()
        out = fleet.render(tree.root, fleet.load_fleet(tree.root, "site"))
        doc = yaml.safe_load(out["docker-compose.yml"])
        self.assertEqual(doc["services"]["svc"]["image"], "bh.cr/example/svc-aarch64/1.0.0")
        self.assertEqual(yaml.safe_load(out["balena.yml"])["type"], "sw.application")
        self.assertEqual(out["meta"]["release_tags"], [["svc", "1.0.0"]])

    def test_merges_services_from_several_projects(self):
        tree = self.tree()
        tree.service("one", "1.0.0")
        tree.service("two", "3.2.1")
        tree.fleet(services={"one": "1.0.0", "two": "3.2.1"})
        doc = yaml.safe_load(fleet.render(tree.root, fleet.load_fleet(tree.root, "site"))["docker-compose.yml"])
        self.assertEqual(set(doc["services"]), {"one", "two"})
        self.assertEqual(set(doc["volumes"]), {"one-data", "two-data"})

    def test_write_render_lays_out_a_push_source(self):
        tree = self.tree()
        tree.service("svc", "1.0.0")
        tree.fleet()
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out)
        target = fleet.write_render(tree.root, "site", out)
        self.assertEqual(sorted(p.name for p in (target / "source").iterdir()), ["balena.yml", "docker-compose.yml"])
        self.assertTrue((target / "meta.json").is_file())


class Refuses(TreeCase):
    def test_an_edited_vendored_fragment(self):
        tree = self.tree()
        tree.service("svc", "1.0.0", tamper=True)
        tree.fleet()
        self.assertProblem(tree, "never edited here")

    def test_a_service_name_two_projects_both_use(self):
        tree = self.tree()
        tree.service("one", "1.0.0", fragment=FRAGMENT.format(service="app", volume="one-data"))
        tree.service("two", "1.0.0", fragment=FRAGMENT.format(service="app", volume="two-data"))
        tree.fleet(services={"one": "1.0.0", "two": "1.0.0"})
        self.assertProblem(tree, "service 'app' is defined by both one and two")

    def test_a_volume_name_two_projects_both_use(self):
        tree = self.tree()
        tree.service("one", "1.0.0", fragment=FRAGMENT.format(service="one", volume="data"))
        tree.service("two", "1.0.0", fragment=FRAGMENT.format(service="two", volume="data"))
        tree.fleet(services={"one": "1.0.0", "two": "1.0.0"})
        self.assertProblem(tree, "volume 'data' is defined by both one and two")

    def test_a_fragment_without_the_image_placeholder(self):
        tree = self.tree()
        tree.service("svc", "1.0.0", fragment="services:\n  svc:\n    image: nginx\n")
        tree.fleet()
        self.assertProblem(tree, "no `image:")

    def test_a_service_running_some_other_image(self):
        tree = self.tree()
        text = FRAGMENT.format(service="svc", volume="d") + "  extra:\n    image: nginx\n"
        tree.service("svc", "1.0.0", fragment=text)
        tree.fleet()
        self.assertProblem(tree, "service extra must use image")

    def test_top_level_keys_with_no_merge_rule(self):
        tree = self.tree()
        tree.service("svc", "1.0.0", fragment=FRAGMENT.format(service="svc", volume="d") + "networks: {}\n")
        tree.fleet()
        self.assertProblem(tree, "top-level networks is not supported")

    def test_an_unquoted_or_non_semver_version(self):
        tree = self.tree()
        tree.service("svc", "1.0.0")
        tree.fleet(services={"svc": 1.0})
        self.assertProblem(tree, "is not a quoted X.Y.Z")

    def test_a_service_name_that_escapes_services_dir(self):
        tree = self.tree()
        tree.fleet(services={"../etc": "1.0.0"})
        self.assertProblem(tree, "does not match")

    def test_unknown_manifest_keys(self):
        tree = self.tree()
        tree.service("svc", "1.0.0")
        tree.fleet(typo=True)
        self.assertProblem(tree, "unknown typo")

    def test_a_vendored_release_whose_tag_names_another_version(self):
        tree = self.tree()
        tree.service("svc", "1.0.0")
        source = tree.root / "services" / "svc" / "1.0.0" / "source.yml"
        source.write_text(source.read_text().replace("v1.0.0", "v1.0.1"))
        tree.fleet()
        self.assertProblem(tree, "does not name version 1.0.0")


class VersionBumps(TreeCase):
    def test_a_changed_composition_needs_a_new_version(self):
        base = self.tree()
        base.service("svc", "1.0.0")
        base.fleet()
        head = self.copy(base)
        head.service("svc", "1.1.0")
        head.fleet(services={"svc": "1.1.0"})
        self.assertProblem(head, "raise it", base=base)
        head.fleet(services={"svc": "1.1.0"}, version="2.1.0")
        self.assertEqual(fleet.check(head.root, base.root), [])

    def test_a_version_never_goes_down(self):
        base = self.tree()
        base.service("svc", "1.0.0")
        base.fleet(version="2.1.0")
        head = self.copy(base)
        head.fleet(version="2.0.9")
        self.assertProblem(head, "is lower than", base=base)

    def test_a_new_fleet_needs_no_base(self):
        base = self.tree()
        base.service("svc", "1.0.0")
        head = self.copy(base)
        head.fleet()
        self.assertEqual(fleet.check(head.root, base.root), [])


class Changed(TreeCase):
    def setUp(self):
        self.base = self.tree()
        self.base.service("svc", "1.0.0")
        self.base.service("svc", "1.1.0")
        self.base.fleet()

    def test_nothing_changed_pushes_nothing(self):
        head = self.copy(self.base)
        self.assertEqual(fleet.changed(head.root, self.base.root), [])

    def test_a_new_service_version_pushes(self):
        head = self.copy(self.base)
        head.fleet(services={"svc": "1.1.0"}, version="2.1.0")
        self.assertEqual(fleet.changed(head.root, self.base.root), ["site"])

    def test_a_fleet_with_deploy_off_never_pushes(self):
        head = self.copy(self.base)
        head.fleet(services={"svc": "1.1.0"}, version="2.1.0", deploy=False)
        self.assertEqual(fleet.changed(head.root, self.base.root), [])

    def test_switching_deploy_on_pushes_even_when_nothing_else_changed(self):
        # The cutover: the first crew-balena release of a fleet that
        # crew-printcapture used to push to.
        self.base.fleet(deploy=False)
        head = self.copy(self.base)
        head.fleet(deploy=True)
        self.assertEqual(fleet.changed(head.root, self.base.root), ["site"])

    def test_renaming_the_fleet_slug_alone_does_not_push(self):
        # The balenaCloud rename (syneo/crew -> syneo/360stjacques) is done in
        # the dashboard; the manifest follows it without a new release.
        head = self.copy(self.base)
        head.fleet(slug="example/renamed")
        self.assertEqual(fleet.changed(head.root, self.base.root), [])

    def test_a_fleet_new_at_this_merge_pushes(self):
        head = self.copy(self.base)
        head.fleet("other")
        self.assertEqual(fleet.changed(head.root, self.base.root), ["other"])


class Cli(TreeCase):
    def test_check_exit_codes(self):
        tree = self.tree()
        tree.service("svc", "1.0.0")
        tree.fleet()
        self.assertEqual(fleet.main(["--root", str(tree.root), "check"]), 0)
        tree.fleet(version="2.0")
        self.assertEqual(fleet.main(["--root", str(tree.root), "check"]), 1)


if __name__ == "__main__":
    unittest.main()
