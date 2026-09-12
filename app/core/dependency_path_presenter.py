from __future__ import annotations


def summarize_dependency_path(flow_report) -> str:
    dependency = getattr(flow_report, "dependency", None)
    if dependency is None:
        return "Không có dữ liệu dependency graph"

    reachable = [
        item for item in getattr(dependency, "activation_paths", [])
        if getattr(item, "startup_reachable", False)
    ]
    if reachable:
        best = max(reachable, key=lambda item: (len(getattr(item, "path", []) or []), getattr(item, "target", "")))
        path = " -> ".join(best.path)
        return "Startup reachable: " + path

    roots = getattr(dependency, "roots", [])
    suspicious = getattr(flow_report, "suspicious_classes", [])
    if roots and suspicious:
        return "Không tìm thấy static path từ MIDlet entry tới class nghi vấn"
    if not roots:
        return "Chưa xác định được MIDlet entry class từ MANIFEST.MF"
    return "Không có class nghi vấn cần kiểm tra dependency path"
