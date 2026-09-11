
import sys
from core.jar_scanner import JarScanner
from core.translation_project import TranslationProject
from core.build_readiness import BuildReadinessAnalyzer

def main():
    if len(sys.argv)<2:
        print("Usage: python build_readiness.py game.jar [project.jtv2.json]")
        return 2
    result=JarScanner().scan(sys.argv[1])
    if len(sys.argv)>=3:
        project=TranslationProject.load(sys.argv[2])
        project.jar_path=sys.argv[1]
    else:
        project=TranslationProject(jar_path=sys.argv[1])
    r=BuildReadinessAnalyzer().analyze(result,project)
    print("STATUS:",r.status)
    print(f"Translated: {r.translated_strings}/{r.total_strings}")
    for i in r.issues:
        print(f"[{i.level}] {i.category}: {i.message}")
    return 0 if r.status!="BLOCKED" else 1

if __name__=="__main__":
    raise SystemExit(main())
