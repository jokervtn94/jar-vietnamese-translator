
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import hashlib
import json
import re

FORMAT_V1 = "jar-translator-exchange-v1"
FORMAT_V2 = "jar-translator-exchange-v2"
SCHEMA_VERSION = 2

PLACEHOLDER_PATTERNS = [
    r'%(?:\d+\$)?[-+#0-9.*]*[sdifuxXcfeEgGaApn%]',
    r'\{(?:\d+|[A-Za-z_]\w*)\}',
    r'\\[nrt]',
    r'<[^>\n]{1,40}>',
]

IMMUTABLE_ITEM_FIELDS = [
    "id","key","source","kind","index","original","original_sha256","placeholders"
]

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def sha256_file(path: str) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def extract_placeholders(text: str) -> List[str]:
    found=[]
    for pattern in PLACEHOLDER_PATTERNS:
        found.extend(re.findall(pattern,text))
    return sorted(found)

def placeholders_preserved(original: str, translated: str) -> bool:
    return extract_placeholders(original) == extract_placeholders(translated)

@dataclass
class ImportResult:
    imported: int = 0
    skipped_existing: int = 0
    rejected_empty: int = 0
    rejected_unknown: int = 0
    rejected_original_mismatch: int = 0
    rejected_placeholder: int = 0
    rejected_schema: int = 0
    rejected_hash: int = 0
    rejected_duplicate: int = 0
    rejected_source_jar: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def rejected_total(self):
        return (
            self.rejected_empty
            + self.rejected_unknown
            + self.rejected_original_mismatch
            + self.rejected_placeholder
            + self.rejected_schema
            + self.rejected_hash
            + self.rejected_duplicate
            + self.rejected_source_jar
        )

