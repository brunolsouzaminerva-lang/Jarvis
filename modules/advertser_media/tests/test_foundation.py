"""Exercise security and persistence boundaries using temporary fixtures only.

Run from the checkout with:
    python -m unittest discover -s modules/advertser_media/tests -v
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock
from uuid import UUID


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from advertser_media import (  # noqa: E402
    AuthenticationFailed,
    AuthenticationNotConfigured,
    ClientProfile,
    MarketingService,
    ModuleConfig,
    PermissionDenied,
    Principal,
    Role,
    StorageIsolationError,
    UnknownClient,
    ValidationError,
)


CLIENT_A = UUID("00000000-0000-4000-8000-00000000000a")
CLIENT_B = UUID("00000000-0000-4000-8000-00000000000b")
UNKNOWN_CLIENT = UUID("00000000-0000-4000-8000-00000000000c")


class FakeVerifier:
    """A test-only verifier; the product has no built-in test login."""

    def __init__(self, identities):
        self.identities = dict(identities)
        self.calls = []

    def verify(self, credential):
        self.calls.append(credential)
        if not isinstance(credential, str) or credential not in self.identities:
            raise ValueError("unrecognized synthetic credential")
        principal = self.identities[credential]
        if isinstance(principal, Exception):
            raise principal
        return principal


def tree_bytes(root):
    """Capture bytes and directory names, without following symbolic links."""
    if not root.exists():
        return None
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("link", str(path.readlink()))
        elif path.is_file():
            result[relative] = ("file", path.read_bytes())
        else:
            result[relative] = ("dir",)
    return result


class MarketingFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="advertser-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.runtime = self.base / "runtime"
        self.config = ModuleConfig(
            data_root=self.runtime,
            allowed_clients=frozenset({CLIENT_A, CLIENT_B}),
        )
        self.verifier = FakeVerifier({
            "manager-a": Principal("manager-a", frozenset({Role.MANAGER}), frozenset({CLIENT_A})),
            "manager-b": Principal("manager-b", frozenset({Role.MANAGER}), frozenset({CLIENT_B})),
            "admin-a": Principal("admin-a", frozenset({Role.ADMIN}), frozenset({CLIENT_A})),
            "viewer-a": Principal("viewer-a", frozenset({Role.VIEWER}), frozenset({CLIENT_A})),
            "admin-both": Principal("admin-both", frozenset({Role.ADMIN}), frozenset({CLIENT_A, CLIENT_B})),
        })
        self.service = MarketingService(self.config, identity_verifier=self.verifier)

    def profile(self, client_id=CLIENT_A, **changes):
        fields = dict(
            client_id=client_id,
            name="Synthetic client A" if client_id == CLIENT_A else "Synthetic client B",
            segment="Synthetic segment",
            target_audience="Adults in a fictional market",
            objectives=("Build awareness", "Measure qualified leads"),
            monthly_fee=Decimal("1234.50"),
            currency="BRL",
            account_manager="Synthetic account owner",
        )
        fields.update(changes)
        return ClientProfile(**fields)

    def database(self, client_id=CLIENT_A):
        return self.runtime / "advertser_media" / "clients" / str(client_id) / "marketing.sqlite3"

    def audit_table(self, connection):
        for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            columns = {row[1] for row in connection.execute('PRAGMA table_info("' + name.replace('"', '""') + '")')}
            if {"event_id", "actor_id", "action", "occurred_at"} <= columns:
                return name
        self.fail("No audit table with the documented audit fields")

    @contextmanager
    def failing_audit_insert(self):
        """Deny the actual audit insert after the business write has run."""
        real_connect = sqlite3.connect
        attempted = []

        def connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)

            def authorize(action, table, column, database, source):
                if action == sqlite3.SQLITE_INSERT and table == "audit_events":
                    attempted.append(table)
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            connection.set_authorizer(authorize)
            return connection

        with mock.patch("advertser_media.storage.sqlite3.connect", side_effect=connect):
            yield attempted

    def test_profiles_persist_across_instances_and_each_client_has_its_own_database(self):
        profile_a = self.profile()
        profile_b = self.profile(CLIENT_B, monthly_fee=Decimal("99.99"))
        self.assertEqual(self.service.upsert_client("manager-a", profile_a), profile_a)
        self.assertEqual(self.service.upsert_client("manager-b", profile_b), profile_b)
        reopened = MarketingService(self.config, identity_verifier=self.verifier)
        self.assertEqual(reopened.get_client("manager-a", CLIENT_A), profile_a)
        self.assertEqual(reopened.get_client("manager-b", CLIENT_B), profile_b)
        self.assertTrue(self.database().is_file())
        self.assertTrue(self.database(CLIENT_B).is_file())
        self.assertFalse(self.database().samefile(self.database(CLIENT_B)))
        self.assertNotIn(profile_b.name.encode(), self.database().read_bytes())
        self.assertNotIn(profile_a.name.encode(), self.database(CLIENT_B).read_bytes())

    def test_missing_client_reads_and_audit_reads_create_no_runtime_files(self):
        self.assertIsNone(self.service.get_client("manager-a", CLIENT_A))
        self.assertEqual(self.service.list_audit("manager-a", CLIENT_A), ())
        self.assertIsNone(tree_bytes(self.runtime))

    def test_create_and_update_have_exactly_one_audit_event_in_the_correct_client(self):
        original = self.profile()
        self.service.upsert_client("manager-a", original)
        updated = replace(original, name="Updated synthetic name")
        self.service.upsert_client("admin-a", updated)
        events = self.service.list_audit("manager-a", CLIENT_A)
        self.assertEqual([event.action for event in events], ["client.created", "client.updated"])
        self.assertEqual([event.actor_id for event in events], ["manager-a", "admin-a"])
        self.assertEqual({event.client_id for event in events}, {CLIENT_A})
        self.assertEqual(len({event.event_id for event in events}), 2)
        for event in events:
            self.assertIsInstance(event.event_id, UUID)
            occurred = datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
            self.assertEqual(occurred.utcoffset(), timezone.utc.utcoffset(occurred))
        self.assertEqual(self.service.get_client("manager-a", CLIENT_A), updated)
        self.assertEqual(self.service.list_audit("manager-b", CLIENT_B), ())
        self.assertFalse(self.database(CLIENT_B).exists())

    def test_viewer_can_read_but_cannot_write_or_read_audit(self):
        original = self.profile()
        self.service.upsert_client("manager-a", original)
        before = tree_bytes(self.runtime)
        self.assertEqual(self.service.get_client("viewer-a", CLIENT_A), original)
        with self.assertRaises(PermissionDenied):
            self.service.upsert_client("viewer-a", replace(original, name="Forbidden"))
        with self.assertRaises(PermissionDenied):
            self.service.list_audit("viewer-a", CLIENT_A)
        self.assertEqual(tree_bytes(self.runtime), before)

    def test_admin_is_scoped_and_cannot_create_another_clients_database(self):
        for action in (
            lambda: self.service.get_client("admin-a", CLIENT_B),
            lambda: self.service.upsert_client("admin-a", self.profile(CLIENT_B)),
            lambda: self.service.list_audit("admin-a", CLIENT_B),
        ):
            with self.subTest(action=action), self.assertRaises(PermissionDenied):
                action()
        self.assertIsNone(tree_bytes(self.runtime))

    def test_cross_client_operations_cannot_read_or_modify_existing_clients(self):
        self.service.upsert_client("manager-a", self.profile())
        self.service.upsert_client("manager-b", self.profile(CLIENT_B))
        before = tree_bytes(self.runtime)
        for action in (
            lambda: self.service.get_client("manager-a", CLIENT_B),
            lambda: self.service.upsert_client("manager-a", self.profile(CLIENT_B, name="Forbidden")),
            lambda: self.service.list_audit("manager-a", CLIENT_B),
            lambda: self.service.get_client("manager-b", CLIENT_A),
        ):
            with self.subTest(action=action), self.assertRaises(PermissionDenied):
                action()
        self.assertEqual(tree_bytes(self.runtime), before)

    def test_unknown_client_is_rejected_even_when_trusted_principal_claims_it(self):
        self.verifier.identities["unknown-admin"] = Principal(
            "unknown-admin", frozenset({Role.ADMIN}), frozenset({UNKNOWN_CLIENT})
        )
        for action in (
            lambda: self.service.get_client("unknown-admin", UNKNOWN_CLIENT),
            lambda: self.service.upsert_client("unknown-admin", self.profile(UNKNOWN_CLIENT)),
            lambda: self.service.list_audit("unknown-admin", UNKNOWN_CLIENT),
        ):
            with self.subTest(action=action), self.assertRaises(UnknownClient):
                action()
        self.assertIsNone(tree_bytes(self.runtime))

    def test_default_auth_refuses_every_operation_before_creating_any_files(self):
        closed = MarketingService(self.config)
        for action in (
            lambda: closed.get_client("anything", CLIENT_A),
            lambda: closed.upsert_client("anything", self.profile()),
            lambda: closed.list_audit("anything", CLIENT_A),
        ):
            with self.subTest(action=action), self.assertRaises(AuthenticationNotConfigured):
                action()
        self.assertIsNone(tree_bytes(self.runtime))

    def test_authentication_precedes_any_inspection_of_untrusted_profile_objects(self):
        marker = self.base / "hostile-profile-property-accessed"

        class HostileProfile:
            @property
            def client_id(self):
                marker.write_bytes(b"synthetic property side effect")
                raise AssertionError("Untrusted profile was inspected before authentication")

        for service, credential, error in (
            (MarketingService(self.config), "anything", AuthenticationNotConfigured),
            (self.service, "invalid-synthetic-credential", AuthenticationFailed),
        ):
            with self.subTest(error=error.__name__), self.assertRaises(error):
                service.upsert_client(credential, HostileProfile())
            self.assertFalse(marker.exists())
            self.assertFalse(self.runtime.exists())

    def test_caller_role_claims_and_test_login_strings_cannot_authenticate(self):
        credentials = (
            "admin", "manager", "test", "manager-a;role=admin",
            json.dumps({"user_id": "intruder", "roles": ["admin"], "client_ids": [str(CLIENT_A)]}),
            {"user_id": "intruder", "roles": ["admin"], "client_ids": [str(CLIENT_A)]},
            self.verifier.identities["admin-a"],
        )
        for credential in credentials:
            with self.subTest(credential=type(credential).__name__), self.assertRaises(AuthenticationFailed):
                self.service.upsert_client(credential, self.profile())
        self.assertIsNone(tree_bytes(self.runtime))

    def test_verifier_failure_or_invalid_result_fails_closed_without_files(self):
        for result in (None, {}, "admin", RuntimeError("synthetic verifier failure")):
            self.verifier.identities["bad-verifier"] = result
            with self.subTest(result=type(result).__name__), self.assertRaises(AuthenticationFailed):
                self.service.upsert_client("bad-verifier", self.profile())
        self.assertIsNone(tree_bytes(self.runtime))

    def test_authorization_is_rechecked_after_revocation_and_between_clients(self):
        self.service.upsert_client("manager-a", self.profile())
        before = tree_bytes(self.runtime)
        self.verifier.identities["manager-a"] = Principal(
            "manager-a", frozenset({Role.VIEWER}), frozenset({CLIENT_A})
        )
        with self.assertRaises(PermissionDenied):
            self.service.upsert_client("manager-a", self.profile(name="After revocation"))
        self.assertEqual(tree_bytes(self.runtime), before)
        self.verifier.identities["manager-a"] = Principal(
            "manager-a", frozenset({Role.MANAGER}), frozenset({CLIENT_B})
        )
        with self.assertRaises(PermissionDenied):
            self.service.get_client("manager-a", CLIENT_A)
        self.assertIsNone(self.service.get_client("manager-a", CLIENT_B))
        self.assertEqual(tree_bytes(self.runtime), before)

    def test_protected_synthetic_ggo_tree_stays_byte_identical_after_writes_and_errors(self):
        protected = self.base / "synthetic-ggo"
        fixtures = {
            "main.py": b"# synthetic protected entrypoint\n",
            "ui.py": b"# synthetic protected visual adapter\n",
            "GGO/DUX/BASE.xlsx": b"synthetic-workbook-bytes\x00\x01",
            "GGO/previous-cycle.xlsx": b"synthetic-history-bytes",
            "config/settings.json": b'{"synthetic": true}',
            "memory/fixture.txt": b"synthetic memory bytes",
        }
        for relative, payload in fixtures.items():
            path = protected / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        before = tree_bytes(protected)
        config = ModuleConfig(self.runtime, frozenset({CLIENT_A, CLIENT_B}), (protected,))
        service = MarketingService(config, identity_verifier=self.verifier)
        service.upsert_client("manager-a", self.profile())
        service.get_client("manager-a", CLIENT_A)
        service.list_audit("manager-a", CLIENT_A)
        with self.assertRaises(PermissionDenied):
            service.upsert_client("manager-a", self.profile(CLIENT_B))
        self.assertEqual(tree_bytes(protected), before)

    def test_runtime_cannot_be_placed_inside_a_protected_tree(self):
        protected = self.base / "synthetic-ggo"
        protected.mkdir()
        (protected / "BASE.xlsx").write_bytes(b"synthetic protected workbook")
        before = tree_bytes(protected)
        with self.assertRaises((ValidationError, StorageIsolationError)):
            config = ModuleConfig(protected / "runtime", frozenset({CLIENT_A}), (protected,))
            MarketingService(config, identity_verifier=self.verifier).upsert_client("manager-a", self.profile())
        self.assertEqual(tree_bytes(protected), before)

    def test_symlink_components_and_database_cannot_redirect_client_storage(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "sentinel").write_bytes(b"synthetic outside sentinel")
        for component in ("root", "module", "client", "database"):
            with self.subTest(component=component):
                runtime = self.base / ("runtime-" + component)
                target = runtime / "advertser_media" / "clients" / str(CLIENT_A) / "marketing.sqlite3"
                if component == "root":
                    link, destination = runtime, outside
                elif component == "module":
                    runtime.mkdir()
                    link, destination = runtime / "advertser_media", outside
                elif component == "client":
                    target.parent.parent.mkdir(parents=True)
                    link, destination = target.parent, outside
                else:
                    target.parent.mkdir(parents=True)
                    destination = outside / "synthetic-existing.sqlite3"
                    destination.write_bytes(b"do not replace this synthetic file")
                    link = target
                try:
                    link.symlink_to(destination, target_is_directory=component != "database")
                except (NotImplementedError, OSError) as error:
                    self.skipTest("Symlinks unavailable on this platform: " + str(error))
                before = tree_bytes(outside)
                with self.assertRaises((ValidationError, StorageIsolationError)):
                    config = ModuleConfig(runtime, frozenset({CLIENT_A}))
                    service = MarketingService(config, identity_verifier=self.verifier)
                    service.upsert_client("manager-a", self.profile())
                self.assertEqual(tree_bytes(outside), before)

    def test_copied_database_for_another_client_is_never_reused_or_rewritten(self):
        self.service.upsert_client("manager-a", self.profile())
        self.database(CLIENT_B).parent.mkdir(parents=True)
        shutil.copyfile(self.database(), self.database(CLIENT_B))
        before = tree_bytes(self.runtime)
        for action in (
            lambda: self.service.get_client("manager-b", CLIENT_B),
            lambda: self.service.upsert_client("manager-b", self.profile(CLIENT_B)),
            lambda: self.service.list_audit("manager-b", CLIENT_B),
        ):
            with self.subTest(action=action), self.assertRaises(StorageIsolationError):
                action()
        self.assertEqual(tree_bytes(self.runtime), before)
        self.assertEqual(self.service.get_client("manager-a", CLIENT_A), self.profile())

    def test_links_to_another_clients_valid_database_cannot_share_storage(self):
        self.service.upsert_client("manager-a", self.profile())
        target = self.database(CLIENT_B)
        target.parent.mkdir(parents=True)
        for kind in ("symlink", "hardlink"):
            with self.subTest(kind=kind):
                try:
                    if kind == "symlink":
                        target.symlink_to(self.database())
                    else:
                        os.link(self.database(), target)
                except (NotImplementedError, OSError) as error:
                    self.skipTest("Filesystem links unavailable: " + str(error))
                before = tree_bytes(self.runtime)
                for action in (
                    lambda: self.service.get_client("manager-b", CLIENT_B),
                    lambda: self.service.upsert_client("manager-b", self.profile(CLIENT_B)),
                    lambda: self.service.list_audit("manager-b", CLIENT_B),
                ):
                    with self.assertRaises(StorageIsolationError):
                        action()
                self.assertEqual(tree_bytes(self.runtime), before)
                target.unlink()
        self.assertEqual(self.service.get_client("manager-a", CLIENT_A), self.profile())

    def test_corrupt_or_foreign_existing_database_is_not_bootstrapped_or_replaced(self):
        self.service.upsert_client("manager-a", self.profile())
        for kind in ("corrupt", "foreign"):
            with self.subTest(kind=kind):
                target = self.database(CLIENT_B)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.unlink()
                if kind == "corrupt":
                    target.write_bytes(b"synthetic corrupt SQLite file\x00")
                else:
                    with sqlite3.connect(target) as connection:
                        connection.execute("CREATE TABLE unrelated_fixture (value TEXT)")
                        connection.execute("INSERT INTO unrelated_fixture VALUES ('synthetic foreign data')")
                before = tree_bytes(self.runtime)
                for action in (
                    lambda: self.service.get_client("manager-b", CLIENT_B),
                    lambda: self.service.upsert_client("manager-b", self.profile(CLIENT_B)),
                ):
                    with self.assertRaises(StorageIsolationError):
                        action()
                self.assertEqual(tree_bytes(self.runtime), before)

    def test_invalid_module_metadata_is_rejected_without_repairing_the_database(self):
        self.service.upsert_client("manager-a", self.profile())
        for column, value in (("module", "synthetic-other-module"), ("schema_version", 999)):
            with self.subTest(column=column):
                target = self.database(CLIENT_B)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.database(), target)
                with sqlite3.connect(target) as connection:
                    connection.execute("UPDATE module_metadata SET client_id = ?", (str(CLIENT_B),))
                    connection.execute('UPDATE module_metadata SET "' + column + '" = ?', (value,))
                before = tree_bytes(self.runtime)
                with self.assertRaises(StorageIsolationError):
                    self.service.upsert_client("manager-b", self.profile(CLIENT_B))
                self.assertEqual(tree_bytes(self.runtime), before)

    def test_trigger_name_resembling_sqlite_internal_prefix_is_rejected_without_mutation(self):
        self.service.upsert_client("manager-a", self.profile())
        with sqlite3.connect(self.database()) as connection:
            connection.execute(
                "CREATE TRIGGER sqliteXevil AFTER INSERT ON audit_events "
                "BEGIN DELETE FROM audit_events; END"
            )
        before = tree_bytes(self.runtime)
        with self.assertRaises(StorageIsolationError):
            self.service.upsert_client("manager-a", self.profile(name="Forbidden trigger update"))
        self.assertEqual(tree_bytes(self.runtime), before)

    def test_trigger_and_table_with_the_same_name_cannot_hide_schema_tampering(self):
        self.service.upsert_client("manager-a", self.profile())
        with sqlite3.connect(self.database()) as connection:
            metadata_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='module_metadata'"
            ).fetchone()[0]
            metadata = connection.execute("SELECT * FROM module_metadata").fetchone()
            connection.execute("DROP TABLE module_metadata")
            connection.execute(
                "CREATE TRIGGER module_metadata AFTER INSERT ON audit_events "
                "BEGIN DELETE FROM audit_events; END"
            )
            connection.execute(metadata_sql)
            connection.execute("INSERT INTO module_metadata VALUES (?, ?, ?)", metadata)
        before = tree_bytes(self.runtime)
        with self.assertRaises(StorageIsolationError):
            self.service.upsert_client("manager-a", self.profile(name="Forbidden duplicate-name update"))
        self.assertEqual(tree_bytes(self.runtime), before)

    def test_stored_objectives_must_be_a_json_list_instead_of_silently_coercing_values(self):
        self.service.upsert_client("manager-a", self.profile())
        for value in ("synthetic string", {"synthetic key": "synthetic value"}, None, 42):
            with self.subTest(value=value):
                with sqlite3.connect(self.database()) as connection:
                    connection.execute("UPDATE client_profile SET objectives = ?", (json.dumps(value),))
                before = tree_bytes(self.runtime)
                with self.assertRaises(StorageIsolationError):
                    self.service.get_client("manager-a", CLIENT_A)
                self.assertEqual(tree_bytes(self.runtime), before)

    def test_audit_failure_rolls_back_profile_update_and_retry_has_one_event(self):
        original = self.profile()
        self.service.upsert_client("manager-a", original)
        with self.failing_audit_insert() as attempted:
            with self.assertRaises(StorageIsolationError):
                self.service.upsert_client("manager-a", replace(original, name="Failed update"))
        self.assertEqual(attempted, ["audit_events"])
        self.assertEqual(self.service.get_client("manager-a", CLIENT_A), original)
        self.assertEqual(len(self.service.list_audit("manager-a", CLIENT_A)), 1)
        updated = replace(original, name="Successful retry")
        self.service.upsert_client("manager-a", updated)
        self.assertEqual(self.service.get_client("manager-a", CLIENT_A), updated)
        self.assertEqual(len(self.service.list_audit("manager-a", CLIENT_A)), 2)

    def test_failed_first_audit_write_leaves_no_profile_and_can_be_retried(self):
        with self.failing_audit_insert() as attempted:
            with self.assertRaises(StorageIsolationError):
                self.service.upsert_client("manager-a", self.profile())
        self.assertEqual(attempted, ["audit_events"])
        self.assertIsNone(self.service.get_client("manager-a", CLIENT_A))
        self.assertEqual(self.service.list_audit("manager-a", CLIENT_A), ())
        self.service.upsert_client("manager-a", self.profile())
        self.assertEqual(self.service.get_client("manager-a", CLIENT_A), self.profile())
        self.assertEqual([event.action for event in self.service.list_audit("manager-a", CLIENT_A)], ["client.created"])

    def test_audit_stores_only_identifiers_action_actor_and_time_without_payload_or_credentials(self):
        credential = "synthetic-credential-secret-6a16"
        self.verifier.identities[credential] = self.verifier.identities["manager-a"]
        profile = self.profile(
            name="private-name-8d3f", segment="private-segment-9c2a",
            target_audience="private-audience-1e7b", objectives=("private-objective-2f6c",),
            account_manager="private-manager-3a5d", monthly_fee=Decimal("9876.54"),
        )
        self.service.upsert_client(credential, profile)
        with sqlite3.connect(self.database()) as connection:
            name = self.audit_table(connection)
            cursor = connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"')
            columns = {column[0] for column in cursor.description}
            rows = repr(cursor.fetchall())
        self.assertEqual(columns, {"event_id", "client_id", "actor_id", "action", "occurred_at"})
        for secret in (credential, profile.name, profile.segment, profile.target_audience,
                       profile.objectives[0], profile.account_manager, str(profile.monthly_fee)):
            self.assertNotIn(secret, rows)
        self.assertNotIn(credential.encode(), self.database().read_bytes())

    def test_money_round_trips_as_decimal_and_unspecified_fee_stays_absent(self):
        for amount in (None, Decimal("0"), Decimal("0.01"), Decimal("987654321.99")):
            with self.subTest(amount=amount):
                profile = self.profile(monthly_fee=amount)
                self.service.upsert_client("manager-a", profile)
                actual = self.service.get_client("manager-a", CLIENT_A)
                self.assertEqual(actual.monthly_fee, amount)
                if amount is not None:
                    self.assertIsInstance(actual.monthly_fee, Decimal)

    def test_invalid_money_values_are_rejected_before_persistence(self):
        for amount in (Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity"),
                       Decimal("-0.01"), Decimal("1.001"), 10.5, 10, "10.00", True):
            with self.subTest(amount=str(amount)), self.assertRaises(ValidationError):
                self.service.upsert_client("manager-a", self.profile(monthly_fee=amount))
        self.assertIsNone(tree_bytes(self.runtime))

    def test_invalid_client_ids_and_profile_fields_cannot_become_storage_paths(self):
        for client_id in ("../outside", "/tmp/escape", "..\\outside", "C:\\outside", str(CLIENT_A), None):
            with self.subTest(client_id=client_id), self.assertRaises(ValidationError):
                self.service.upsert_client("manager-a", self.profile(client_id))
        for changes in ({"name": ""}, {"name": "   "}, {"name": None},
                        {"objectives": ["mutable list"]}, {"objectives": (None,)},
                        {"currency": "brl"}, {"account_manager": 123}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.service.upsert_client("manager-a", self.profile(**changes))
        self.assertIsNone(tree_bytes(self.runtime))

    def test_import_and_readiness_have_no_file_network_thread_or_private_import_side_effects(self):
        script = textwrap.dedent(r'''
            import builtins, datetime, decimal, enum, importlib.abc, json, os
            import pathlib, socket, sqlite3, sys, threading, typing, uuid
            sys.dont_write_bytecode = True
            sys.path.insert(0, sys.argv[1])
            blocked = {'main', 'ui', 'tools', 'integracao', 'jarvis', 'ggo', 'pyqt6',
                       'pyside6', 'tkinter', 'requests', 'httpx', 'fastapi', 'uvicorn',
                       'google', 'facebook', 'meta'}
            class BlockPrivateImports(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split('.')[0].lower() in blocked:
                        raise AssertionError('unrelated import: ' + fullname)
            sys.meta_path.insert(0, BlockPrivateImports())
            def forbidden(*args, **kwargs):
                raise AssertionError('unexpected thread or network operation')
            threading.Thread.start = forbidden
            socket.socket = forbidden
            socket.create_connection = forbidden
            socket.getaddrinfo = forbidden
            def audit(event, args):
                if event == 'open':
                    filename, mode, flags = args
                    caller = sys._getframe(1)
                    assert caller.f_globals.get('__name__') == 'importlib._bootstrap_external', 'resource access outside Python loader'
                    if isinstance(filename, (str, bytes)):
                        suffix = os.fsdecode(filename)
                        assert suffix.endswith(('.py', '.pyc', '.so', '.pyd')), ('resource read or write', suffix)
                    assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND), 'file write'
                assert event not in {'os.mkdir', 'os.remove', 'os.rename', 'os.rmdir', 'subprocess.Popen',
                                     'socket.connect', 'socket.bind', 'sqlite3.connect'}, event
            sys.addaudithook(audit)
            import advertser_media
            from advertser_media import AuthenticationNotConfigured, ClientProfile, MarketingService, ModuleConfig
            os.stat = forbidden
            os.lstat = forbidden
            os.listdir = forbidden
            os.scandir = forbidden
            config = ModuleConfig(pathlib.Path.cwd() / 'must-not-exist', frozenset({uuid.UUID(int=1)}))
            service = MarketingService(config)
            status = service.readiness()
            profile = ClientProfile(uuid.UUID(int=1), 'Synthetic client')
            for operation in (lambda: service.get_client('synthetic', profile.client_id),
                              lambda: service.upsert_client('synthetic', profile),
                              lambda: service.list_audit('synthetic', profile.client_id)):
                try:
                    operation()
                except AuthenticationNotConfigured:
                    pass
                else:
                    raise AssertionError('default authentication did not fail closed')
            assert isinstance(status, dict), status
            assert all(isinstance(key, str) and isinstance(value, str) for key, value in status.items()), status
            assert not (blocked & {name.split('.')[0].lower() for name in sys.modules}), 'private import loaded'
            print(json.dumps(status, sort_keys=True))
        ''')
        process = subprocess.run(
            [sys.executable, "-I", "-B", "-c", script, str(PACKAGE_ROOT)],
            cwd=self.base, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        status = json.loads(process.stdout)
        self.assertTrue(status)
        values = " ".join(status.values()).lower().replace("_", " ").replace("-", " ")
        self.assertTrue("not configured" in values or "não configurado" in values, status)
        self.assertFalse(any(key.lower() in {"spend", "revenue", "roas", "clicks", "impressions", "leads"} for key in status))
        self.assertEqual(list(self.base.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
