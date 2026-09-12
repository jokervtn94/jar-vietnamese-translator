from pathlib import Path

from core.compatibility_report import CompatibilityExport, RecommendedAction
from core.diagnostic_history import DiagnosticHistoryStore


def _report(index: int) -> CompatibilityExport:
    return CompatibilityExport(
        generated_at_utc=f"2026-09-12T06:{index:02d}:00+00:00",
        jar_name=f"game-{index}.jar",
        compatibility_score=100 - index,
        runtime_risk="high" if index % 2 else "medium",
        startup_title="Likely startup blocker" if index % 2 else "Needs runtime test",
        startup_severity="high" if index % 2 else "medium",
        recommended_actions=[
            RecommendedAction(
                priority=1,
                category="startup_path",
                title="Kiểm tra class trên startup path",
                detail=f"game.Main{index} -> game.Check{index}",
            )
        ],
    )


def test_history_keeps_only_latest_ten_and_round_trips(tmp_path):
    store = DiagnosticHistoryStore(tmp_path / "history.json", max_items=10)

    for index in range(12):
        store.add(
            _report(index),
            tmp_path / f"report-{index}.compat.json",
            tmp_path / f"report-{index}.compat.txt",
        )

    entries = store.load()
    assert len(entries) == 10
    assert entries[0].jar_name == "game-11.jar"
    assert entries[-1].jar_name == "game-2.jar"
    assert entries[0].next_action.startswith("P1 · Kiểm tra class trên startup path")


def test_history_deduplicates_same_report_path(tmp_path):
    store = DiagnosticHistoryStore(tmp_path / "history.json", max_items=10)
    json_path = tmp_path / "same.compat.json"
    txt_path = tmp_path / "same.compat.txt"

    store.add(_report(1), json_path, txt_path)
    store.add(_report(2), json_path, txt_path)

    entries = store.load()
    assert len(entries) == 1
    assert entries[0].jar_name == "game-2.jar"
    assert Path(entries[0].json_path).name == "same.compat.json"