class TranslationExchange:
    def _build_items(self, result, project, include_translated=False):
        items=[]
        seen=set()
        seq=1
        for candidate,string in result.all_strings():
            if string.key in seen:
                continue
            seen.add(string.key)

            existing=project.get(string.key).strip()
            if existing and not include_translated:
                continue

            buildable=(
                string.kind=="class-string"
                or string.kind=="resource-text"
                or (string.kind.startswith("binary:") and string.kind.endswith(":safe"))
            )
            if not buildable:
                continue

            original=string.value
            items.append({
                "id":f"T{seq:05d}",
                "key":string.key,
                "source":string.source,
                "kind":string.kind,
                "index":string.index,
                "original":original,
                "original_sha256":sha256_text(original),
                "placeholders":extract_placeholders(original),
                "translation":existing,
            })
            seq+=1
        return items

    def export_payload(self, result, project, include_translated=False):
        items=self._build_items(result,project,include_translated)
        jar_path=Path(result.jar_path)
        jar_hash=sha256_file(str(jar_path)) if jar_path.exists() else ""

        return {
            "format":FORMAT_V2,
            "schema_version":SCHEMA_VERSION,
            "target_language":"vi-VN",
            "source_jar":{
                "name":jar_path.name,
                "sha256":jar_hash,
            },
            "translation_protocol":{
                "task":"Translate every items[].original into natural Vietnamese and write ONLY the translated text into items[].translation.",
                "mandatory_rules":[
                    "Return valid JSON only. Do not wrap the result in Markdown code fences.",
                    "Keep the entire top-level JSON structure unchanged.",
                    "Do not add, delete, reorder, rename, or merge items.",
                    "Only modify items[].translation.",
                    "Never modify id, key, source, kind, index, original, original_sha256, or placeholders.",
                    "Keep all placeholders exactly unchanged and in equivalent positions where possible, including %s, %d, {0}, {name}, \\n, \\t and <...> tags.",
                    "Preserve escape sequences and produce syntactically valid JSON.",
                    "Use concise, natural Vietnamese suitable for small Java/J2ME mobile-game screens.",
                    "Preserve gameplay meaning, menu intent, proper names, numbers, units and symbols unless they are naturally localized.",
                    "Do not translate technical identifiers, filenames, class names, paths, URLs, commands or format tokens if they appear as content.",
                    "If uncertain whether a string should be translated, copy original into translation instead of inventing text.",
                    "Do not leave translation empty unless original is empty.",
                    "Do not add explanations, comments, notes, prefixes, suffixes, quotation commentary or alternative translations.",
                    "The returned JSON must contain the same number of items as the input.",
                ],
                "immutable_fields":IMMUTABLE_ITEM_FIELDS,
                "editable_fields":["translation"],
                "output_contract":{
                    "required_top_level_fields":[
                        "format","schema_version","target_language","source_jar",
                        "translation_protocol","items"
                    ],
                    "required_item_fields":[
                        "id","key","source","kind","index","original",
                        "original_sha256","placeholders","translation"
                    ],
                    "item_count":len(items),
                    "item_order":"must remain exactly the same",
                    "translation_type":"string",
                    "json_only":True,
                    "markdown_fence_forbidden":True,
                },
                "model_prompt":"Follow translation_protocol.mandatory_rules exactly. Translate only items[].translation. Return this same JSON document and nothing else.",
                "valid_output_example":{
                    "id":"T00001",
                    "key":"DO_NOT_CHANGE",
                    "source":"res/lang.properties",
                    "kind":"resource-text",
                    "index":0,
                    "original":"Score: %d",
                    "original_sha256":"DO_NOT_CHANGE",
                    "placeholders":["%d"],
                    "translation":"Điểm: %d"
                },
            },
            "items":items,
        }

    def export_file(self, result, project, path: str, include_translated=False):
        payload=self.export_payload(result,project,include_translated)
        Path(path).write_text(
            json.dumps(payload,ensure_ascii=False,indent=2),
            encoding="utf-8"
        )
        return len(payload["items"])

    def _current_maps(self, result):
        by_key={}
        by_original={}
        for _,s in result.all_strings():
            by_key[s.key]=s
            by_original.setdefault(s.value,[]).append(s)
        return by_key,by_original

    def _validate_v2_header(self,payload,result,report):
        if payload.get("schema_version") != SCHEMA_VERSION:
            report.rejected_schema+=1
            report.warnings.append(
                f"Unsupported schema_version: {payload.get('schema_version')!r}"
            )
            return False

        source=payload.get("source_jar")
        if not isinstance(source,dict):
            report.rejected_schema+=1
            report.warnings.append("Missing/invalid source_jar block.")
            return False

        expected_name=Path(result.jar_path).name
        supplied_name=source.get("name","")
        if supplied_name and supplied_name != expected_name:
            report.rejected_source_jar+=1
            report.warnings.append(
                f"JSON belongs to another JAR: {supplied_name!r} != {expected_name!r}"
            )
            return False

        supplied_hash=source.get("sha256","")
        jar_path=Path(result.jar_path)
        if supplied_hash and jar_path.exists():
            current_hash=sha256_file(str(jar_path))
            if supplied_hash != current_hash:
                report.rejected_source_jar+=1
                report.warnings.append("source_jar SHA-256 does not match the currently opened JAR.")
                return False

        protocol=payload.get("translation_protocol")
        if not isinstance(protocol,dict):
            report.rejected_schema+=1
            report.warnings.append("Missing translation_protocol block.")
            return False

        contract=protocol.get("output_contract")
        if not isinstance(contract,dict):
            report.rejected_schema+=1
            report.warnings.append("Missing output_contract block.")
            return False

        items=payload.get("items")
        if not isinstance(items,list):
            report.rejected_schema+=1
            report.warnings.append("items must be a list.")
            return False

        expected_count=contract.get("item_count")
        if isinstance(expected_count,int) and expected_count != len(items):
            report.rejected_schema+=1
            report.warnings.append(
                f"Item count changed: expected {expected_count}, got {len(items)}."
            )
            return False
        return True

    def import_payload(self, payload, result, project, overwrite=False) -> ImportResult:
        report=ImportResult()
        by_key,by_original=self._current_maps(result)

        if isinstance(payload,dict) and payload.get("format")==FORMAT_V2:
            if not self._validate_v2_header(payload,result,report):
                return report

            seen_ids=set()
            seen_keys=set()
            for row in payload["items"]:
                if not isinstance(row,dict):
                    report.rejected_schema+=1
                    continue

                missing=[k for k in (
                    "id","key","source","kind","index","original",
                    "original_sha256","placeholders","translation"
                ) if k not in row]
                if missing:
                    report.rejected_schema+=1
                    report.warnings.append(f"Missing required fields: {missing}")
                    continue

                row_id=str(row.get("id",""))
                key=str(row.get("key",""))
                if row_id in seen_ids or key in seen_keys:
                    report.rejected_duplicate+=1
                    report.warnings.append(f"Duplicate id/key detected: {row_id!r}")
                    continue
                seen_ids.add(row_id)
                seen_keys.add(key)

                target=by_key.get(key)
                if target is None:
                    report.rejected_unknown+=1
                    continue

                original=row.get("original")
                if original != target.value:
                    report.rejected_original_mismatch+=1
                    continue

                supplied_hash=row.get("original_sha256","")
                if supplied_hash != sha256_text(target.value):
                    report.rejected_hash+=1
                    report.warnings.append(f"original_sha256 mismatch for {row_id}.")
                    continue

                supplied_placeholders=row.get("placeholders")
                if supplied_placeholders != extract_placeholders(target.value):
                    report.rejected_schema+=1
                    report.warnings.append(f"Placeholder manifest changed for {row_id}.")
                    continue

                # Immutable metadata must still match the scan result.
                if row.get("source") != target.source or row.get("kind") != target.kind or row.get("index") != target.index:
                    report.rejected_schema+=1
                    report.warnings.append(f"Immutable metadata changed for {row_id}.")
                    continue

                translation=row.get("translation")
                if not isinstance(translation,str) or not translation.strip():
                    report.rejected_empty+=1
                    continue

                if project.get(target.key).strip() and not overwrite:
                    report.skipped_existing+=1
                    continue

                translated=translation.strip()
                if not placeholders_preserved(target.value,translated):
                    report.rejected_placeholder+=1
                    report.warnings.append(
                        f"Placeholder mismatch: {target.value!r} -> {translated!r}"
                    )
                    continue

                project.set(target.key,translated)
                report.imported+=1
            return report

        # V1 backward compatibility.
        if isinstance(payload,dict) and isinstance(payload.get("items"),list):
            for row in payload["items"]:
                if not isinstance(row,dict):
                    report.rejected_unknown+=1
                    continue
                key=(row.get("key") or "").strip()
                original=row.get("original","")
                translation=row.get("translation","")
                if not isinstance(translation,str) or not translation.strip():
                    report.rejected_empty+=1
                    continue
                target=by_key.get(key)
                if target is None:
                    matches=by_original.get(original,[])
                    target=matches[0] if len(matches)==1 else None
                if target is None:
                    report.rejected_unknown+=1
                    continue
                if original != target.value:
                    report.rejected_original_mismatch+=1
                    continue
                if project.get(target.key).strip() and not overwrite:
                    report.skipped_existing+=1
                    continue
                translated=translation.strip()
                if not placeholders_preserved(target.value,translated):
                    report.rejected_placeholder+=1
                    continue
                project.set(target.key,translated)
                report.imported+=1
            return report

        # Convenience object {"Original":"Translation"}.
        if isinstance(payload,dict):
            for original,translation in payload.items():
                if not isinstance(original,str) or not isinstance(translation,str):
                    report.rejected_unknown+=1
                    continue
                if not translation.strip():
                    report.rejected_empty+=1
                    continue
                matches=by_original.get(original,[])
                if not matches:
                    report.rejected_unknown+=1
                    continue
                for target in matches:
                    if project.get(target.key).strip() and not overwrite:
                        report.skipped_existing+=1
                        continue
                    translated=translation.strip()
                    if not placeholders_preserved(target.value,translated):
                        report.rejected_placeholder+=1
                        continue
                    project.set(target.key,translated)
                    report.imported+=1
            return report

        if isinstance(payload,list):
            return self.import_payload({"items":payload},result,project,overwrite)

        raise ValueError("Unsupported translation JSON structure.")

    def import_file(self, path: str, result, project, overwrite=False) -> ImportResult:
        payload=json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return self.import_payload(payload,result,project,overwrite)
