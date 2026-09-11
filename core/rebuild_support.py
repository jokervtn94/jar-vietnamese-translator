import os
import shutil
from pathlib import Path
from uuid import uuid4


def install_same_name_build_support():
    """Allow JarBuilder to safely rebuild to the same JAR path.

    The GUI already lets users choose any output name. JarBuilder itself normally
    refuses output == source to protect the original archive. This wrapper keeps
    that protection by creating a persistent .original.jar backup and building
    through a temporary JAR. Repeated same-name builds continue to use the
    untouched backup as their source baseline.
    """
    from core.jar_builder import JarBuilder

    if getattr(JarBuilder, "_same_name_support_installed", False):
        return

    original_build = JarBuilder.build

    def _backup_path(source: Path) -> Path:
        return source.with_name(source.stem + ".original.jar")

    def build(self, result, project, output_path: str):
        visible_source = Path(result.jar_path)
        requested_output = Path(output_path)

        # If this session has already replaced the visible source once, always
        # keep building from the preserved original baseline.
        baseline_value = getattr(result, "_jar_translator_original_source", "")
        baseline = Path(baseline_value) if baseline_value else visible_source

        same_visible_path = False
        try:
            same_visible_path = requested_output.resolve() == visible_source.resolve()
        except Exception:
            same_visible_path = os.path.abspath(str(requested_output)) == os.path.abspath(str(visible_source))

        # Normal Build As... path. If an original baseline exists from a prior
        # same-name rebuild, use it so subsequent builds remain reproducible.
        if not same_visible_path:
            if baseline != visible_source and baseline.exists():
                old_path = result.jar_path
                try:
                    result.jar_path = str(baseline)
                    report = original_build(self, result, project, str(requested_output))
                    report.source_jar = str(visible_source)
                    return report
                finally:
                    result.jar_path = old_path
            return original_build(self, result, project, str(requested_output))

        # Same-name rebuild: preserve the original JAR once, then build to a
        # temporary sibling and atomically replace the requested JAR only after
        # archive/regression validation succeeds.
        backup = baseline if baseline != visible_source and baseline.exists() else _backup_path(visible_source)
        if not backup.exists():
            shutil.copy2(visible_source, backup)
        result._jar_translator_original_source = str(backup)

        temp_output = visible_source.with_name(
            f".{visible_source.stem}.jartranslator-{uuid4().hex}.tmp.jar"
        )
        old_path = result.jar_path
        try:
            result.jar_path = str(backup)
            report = original_build(self, result, project, str(temp_output))

            if not report.validation_ok:
                raise ValueError(
                    "Same-name rebuild was not installed because validation failed. "
                    f"The original JAR is still preserved at: {backup}"
                )

            os.replace(temp_output, visible_source)
            report.source_jar = str(visible_source)
            report.output_jar = str(visible_source)
            report.warnings.append(
                f"Same-name rebuild completed. Original backup preserved at: {backup}"
            )
            return report
        finally:
            result.jar_path = old_path
            try:
                if temp_output.exists():
                    temp_output.unlink()
            except Exception:
                pass

    JarBuilder.build = build
    JarBuilder._same_name_support_installed = True
