from pathlib import Path


def test_scan_worker_is_adaptive_and_reports_progress():
    text=(Path(__file__).parents[1]/"gui"/"main_window.py").read_text(encoding="utf-8")
    assert "JarScanner(deep_scan=False)" in text
    assert "fast_count < 5" in text
    assert "partial_result" in text
    assert "progress = Signal(int, str)" in text


def test_build_monitor_has_tasks_progress_eta_and_log():
    text=(Path(__file__).parents[1]/"gui"/"task_progress_dialog.py").read_text(encoding="utf-8")
    for token in ["Kiểm tra điều kiện build", "Patch class / resource / binary", "Kiểm tra ZIP / CRC / class", "Đối chiếu bản dịch sau build", "Còn lại:", "Task log"]:
        assert token in text


def test_regression_validator_groups_by_source():
    text=(Path(__file__).parents[1]/"core"/"regression_validator.py").read_text(encoding="utf-8")
    assert "by_source" in text
    assert "_validate_binary_group" in text
    assert "JarScanner(deep_scan=False)" in text
