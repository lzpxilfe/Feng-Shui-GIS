"""Contract tests for the cross-language term ontology.

The point of these is not that Chinese labels exist, but that the repository
cannot quietly claim a Korean term and a Chinese term are the same thing.
"""

import copy
import unittest

from feng_shui_gis import profile_catalog
from feng_shui_gis.profile_catalog import (
    label_language_codes,
    label_languages,
    normalize_label_language,
    term_catalog,
    term_correspondence,
    term_correspondence_note,
    term_label,
    term_labels,
    term_ontology,
    term_ontology_entry,
    term_zh_variants,
)


class LabelLanguageContractTests(unittest.TestCase):
    def test_chinese_label_languages_are_declared(self):
        codes = label_language_codes()
        for expected in ("ko", "en", "zh", "zh_hant", "pinyin"):
            self.assertIn(expected, codes)

    def test_every_declared_language_renders_every_term(self):
        for term_id in term_labels():
            for code in label_language_codes():
                label = term_label(term_id, code)
                self.assertTrue(label, f"{term_id} has no label for {code}")
                self.assertNotEqual(
                    label,
                    term_id,
                    f"{term_id} falls back to its raw id in {code}",
                )

    def test_declared_languages_carry_display_names(self):
        for row in label_languages():
            self.assertTrue(
                row["label"].get("en"),
                f"label language {row['code']} has no English display name",
            )

    def test_regional_chinese_codes_do_not_fall_back_to_korean(self):
        for code in ("zh", "zh_CN", "zh-cn", "zh_Hans"):
            self.assertEqual(normalize_label_language(code), "zh", code)
        for code in ("zh_hant", "zh-TW", "zh_HK", "zh_mo"):
            self.assertEqual(normalize_label_language(code), "zh_hant", code)

    def test_unknown_language_falls_back_to_the_default(self):
        self.assertEqual(normalize_label_language("fr"), "ko")
        self.assertEqual(normalize_label_language(None), "ko")
        self.assertEqual(normalize_label_language(""), "ko")
        self.assertEqual(normalize_label_language("de", default="en"), "en")

    def test_simplified_and_traditional_labels_differ_where_the_script_differs(self):
        self.assertEqual(term_label("naecheongnyong", "zh"), "内青龙")
        self.assertEqual(term_label("naecheongnyong", "zh_hant"), "內青龍")


class TermOntologyContractTests(unittest.TestCase):
    def test_compass_school_is_declared_out_of_scope(self):
        scope = term_ontology()["scope"]
        self.assertIn("xingshi", scope["in_scope_schools"])
        self.assertIn("liqi", scope["out_of_scope_schools"])
        self.assertFalse(term_ontology()["schools"]["liqi"]["in_scope"])

    def test_every_term_declares_a_school_and_correspondence(self):
        levels = set(term_ontology()["correspondence_levels"])
        for term_id in term_labels():
            entry = term_ontology_entry(term_id)
            self.assertEqual(
                entry.get("school"),
                "xingshi",
                f"{term_id} is not scoped to the landform school",
            )
            self.assertIn(term_correspondence(term_id), levels, term_id)

    def test_weak_correspondences_explain_themselves(self):
        weak = [
            term_id
            for term_id in term_labels()
            if term_correspondence(term_id) != "direct"
        ]
        self.assertTrue(weak, "expected at least one qualified mapping")
        for term_id in weak:
            for language in ("ko", "en", "zh"):
                self.assertTrue(
                    term_correspondence_note(term_id, language),
                    f"{term_id} is graded {term_correspondence(term_id)} "
                    f"but has no {language} note",
                )

    def test_misa_is_flagged_as_a_repository_choice(self):
        # The one mapping with no settled equivalent in the literature; it must
        # never present itself as an established translation.
        self.assertEqual(term_correspondence("misa"), "contested")
        self.assertIn("毡唇", term_zh_variants("misa"))

    def test_computed_field_layers_are_not_sold_as_classical_entities(self):
        for term_id in ("jangpung", "sashinsa", "hyeoljang"):
            self.assertEqual(term_correspondence(term_id), "approximate", term_id)


class TermCatalogValidationTests(unittest.TestCase):
    def _validate(self, mutate):
        catalog = copy.deepcopy(term_catalog())
        mutate(catalog)
        return profile_catalog._validate_term_catalog(catalog)

    def test_valid_catalog_passes(self):
        self.assertIsNotNone(self._validate(lambda catalog: None))

    def test_qualified_mapping_without_a_note_is_rejected(self):
        def mutate(catalog):
            catalog["term_ontology"]["terms"]["jusan"]["correspondence"] = "contested"

        with self.assertRaises(RuntimeError):
            self._validate(mutate)

    def test_term_missing_from_the_ontology_is_rejected(self):
        def mutate(catalog):
            catalog["term_ontology"]["terms"].pop("jusan")

        with self.assertRaises(RuntimeError):
            self._validate(mutate)

    def test_out_of_scope_school_is_rejected(self):
        def mutate(catalog):
            catalog["term_ontology"]["terms"]["jusan"]["school"] = "liqi"

        with self.assertRaises(RuntimeError):
            self._validate(mutate)

    def test_language_no_term_can_render_is_rejected(self):
        def mutate(catalog):
            catalog["label_languages"].append(
                {"code": "de", "label": {"en": "German"}}
            )

        with self.assertRaises(RuntimeError):
            self._validate(mutate)

    def test_dropping_a_required_language_is_rejected(self):
        def mutate(catalog):
            catalog["label_languages"] = [
                row for row in catalog["label_languages"] if row["code"] != "en"
            ]

        with self.assertRaises(RuntimeError):
            self._validate(mutate)


if __name__ == "__main__":
    unittest.main()
