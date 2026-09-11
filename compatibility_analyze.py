
import sys
from core.jar_scanner import JarScanner
from core.compatibility_analyzer import CompatibilityAnalyzer

def main():
    if len(sys.argv)<2:
        print("Usage: python compatibility_analyze.py game.jar")
        return 2
    result=JarScanner().scan(sys.argv[1])
    report=CompatibilityAnalyzer().analyze(sys.argv[1],result,None)
    print("Encoding risk:",report.encoding_risk)
    print("Font risk:",report.font_risk)
    print("Overall:",report.overall_risk)
    for f in report.findings:
        print(f"[{f.severity}] {f.category} {f.source}: {f.message}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
