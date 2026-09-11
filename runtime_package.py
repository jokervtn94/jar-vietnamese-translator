
import sys
from core.runtime_test_packager import RuntimeTestPackager

def main():
    if len(sys.argv)<4:
        print("Usage: python runtime_package.py source.jar translated.jar destination_dir [build-report.json] [regression-report.json]")
        return 2
    r=RuntimeTestPackager().create(
        sys.argv[1],sys.argv[2],sys.argv[3],
        sys.argv[4] if len(sys.argv)>4 else None,
        sys.argv[5] if len(sys.argv)>5 else None
    )
    print("Folder:",r.folder)
    print("ZIP:",r.zip_path)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
