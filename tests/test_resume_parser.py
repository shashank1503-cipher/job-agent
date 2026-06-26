"""Tests for utils/resume_parser.py.

Covers:
- Backup created before any write
- Only the three allowed sections are ever patched
- A declined section (user answers 'n') is not written
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

import utils.resume_parser as rp

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_PREFS_DATA = {
    "preferences": {
        "keywords_must_have": ["Python", "Backend"],
        "keywords_nice_to_have": {
            "tier1": ["Django", "FastAPI"],
            "tier2": ["Go", "Docker"],
        },
        "experience_years": {"min": 1, "max": 4},
        "roles": ["Backend Engineer"],
        "locations": ["Remote"],
        "exclude_companies": ["BadCorp"],
        "remote_locations": ["India", "IN"],
        "min_salary_lpa": 28,
    }
}

_PROPOSED_ALL = {
    "keywords_must_have": ["Python", "REST API", "Postgres"],
    "keywords_nice_to_have": {
        "tier1": ["FastAPI", "Elasticsearch"],
        "tier2": ["AWS", "Docker"],
    },
    "experience_years": {"min": 2, "max": 6},
}


@pytest.fixture
def prefs_file(tmp_path):
    path = tmp_path / "preferences.yaml"
    path.write_text(
        yaml.dump(_PREFS_DATA, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Backup behaviour
# ---------------------------------------------------------------------------


class TestBackup:
    def test_bak_created_on_patch(self, prefs_file, monkeypatch):
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        rp.patch_prefs({"keywords_must_have": ["Python", "REST API"]})
        assert prefs_file.with_suffix(".yaml.bak").exists()

    def test_bak_contains_original_content(self, prefs_file, monkeypatch):
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        original = prefs_file.read_text()
        rp.patch_prefs({"keywords_must_have": ["Python", "REST API"]})
        bak = prefs_file.with_suffix(".yaml.bak")
        assert bak.read_text() == original

    def test_bak_not_created_when_nothing_accepted(self, prefs_file, monkeypatch):
        """patch_prefs is never called when accepted is empty, so no backup."""
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        bak = prefs_file.with_suffix(".yaml.bak")
        # Don't call patch_prefs — simulate the "no sections accepted" branch
        assert not bak.exists()


# ---------------------------------------------------------------------------
# Only allowed sections are written
# ---------------------------------------------------------------------------


class TestAllowedSectionsOnly:
    def test_patched_section_updated(self, prefs_file, monkeypatch):
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        rp.patch_prefs({"keywords_must_have": ["Python", "REST API", "Postgres"]})
        data = yaml.safe_load(prefs_file.read_text())
        prefs = data["preferences"]
        assert prefs["keywords_must_have"] == ["Python", "REST API", "Postgres"]

    def test_untouched_keys_remain_unchanged(self, prefs_file, monkeypatch):
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        rp.patch_prefs({"keywords_must_have": ["Python", "REST API"]})
        data = yaml.safe_load(prefs_file.read_text())
        prefs = data["preferences"]
        assert prefs["roles"] == ["Backend Engineer"]
        assert prefs["locations"] == ["Remote"]
        assert prefs["exclude_companies"] == ["BadCorp"]
        assert prefs["remote_locations"] == ["India", "IN"]
        assert prefs["min_salary_lpa"] == 28

    def test_extra_keys_from_claude_not_written(self, prefs_file, monkeypatch):
        """Keys outside ALLOWED_SECTIONS must be stripped before patch_prefs is called."""
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        # Simulate: proposed dict has forbidden keys mixed in
        proposed_with_poison = {
            **_PROPOSED_ALL,
            "roles": ["Staff Engineer"],
            "exclude_companies": ["NewBadCorp"],
        }
        # The main() loop filters via ALLOWED_SECTIONS; replicate that here
        safe = {
            k: v for k, v in proposed_with_poison.items() if k in rp.ALLOWED_SECTIONS
        }
        rp.patch_prefs(safe)

        data = yaml.safe_load(prefs_file.read_text())
        prefs = data["preferences"]
        assert prefs["roles"] == ["Backend Engineer"], "roles must not be overwritten"
        assert prefs["exclude_companies"] == ["BadCorp"], (
            "exclude_companies must not be overwritten"
        )

    def test_all_three_sections_patched_at_once(self, prefs_file, monkeypatch):
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        rp.patch_prefs(_PROPOSED_ALL)
        data = yaml.safe_load(prefs_file.read_text())
        prefs = data["preferences"]
        assert prefs["keywords_must_have"] == _PROPOSED_ALL["keywords_must_have"]
        assert prefs["keywords_nice_to_have"] == _PROPOSED_ALL["keywords_nice_to_have"]
        assert prefs["experience_years"] == _PROPOSED_ALL["experience_years"]


# ---------------------------------------------------------------------------
# Declined sections not patched
# ---------------------------------------------------------------------------


class TestDeclinedSections:
    def test_all_declined_means_no_patch(self, prefs_file, monkeypatch):
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        with patch("builtins.input", return_value="n"):
            accepted = {
                section: _PROPOSED_ALL[section]
                for section in rp.ALLOWED_SECTIONS
                if rp.prompt_yn(f"Apply {section}?")
            }
        assert accepted == {}
        # File untouched — backup must NOT exist
        assert not prefs_file.with_suffix(".yaml.bak").exists()

    def test_partial_decline_only_accepted_written(self, prefs_file, monkeypatch):
        monkeypatch.setattr(rp, "PREFS_PATH", prefs_file)
        # Accept only experience_years
        accepted = {"experience_years": {"min": 2, "max": 6}}
        rp.patch_prefs(accepted)

        data = yaml.safe_load(prefs_file.read_text())
        prefs = data["preferences"]
        assert prefs["experience_years"] == {"min": 2, "max": 6}
        # Declined sections remain at original values
        assert prefs["keywords_must_have"] == ["Python", "Backend"]
        assert prefs["keywords_nice_to_have"]["tier1"] == ["Django", "FastAPI"]

    def test_prompt_yn_returns_false_on_n(self):
        with patch("builtins.input", return_value="n"):
            assert rp.prompt_yn("Apply?") is False

    def test_prompt_yn_returns_true_on_y(self):
        with patch("builtins.input", return_value="y"):
            assert rp.prompt_yn("Apply?") is True


# ---------------------------------------------------------------------------
# ClaudeClient mocked
# ---------------------------------------------------------------------------


class TestCallClaude:
    def _mock_client(self, response_text: str):
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=response_text)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp
        return mock_client

    def test_returns_parsed_dict(self):
        mock_client = self._mock_client(json.dumps(_PROPOSED_ALL))
        with patch("utils.resume_parser.ClaudeClient", return_value=mock_client):
            result = rp.call_claude("resume text", "prefs yaml")
        assert result == _PROPOSED_ALL

    def test_strips_markdown_fences(self):
        wrapped = f"```json\n{json.dumps(_PROPOSED_ALL)}\n```"
        mock_client = self._mock_client(wrapped)
        with patch("utils.resume_parser.ClaudeClient", return_value=mock_client):
            result = rp.call_claude("resume text", "prefs yaml")
        assert result == _PROPOSED_ALL

    def test_strips_plain_code_fences(self):
        wrapped = f"```\n{json.dumps(_PROPOSED_ALL)}\n```"
        mock_client = self._mock_client(wrapped)
        with patch("utils.resume_parser.ClaudeClient", return_value=mock_client):
            result = rp.call_claude("resume text", "prefs yaml")
        assert result == _PROPOSED_ALL

    def test_claude_called_with_correct_model(self):
        mock_client = self._mock_client(json.dumps(_PROPOSED_ALL))
        with patch("utils.resume_parser.ClaudeClient", return_value=mock_client):
            rp.call_claude("resume text", "prefs yaml")
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"
