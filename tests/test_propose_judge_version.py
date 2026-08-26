"""Tests for scripts/09_propose_judge_version.py (mocked API — no real calls)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parent.parent / "scripts" / "09_propose_judge_version.py"
_spec = importlib.util.spec_from_file_location("propose_judge_version", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

assert_safe_paths = _mod.assert_safe_paths
preserved_sections = _mod.preserved_sections
verify_preserved = _mod.verify_preserved
split_output = _mod.split_output
propose = _mod.propose
SEP = _mod.RATIONALE_SEPARATOR

TEMPLATE = (
    "You are a judge. Framing sentence.\n\n"
    "### RUBRIC DIMENSIONS\n"
    "- dim_a: original definition.\n\n"
    "### IMPORTANT NOTE\n"
    "clarification.\n\n"
    "### CALIBRATION EXAMPLES\n"
    "These are excluded.\n\n"
    "{{CALIBRATION_EXAMPLES}}"
    "### INSTRUCTIONS\n"
    "Call the tool. Output booleans."
)
# Valid edit: only a rubric definition changes.
CANDIDATE = TEMPLATE.replace("- dim_a: original definition.", "- dim_a: clearer definition.")


# --------------------------------------------------------------------------- #
# Mock API
# --------------------------------------------------------------------------- #

class _Block:
    type = "text"
    def __init__(self, text): self.text = text

class _Resp:
    def __init__(self, text): self.content = [_Block(text)]

class _Messages:
    def __init__(self, text): self._text = text
    def create(self, **kwargs): return _Resp(self._text)

class FakeClient:
    def __init__(self, text): self.messages = _Messages(text)


# --------------------------------------------------------------------------- #
# assert_safe_paths
# --------------------------------------------------------------------------- #

class TestSafePaths:
    def test_allows_normal_paths(self):
        assert_safe_paths([Path("judge_prompts/v1.txt"), Path("stats_dev_v1.md"),
                           Path("judge_prompts/v2.candidate.txt")])

    @pytest.mark.parametrize("bad", [
        "judge_prompts/FROZEN",
        "data/processed_mrbench/calibration.csv",
        "judge_test.csv",
        "judge_test_results.jsonl",
        "src/claude_behavior_eval/judge.py",
    ])
    def test_refuses_forbidden(self, bad):
        with pytest.raises(ValueError):
            assert_safe_paths([Path(bad)])


# --------------------------------------------------------------------------- #
# preserved sections / verification
# --------------------------------------------------------------------------- #

class TestPreserved:
    def test_extracts_opening_and_instructions(self):
        opening, instructions = preserved_sections(TEMPLATE)
        assert opening == "You are a judge. Framing sentence.\n\n"
        assert instructions == "### INSTRUCTIONS\nCall the tool. Output booleans."

    def test_valid_candidate_passes(self):
        assert verify_preserved(TEMPLATE, CANDIDATE) == []

    def test_changed_opening_fails(self):
        bad = CANDIDATE.replace("Framing sentence.", "Different framing.")
        assert "opening framing was modified" in verify_preserved(TEMPLATE, bad)

    def test_changed_instructions_fails(self):
        bad = CANDIDATE.replace("Output booleans.", "Output something else.")
        assert "output/tool instructions were modified" in verify_preserved(TEMPLATE, bad)

    def test_missing_marker_fails(self):
        bad = CANDIDATE.replace("{{CALIBRATION_EXAMPLES}}", "")
        assert any("marker" in p for p in verify_preserved(TEMPLATE, bad))


# --------------------------------------------------------------------------- #
# split_output
# --------------------------------------------------------------------------- #

class TestSplit:
    def test_splits_candidate_and_rationale(self):
        text = f"{CANDIDATE}\n{SEP}\n- dim_a FN 5 rows ids: a,b,c"
        cand, rat = split_output(text)
        assert cand == CANDIDATE
        assert rat.startswith("- dim_a FN")

    def test_missing_separator_raises(self):
        with pytest.raises(ValueError):
            split_output("no separator here")


# --------------------------------------------------------------------------- #
# propose (mock client)
# --------------------------------------------------------------------------- #

def test_propose_returns_text():
    out = propose(FakeClient("HELLO"), "m", "cur", "stats", "dis")
    assert out == "HELLO"


# --------------------------------------------------------------------------- #
# main() integration (mocked Anthropic)
# --------------------------------------------------------------------------- #

def _setup(tmp_path: Path):
    cur = tmp_path / "v1.txt"; cur.write_text(TEMPLATE, encoding="utf-8")
    stats = tmp_path / "stats_dev_v1.md"; stats.write_text("stats", encoding="utf-8")
    dis = tmp_path / "disagreements_v1.md"; dis.write_text("dis", encoding="utf-8")
    out = tmp_path / "v2.candidate.txt"
    rat = tmp_path / "v2.rationale.md"
    argv = ["--current", str(cur), "--stats", str(stats), "--disagreements", str(dis),
            "--out", str(out), "--rationale", str(rat), "--model", "test-model"]
    return out, rat, argv


def test_main_success_writes_out_and_rationale(tmp_path, monkeypatch):
    out, rat, argv = _setup(tmp_path)
    model_text = f"{CANDIDATE}\n{SEP}\n- dim_a FN 4 rows ids: a,b,c; rule: X"
    monkeypatch.setattr(_mod, "Anthropic", lambda *a, **k: FakeClient(model_text))
    _mod.main(argv)
    assert out.read_text(encoding="utf-8") == CANDIDATE
    assert "dim_a FN" in rat.read_text(encoding="utf-8")
    assert not _mod._rejected_path(out).exists()


def test_main_rejects_preserved_violation(tmp_path, monkeypatch):
    out, rat, argv = _setup(tmp_path)
    bad = CANDIDATE.replace("Output booleans.", "Output something else.")
    model_text = f"{bad}\n{SEP}\nrationale"
    monkeypatch.setattr(_mod, "Anthropic", lambda *a, **k: FakeClient(model_text))
    with pytest.raises(SystemExit) as exc:
        _mod.main(argv)
    assert exc.value.code != 0
    assert not out.exists()
    assert _mod._rejected_path(out).read_text(encoding="utf-8") == bad
    assert not rat.exists()


def test_main_rejects_missing_separator(tmp_path, monkeypatch):
    out, rat, argv = _setup(tmp_path)
    monkeypatch.setattr(_mod, "Anthropic", lambda *a, **k: FakeClient("no separator at all"))
    with pytest.raises(SystemExit) as exc:
        _mod.main(argv)
    assert exc.value.code != 0
    assert _mod._rejected_path(out).read_text(encoding="utf-8") == "no separator at all"
    assert not out.exists()


def test_main_refuses_forbidden_path(tmp_path, monkeypatch):
    _, _, argv = _setup(tmp_path)
    # Point --out at judge.py; must exit before any API call.
    argv[argv.index("--out") + 1] = str(tmp_path / "judge.py")
    called = {"api": False}
    monkeypatch.setattr(_mod, "Anthropic",
                        lambda *a, **k: called.__setitem__("api", True) or FakeClient(""))
    with pytest.raises(SystemExit):
        _mod.main(argv)
    assert called["api"] is False
