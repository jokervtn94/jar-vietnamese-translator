from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set
import zipfile

from core.class_dependency_inspector import ClassDependencyInspector, ClassDependencyReport


NAME_HINTS = (
    "activate", "activation", "active", "register", "registration", "license", "licence",
    "unlock", "payment", "billing", "purchase", "pay", "subscribe", "subscription",
    "sms", "fee", "charge", "premium",
)

TEXT_HINTS = (
    b"activate", b"activation", b"register", b"registration", b"license", b"licence",
    b"unlock", b"payment", b"billing", b"purchase", b"subscribe", b"subscription",
    b"premium", b"charge", b"send sms", b"sms://", b"messageconnection",
)

UTF8_HINTS = (
    "激活", "注册", "购买", "付费", "收费", "短信", "订购", "支付", "解锁", "授权",
)


@dataclass
class ActivationFlowFinding:
    severity: str
    source: str
    category: str
    message: str


@dataclass
class ActivationFlowReport:
    risk: str = "low"
    score: int = 0
    likely_activation_gate: bool = False
    likely_payment_flow: bool = False
    wma_linked: bool = False
    startup_activation_reachable: bool = False
    startup_payment_reachable: bool = False
    suspicious_classes: List[str] = field(default_factory=list)
    suspicious_resources: List[str] = field(default_factory=list)
    matched_terms: Dict[str, List[str]] = field(default_factory=dict)
    dependency: ClassDependencyReport = field(default_factory=ClassDependencyReport)
    findings: List[ActivationFlowFinding] = field(default_factory=list)


class ActivationFlowAnalyzer:
    """Static, read-only detector for legacy activation/payment flow indicators."""

    def analyze(self, jar_path: str) -> ActivationFlowReport:
        report = ActivationFlowReport()
        class_hits: Set[str] = set()
        resource_hits: Set[str] = set()
        terms: Dict[str, Set[str]] = {}
        wma_sources: Set[str] = set()

        with zipfile.ZipFile(jar_path, "r") as z:
            for info in z.infolist():
                if info.is_dir() or info.file_size > 8 * 1024 * 1024:
                    continue
                name = info.filename
                low_name = name.lower()
                is_class = low_name.endswith(".class")

                name_matches = [hint for hint in NAME_HINTS if hint in low_name]
                if name_matches:
                    (class_hits if is_class else resource_hits).add(name)
                    terms.setdefault(name, set()).update(name_matches)

                if not (is_class or low_name.endswith((
                    ".txt", ".properties", ".xml", ".ini", ".cfg", ".json", ".csv",
                    ".lang", ".lng", ".dat", ".bin", ".res"
                ))):
                    continue
                try:
                    data = z.read(info)
                except Exception:
                    continue
                low = data.lower()

                matched = []
                for token in TEXT_HINTS:
                    if token in low:
                        matched.append(token.decode("ascii", errors="ignore"))
                text = data.decode("utf-8", errors="ignore")
                for token in UTF8_HINTS:
                    if token in text:
                        matched.append(token)

                if b"javax/wireless/messaging/" in low or b"messageconnection" in low or b"sms://" in low:
                    wma_sources.add(name)

                if matched:
                    (class_hits if is_class else resource_hits).add(name)
                    terms.setdefault(name, set()).update(matched)

        report.suspicious_classes = sorted(class_hits)
        report.suspicious_resources = sorted(resource_hits)
        report.matched_terms = {k: sorted(v) for k, v in sorted(terms.items())}
        report.wma_linked = bool(wma_sources.intersection(class_hits) or wma_sources.intersection(resource_hits))

        try:
            report.dependency = ClassDependencyInspector().analyze(jar_path, report.suspicious_classes)
            report.startup_activation_reachable = report.dependency.startup_activation_reachable
            report.startup_payment_reachable = report.dependency.startup_payment_reachable
        except Exception as exc:
            report.findings.append(ActivationFlowFinding(
                "medium", "JAR", "dependency",
                f"Class dependency inspection could not complete: {exc}"
            ))

        score = 0
        if report.suspicious_classes:
            score += min(45, 12 + 8 * len(report.suspicious_classes))
        if report.suspicious_resources:
            score += min(20, 5 * len(report.suspicious_resources))
        if report.wma_linked:
            score += 30

        all_terms = {term.lower() for values in report.matched_terms.values() for term in values}
        activation_terms = {"activate", "activation", "register", "registration", "license", "licence", "unlock", "激活", "注册", "解锁", "授权"}
        payment_terms = {"payment", "billing", "purchase", "pay", "subscribe", "subscription", "premium", "charge", "购买", "付费", "收费", "订购", "支付"}
        has_activation = bool(all_terms.intersection(activation_terms))
        has_payment = bool(all_terms.intersection(payment_terms))

        report.likely_activation_gate = bool(has_activation and report.suspicious_classes) or bool(report.wma_linked and has_activation)
        report.likely_payment_flow = bool(has_payment and report.suspicious_classes) or bool(report.wma_linked and has_payment)
        if report.likely_activation_gate:
            score += 15
        if report.likely_payment_flow:
            score += 15
        if report.startup_activation_reachable:
            score += 20
        if report.startup_payment_reachable:
            score += 10
        report.score = min(100, score)
        report.risk = "high" if report.score >= 60 else ("medium" if report.score >= 30 else "low")

        if report.suspicious_classes:
            report.findings.append(ActivationFlowFinding(
                report.risk, ", ".join(report.suspicious_classes[:5]), "activation",
                "Class names/constants contain activation, registration, licensing, payment, or SMS-flow indicators."
            ))
        if report.wma_linked:
            report.findings.append(ActivationFlowFinding(
                "high", ", ".join(sorted(wma_sources)[:5]), "wma_link",
                "Activation/payment indicators overlap with legacy WMA/SMS usage. This may be more than a missing API and can require runtime-flow analysis."
            ))
        if report.startup_activation_reachable:
            reachable = [p for p in report.dependency.activation_paths if p.startup_reachable]
            sample = " → ".join(reachable[0].path) if reachable else "MIDlet → activation/payment class"
            report.findings.append(ActivationFlowFinding(
                "high", "MANIFEST.MF / class graph", "startup_path",
                "Activation/payment class is statically reachable from a MIDlet entry class: " + sample
            ))
        elif report.suspicious_classes and report.dependency.roots:
            report.findings.append(ActivationFlowFinding(
                "medium", "class graph", "startup_path",
                "Suspicious activation/payment classes exist, but no static reference path from the MIDlet entry class was found. The flow may be optional or dynamically dispatched."
            ))
        if report.likely_activation_gate:
            report.findings.append(ActivationFlowFinding(
                "high", "JAR", "activation_gate",
                "Likely activation/registration gate detected. The tool should report it but must not assume that blocking SMS equals successful activation."
            ))
        if report.likely_payment_flow:
            report.findings.append(ActivationFlowFinding(
                "high", "JAR", "payment_flow",
                "Likely legacy payment/subscription flow detected. Keep analysis read-only and do not emulate a successful purchase."
            ))
        if not report.findings:
            report.findings.append(ActivationFlowFinding(
                "low", "JAR", "activation",
                "No strong activation/payment-flow indicators were detected by the static heuristic scan."
            ))
        return report
