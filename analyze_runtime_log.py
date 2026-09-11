
import sys
from core.runtime_log_analyzer import RuntimeLogAnalyzer

def main():
    if len(sys.argv)<2:
        print("Usage: python analyze_runtime_log.py runtime.log [build-report.json]")
        return 2
    r=RuntimeLogAnalyzer().analyze(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else None)
    print("STATUS:",r.status)
    print("Summary:",r.summary)
    print("High:",r.high_count,"Medium:",r.medium_count)
    for i in r.issues:
        rel=", ".join(i.related_patch_sources) if i.related_patch_sources else "-"
        print(f"[{i.severity}] line {i.line_no} {i.category} {i.exception} patch={rel}")
        print(" ",i.text)
    return 1 if r.status=="FAIL" else 0

if __name__=="__main__":
    raise SystemExit(main())
