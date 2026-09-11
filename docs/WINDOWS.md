# Windows usage

## Run from source

Double-click:

```text
RUN_JAR_TRANSLATOR.bat
```

The launcher creates/uses a local Python environment and starts the application.

## Silent launcher

```text
RUN_SILENT.vbs
```

Use this when you want to launch without keeping a console window open.

## Portable build

Double-click:

```text
BUILD_PORTABLE_EXE.bat
```

PyInstaller creates a portable distribution under `dist/`.

`RUN_PORTABLE.bat` can be used with the generated portable folder.
