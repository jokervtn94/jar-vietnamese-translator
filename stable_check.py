
import sys
from core.jar_scanner import JarScanner
from core.translation_project import TranslationProject
from core.stable_pipeline import StablePipeline

def main():
    if len(sys.argv) < 3:
        print("Usage: python stable_check.py game.jar project.jtv2.json")
        return 2

    result = JarScanner().scan(sys.argv[1])
    project = TranslationProject.load(sys.argv[2])
    project.jar_path = sys.argv[1]

    r = StablePipeline().readiness(result, project)
    print("V4.7 BUILD READINESS:", r.status)
    print(f"Translations: {r.translated_strings}/{r.total_strings}")
    print(f"Binary safe/locked: {r.binary_safe}/{r.binary_unsafe}")
    print("Compatibility:", r.compatibility_risk)
    print("Glyph:", r.glyph_risk)
    for i in r.issues:
        print(f"[{i.level}] {i.category}: {i.message}")
    return 1 if r.status == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
