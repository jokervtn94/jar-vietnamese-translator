from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set
import zipfile


@dataclass
class DependencyPath:
    root: str
    target: str
    path: List[str] = field(default_factory=list)
    startup_reachable: bool = False


@dataclass
class ClassDependencyReport:
    roots: List[str] = field(default_factory=list)
    graph: Dict[str, List[str]] = field(default_factory=dict)
    activation_paths: List[DependencyPath] = field(default_factory=list)
    startup_activation_reachable: bool = False
    startup_payment_reachable: bool = False
    notes: List[str] = field(default_factory=list)


class ClassDependencyInspector:
    """Conservative static dependency graph for classes contained in a JAR.

    The inspector does not decompile or patch code. It derives class-to-class
    references from constant-pool-style class names and starts reachability from
    MIDlet classes declared in MANIFEST.MF. This answers whether suspicious
    activation/payment classes are at least statically reachable from startup.
    """

    def _manifest(self, z: zipfile.ZipFile) -> Dict[str, str]:
        try:
            data = z.read("META-INF/MANIFEST.MF")
        except KeyError:
            return {}
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        logical: List[str] = []
        for line in text.split("\n"):
            if line.startswith(" ") and logical:
                logical[-1] += line[1:]
            else:
                logical.append(line)
        out: Dict[str, str] = {}
        for line in logical:
            if ":" in line:
                key, value = line.split(":", 1)
                out[key.strip()] = value.strip()
        return out

    @staticmethod
    def _entry_to_class(entry: str) -> str:
        return entry[:-6].replace("/", ".") if entry.lower().endswith(".class") else entry

    @staticmethod
    def _internal_name(class_name: str) -> bytes:
        return class_name.replace(".", "/").encode("ascii", errors="ignore")

    @staticmethod
    def _is_activation_name(name: str) -> bool:
        low = name.lower()
        return any(x in low for x in (
            "activate", "activation", "register", "registration", "license", "licence",
            "unlock", "pay", "payment", "billing", "purchase", "subscribe", "subscription",
            "sms", "premium", "charge",
        ))

    @staticmethod
    def _is_payment_name(name: str) -> bool:
        low = name.lower()
        return any(x in low for x in (
            "pay", "payment", "billing", "purchase", "subscribe", "subscription",
            "premium", "charge",
        ))

    def _roots_from_manifest(self, manifest: Dict[str, str], classes: Set[str]) -> List[str]:
        roots: List[str] = []
        for key, value in manifest.items():
            if not key.lower().startswith("midlet-") or key.lower() in {"midlet-name", "midlet-vendor", "midlet-version"}:
                continue
            parts = [p.strip() for p in value.split(",")]
            if not parts:
                continue
            candidate = parts[-1]
            if candidate in classes and candidate not in roots:
                roots.append(candidate)
        return roots

    def _shortest_path(self, graph: Dict[str, List[str]], root: str, target: str) -> List[str]:
        if root == target:
            return [root]
        queue: List[List[str]] = [[root]]
        seen = {root}
        while queue:
            path = queue.pop(0)
            for nxt in graph.get(path[-1], []):
                if nxt in seen:
                    continue
                new_path = path + [nxt]
                if nxt == target:
                    return new_path
                seen.add(nxt)
                queue.append(new_path)
        return []

    def analyze(self, jar_path: str, suspicious_classes: List[str] | None = None) -> ClassDependencyReport:
        report = ClassDependencyReport()
        suspicious_classes = suspicious_classes or []

        with zipfile.ZipFile(jar_path, "r") as z:
            entries = [i.filename for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith(".class")]
            classes = {self._entry_to_class(e) for e in entries}
            entry_by_class = {self._entry_to_class(e): e for e in entries}
            manifest = self._manifest(z)
            report.roots = self._roots_from_manifest(manifest, classes)

            graph: Dict[str, List[str]] = {}
            internal_names = {name: self._internal_name(name) for name in classes}
            for class_name, entry in entry_by_class.items():
                try:
                    data = z.read(entry)
                except Exception:
                    graph[class_name] = []
                    continue
                refs = []
                for target, marker in internal_names.items():
                    if target == class_name or not marker:
                        continue
                    if marker in data:
                        refs.append(target)
                graph[class_name] = sorted(set(refs))
            report.graph = graph

        suspicious_names: Set[str] = set()
        for entry in suspicious_classes:
            suspicious_names.add(self._entry_to_class(entry))
        suspicious_names.update(name for name in report.graph if self._is_activation_name(name))

        for target in sorted(suspicious_names):
            best: List[str] = []
            best_root = ""
            for root in report.roots:
                path = self._shortest_path(report.graph, root, target)
                if path and (not best or len(path) < len(best)):
                    best = path
                    best_root = root
            reachable = bool(best)
            report.activation_paths.append(DependencyPath(
                root=best_root or (report.roots[0] if report.roots else ""),
                target=target,
                path=best,
                startup_reachable=reachable,
            ))
            if reachable:
                report.startup_activation_reachable = True
                if self._is_payment_name(target):
                    report.startup_payment_reachable = True

        if not report.roots:
            report.notes.append("Không xác định được MIDlet entry class từ MANIFEST.MF; reachability từ startup chưa thể kết luận.")
        elif report.startup_activation_reachable:
            report.notes.append("Có class activation/payment statically reachable từ MIDlet entry class; đây là tín hiệu startup-path mạnh hơn tên class đơn lẻ.")
        else:
            report.notes.append("Không tìm thấy đường tham chiếu tĩnh từ MIDlet entry class tới class activation/payment đã nhận diện. Flow có thể là chức năng phụ hoặc dùng dispatch động.")
        return report
