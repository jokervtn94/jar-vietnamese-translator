import csv, json

class Exporter:
    @staticmethod
    def to_json(result, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def to_csv(result, path: str, translations=None):
        translations = translations or {}
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["key", "source", "source_type", "score", "kind", "index", "encoding", "original", "vietnamese"])
            for c in result.candidates:
                for s in c.strings:
                    w.writerow([s.key, c.source, c.source_type, c.score, s.kind, s.index, s.encoding, s.value, translations.get(s.key, "")])
