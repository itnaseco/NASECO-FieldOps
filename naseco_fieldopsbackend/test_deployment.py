# Copyright (c) 2026, NASECO and contributors
# For license information, please see license.txt

import json
import unittest
from pathlib import Path

import frappe

from naseco_fieldopsbackend.deployment import FIXTURES, TRANSACTIONAL_DOCTYPES


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures"


class TestDeploymentFixtures(unittest.TestCase):
	def _fixture_records(self):
		for fixture in FIXTURES:
			doctype = fixture["dt"]
			path = FIXTURE_DIRECTORY / f"{frappe.scrub(doctype)}.json"
			yield doctype, json.loads(path.read_text())

	def test_fixture_manifest_excludes_operational_doctypes(self):
		fixture_doctypes = {fixture["dt"] for fixture in FIXTURES}
		self.assertFalse(fixture_doctypes & TRANSACTIONAL_DOCTYPES)

	def test_fixture_directory_matches_manifest(self):
		expected = {frappe.scrub(fixture["dt"]) for fixture in FIXTURES}
		actual = {path.stem for path in FIXTURE_DIRECTORY.glob("*.json")}
		self.assertEqual(actual, expected)

	def test_fixture_files_contain_only_the_declared_doctype(self):
		for doctype, records in self._fixture_records():
			self.assertTrue(records, f"{doctype} fixture must not be empty")
			self.assertEqual({record.get("doctype") for record in records}, {doctype})
			self.assertFalse(
				{record.get("doctype") for record in records} & TRANSACTIONAL_DOCTYPES
			)

	def test_unrelated_site_customizations_are_not_fixtures(self):
		fixture_doctypes = {fixture["dt"] for fixture in FIXTURES}
		self.assertNotIn("Custom Field", fixture_doctypes)
		self.assertNotIn("Client Script", fixture_doctypes)
		self.assertNotIn("User", fixture_doctypes)
		self.assertNotIn("Company", fixture_doctypes)

	def test_fixtures_do_not_capture_site_users(self):
		for doctype, records in self._fixture_records():
			for record in records:
				self.assertFalse(
					record.get("default_assigned_to"),
					f"{doctype} {record.get('name')} contains a site-specific assignee",
				)
				serialized = json.dumps(record)
				self.assertNotIn("@", serialized, f"{doctype} fixture contains an email address")
