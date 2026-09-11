
import sys, zipfile
from core.binary_resource_analyzer import BinaryResourceAnalyzer

def main():
    if len(sys.argv) < 2:
        print("Usage: python binary_analyze.py game.jar")
        return 2
    with zipfile.ZipFile(sys.argv[1], "r") as z:
        for name in z.namelist():
            if name.lower().endswith((".dat",".bin",".res")):
                a=BinaryResourceAnalyzer().analyze(name,z.read(name))
                print(f"{name}: format={a.format_name}, confidence={a.confidence}%, strings={a.total_count}, safe={a.safe_count}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
