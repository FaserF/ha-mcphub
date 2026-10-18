"""Test that all translation keys are present in EN and DE."""

import json
from pathlib import Path

import pytest

INTEGRATION_DIR = next(
    p
    for p in (Path(__file__).resolve().parent.parent / "custom_components").iterdir()
    if p.is_dir() and p.name != "__pycache__"
)
STRINGS_FILE = INTEGRATION_DIR / "strings.json"
TRANSLATIONS_DIR = INTEGRATION_DIR / "translations"
REQUIRED_LANGUAGES = ["en", "de"]


def _flatten_keys(data: dict, prefix: str = "") -> set[str]:
    """Recursively flatten JSON keys into dot-separated paths."""
    keys: set[str] = set()
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.update(_flatten_keys(value, full_key))
        else:
            keys.add(full_key)
    return keys


def test_strings_json_exists():
    """Verify strings.json exists."""
    assert STRINGS_FILE.exists(), f"strings.json not found at {STRINGS_FILE}"


@pytest.mark.parametrize("lang", REQUIRED_LANGUAGES)
def test_translation_file_exists(lang: str):
    """Verify required translation files exist."""
    path = TRANSLATIONS_DIR / f"{lang}.json"
    assert path.exists(), f"Translation file {lang}.json is missing at {path}"


def test_translation_files_parity():
    """Ensure every key in strings.json, en.json, and de.json matches exactly."""
    with open(STRINGS_FILE, encoding="utf-8") as f:
        strings_data = json.load(f)
    strings_keys = _flatten_keys(strings_data)

    for lang in REQUIRED_LANGUAGES:
        translation_file = TRANSLATIONS_DIR / f"{lang}.json"
        with open(translation_file, encoding="utf-8") as f:
            translation_data = json.load(f)
        translation_keys = _flatten_keys(translation_data)

        missing_in_translation = strings_keys - translation_keys
        extra_in_translation = translation_keys - strings_keys

        assert not missing_in_translation, (
            f"{lang}.json is missing keys present in strings.json: {missing_in_translation}"
        )
        assert not extra_in_translation, (
            f"{lang}.json has extra keys not in strings.json: {extra_in_translation}"
        )
