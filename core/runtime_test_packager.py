
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import hashlib, json, shutil, zipfile
from datetime import datetime

@dataclass
class RuntimePackageResult:
    folder: str
    zip_path: str
    summary_path: str
    source_copy: str
    output_copy: str
    build_report_copy: str = ""
    regression_report_copy: str = ""

class RuntimeTestPackager:
    def _sha256(self, path: Path) -> str:
        h=hashlib.sha256()
        with open(path,"rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""):
                h.update(chunk)
        return h.hexdigest()

    def create(
        self,
        source_jar: str,
        output_jar: str,
        destination_dir: str,
        build_report: Optional[str]=None,
        regression_report: Optional[str]=None,
        notes: str=""
    ) -> RuntimePackageResult:
        src=Path(source_jar)
        out=Path(output_jar)
        dest=Path(destination_dir)

        if not src.exists():
            raise FileNotFoundError(f"Source JAR not found: {src}")
        if not out.exists():
            raise FileNotFoundError(f"Output JAR not found: {out}")

        stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        folder=dest/f"{out.stem}_runtime_test_{stamp}"
        folder.mkdir(parents=True,exist_ok=False)

        source_copy=folder/f"00_SOURCE_{src.name}"
        output_copy=folder/f"01_TRANSLATED_{out.name}"
        shutil.copy2(src,source_copy)
        shutil.copy2(out,output_copy)

        build_copy=""
        if build_report and Path(build_report).exists():
            p=Path(build_report)
            target=folder/f"02_BUILD_REPORT{p.suffix}"
            shutil.copy2(p,target)
            build_copy=str(target)

        regression_copy=""
        if regression_report and Path(regression_report).exists():
            p=Path(regression_report)
            target=folder/f"03_REGRESSION_REPORT{p.suffix}"
            shutil.copy2(p,target)
            regression_copy=str(target)

        summary=folder/"RUNTIME_TEST_SUMMARY.txt"
        summary.write_text(
            "\n".join([
                "JAR Vietnamese Translator - Runtime Test Package",
                "================================================",
                f"Created: {datetime.now().isoformat(timespec='seconds')}",
                "",
                f"Source JAR: {source_copy.name}",
                f"Source SHA256: {self._sha256(source_copy)}",
                "",
                f"Translated JAR: {output_copy.name}",
                f"Translated SHA256: {self._sha256(output_copy)}",
                "",
                "Recommended test order:",
                "1. Run SOURCE JAR first and confirm the game boots normally.",
                "2. Run TRANSLATED JAR with the same emulator/device settings.",
                "3. Check menu text, accented Vietnamese glyphs, line wrapping and crashes.",
                "4. If a crash occurs, keep emulator logs together with this package.",
                "5. Compare against BUILD_REPORT and REGRESSION_REPORT.",
                "",
                "Suggested environments:",
                "- FreeJ2ME on Windows",
                "- FreeJ2ME / compatible J2ME runtime on RG35XX",
                "",
                "Notes:",
                notes or "(none)"
            ]),
            encoding="utf-8"
        )

        manifest=folder/"PACKAGE_MANIFEST.json"
        payload={
            "format":"jar-translator-runtime-test-package",
            "version":"4.6",
            "source":{
                "file":source_copy.name,
                "sha256":self._sha256(source_copy),
                "size":source_copy.stat().st_size,
            },
            "translated":{
                "file":output_copy.name,
                "sha256":self._sha256(output_copy),
                "size":output_copy.stat().st_size,
            },
            "build_report":Path(build_copy).name if build_copy else "",
            "regression_report":Path(regression_copy).name if regression_copy else "",
            "summary":summary.name,
        }
        manifest.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

        zip_path=folder.with_suffix(".zip")
        with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
            for f in folder.rglob("*"):
                if f.is_file():
                    z.write(f,f.relative_to(folder))

        return RuntimePackageResult(
            str(folder),str(zip_path),str(summary),
            str(source_copy),str(output_copy),build_copy,regression_copy
        )
