"""Contract tests for ridge classes and the Sangyeongpyo reference system.

The plugin grades ridges by rank inside the supplied DEM extent. The Korean
named hierarchy (daegan / jeonggan / jeongmaek) is fixed at national scale.
These tests exist to keep the second from being used as a label for the first.
"""

import copy
import json
import os
import unittest

from feng_shui_gis import korean_ridge_system as krs
from feng_shui_gis.korean_ridge_system import (
    computed_ridge_class_ids,
    computed_ridge_classes,
    named_ridge_system,
    named_system_disclaimer,
    named_system_requirement,
    ridge_catalog,
    ridge_class_definition,
    ridge_class_is_extent_relative,
    ridge_class_label,
)

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "feng_shui_gis",
    "config",
)

# The proper nouns of the national system. A computed grade must never be
# presented to the user under any of these.
SANGYEONGPYO_NAMES = ("대간", "정간", "정맥", "기맥", "지맥")


class ComputedClassTests(unittest.TestCase):
    def test_catalog_declares_the_classes_the_analysis_assigns(self):
        self.assertEqual(set(computed_ridge_class_ids()), {"major", "minor"})

    def test_every_class_has_a_label_and_a_definition(self):
        for entry in computed_ridge_classes():
            for language in ("ko", "en"):
                self.assertTrue(ridge_class_label(entry["id"], language), entry["id"])
                self.assertTrue(
                    ridge_class_definition(entry["id"], language), entry["id"]
                )

    def test_computed_grades_are_marked_extent_relative(self):
        # Widening or narrowing the DEM changes the rank, so nothing here is an
        # absolute property of the ridge.
        for class_id in computed_ridge_class_ids():
            self.assertTrue(ridge_class_is_extent_relative(class_id), class_id)

    def test_unknown_class_degrades_to_its_id(self):
        self.assertEqual(ridge_class_label("nope", "ko"), "nope")
        self.assertEqual(ridge_class_definition("nope", "ko"), "")
        self.assertFalse(ridge_class_is_extent_relative("nope"))


class NamedSystemSeparationTests(unittest.TestCase):
    def test_computed_labels_never_use_sangyeongpyo_proper_nouns(self):
        for entry in computed_ridge_classes():
            for language in ("ko", "en", "zh"):
                label = ridge_class_label(entry["id"], language)
                for name in SANGYEONGPYO_NAMES:
                    self.assertNotIn(
                        name,
                        label,
                        f"computed class {entry['id']} is labelled with '{name}'",
                    )

    def test_ridge_legend_does_not_reuse_sangyeongpyo_proper_nouns(self):
        with open(os.path.join(CONFIG_DIR, "ui_texts.json"), encoding="utf-8") as handle:
            ui_texts = json.load(handle)
        for row in ui_texts["ridge_legend"]:
            for label in row["label"].values():
                for name in SANGYEONGPYO_NAMES:
                    self.assertNotIn(name, label, f"legend row {row['id']}: {label}")

    def test_plugin_does_not_claim_to_identify_the_named_system(self):
        self.assertIs(named_ridge_system()["identified_by_this_plugin"], False)

    def test_named_system_records_the_real_hierarchy(self):
        ranks = {rank["id"]: rank for rank in named_ridge_system()["ranks"]}
        self.assertEqual(ranks["daegan"]["count"], 1)
        self.assertEqual(ranks["jeonggan"]["count"], 1)
        self.assertEqual(ranks["jeongmaek"]["count"], 13)
        # The lower branches have no settled inventory, so no count is claimed.
        self.assertIsNone(ranks["gimaek_jimaek"]["count"])

    def test_disclaimer_and_requirement_are_available_to_the_ui(self):
        for language in ("ko", "en"):
            self.assertTrue(named_system_disclaimer(language))
            self.assertTrue(named_system_requirement(language))

    def test_class_ids_do_not_collide_with_named_ranks(self):
        rank_ids = {rank["id"] for rank in named_ridge_system()["ranks"]}
        self.assertFalse(rank_ids & set(computed_ridge_class_ids()))


class CatalogValidationTests(unittest.TestCase):
    def _validate(self, mutate):
        catalog = copy.deepcopy(ridge_catalog())
        mutate(catalog)
        return krs._validate(catalog)

    def test_valid_catalog_passes(self):
        self.assertIsNotNone(self._validate(lambda catalog: None))

    def test_claiming_to_identify_the_named_system_is_rejected(self):
        # Flipping this flag without doing the spatial match would reinstate
        # exactly the overreach this catalog exists to prevent.
        def mutate(catalog):
            catalog["named_system"]["identified_by_this_plugin"] = True

        with self.assertRaises(RuntimeError):
            self._validate(mutate)

    def test_missing_definition_is_rejected(self):
        def mutate(catalog):
            catalog["computed_classes"][0].pop("definition")

        with self.assertRaises(RuntimeError):
            self._validate(mutate)

    def test_duplicate_class_id_is_rejected(self):
        def mutate(catalog):
            catalog["computed_classes"].append(
                copy.deepcopy(catalog["computed_classes"][0])
            )

        with self.assertRaises(RuntimeError):
            self._validate(mutate)

    def test_class_id_colliding_with_a_named_rank_is_rejected(self):
        def mutate(catalog):
            catalog["computed_classes"][0]["id"] = "jeongmaek"

        with self.assertRaises(RuntimeError):
            self._validate(mutate)

    def test_dropping_the_disclaimer_is_rejected(self):
        def mutate(catalog):
            catalog["named_system"].pop("why_not_identified")

        with self.assertRaises(RuntimeError):
            self._validate(mutate)


if __name__ == "__main__":
    unittest.main()
