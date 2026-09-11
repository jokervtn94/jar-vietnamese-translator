
import sys
from core.jar_scanner import JarScanner
from core.glyph_analyzer import GlyphAnalyzer

def main():
    if len(sys.argv)<2:
        print("Usage: python glyph_analyze.py game.jar")
        return 2
    result=JarScanner().scan(sys.argv[1])
    r=GlyphAnalyzer().analyze(sys.argv[1],result,None)
    print("Risk:",r.risk)
    print("Confidence:",r.confidence)
    print("Maps:",len(r.maps))
    print("Missing:", " ".join(sorted(r.missing_chars,key=lambda c:ord(c))))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
