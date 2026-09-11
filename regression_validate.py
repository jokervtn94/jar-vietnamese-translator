
import sys
from core.jar_scanner import JarScanner
from core.translation_project import TranslationProject
from core.regression_validator import RegressionValidator

def main():
    if len(sys.argv)<4:
        print("Usage: python regression_validate.py source.jar project.jtv2.json output.jar")
        return 2
    result=JarScanner().scan(sys.argv[1])
    project=TranslationProject.load(sys.argv[2])
    project.jar_path=sys.argv[1]
    rr=RegressionValidator().validate(result,project,sys.argv[3])
    print("Archive:", "PASS" if rr.archive_ok else "FAIL")
    print("Rescan:", "PASS" if rr.rescan_ok else "FAIL")
    print("Regression:", "PASS" if rr.validation_ok else "FAIL")
    print("Passed:", rr.passed, "Failed:", rr.failed, "Skipped:", rr.skipped)
    for i in rr.items:
        print(f"[{i.status}] {i.source}: {i.original} -> {i.translated} | {i.detail}")
    return 0 if rr.validation_ok else 1

if __name__=="__main__":
    raise SystemExit(main())
