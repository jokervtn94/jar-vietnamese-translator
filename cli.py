import argparse
from core.jar_scanner import JarScanner
from exporters.exporter import Exporter

p = argparse.ArgumentParser(description="JAR Vietnamese Translator scanner")
p.add_argument("jar")
p.add_argument("--csv")
p.add_argument("--json")
a = p.parse_args()
r = JarScanner().scan(a.jar)
print(f"Entries: {len(r.entries)} | Candidates: {len(r.candidates)}")
for c in r.candidates[:20]:
    print(f"[{c.score:3d}%] {len(c.strings):4d} strings  {c.source}")
if a.csv: Exporter.to_csv(r, a.csv)
if a.json: Exporter.to_json(r, a.json)
