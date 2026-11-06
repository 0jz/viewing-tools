# Viewing Tools

Fast, offline Windows document viewers built on one shared PySide6 (Qt 6) core. Files never leave your computer.

| App | Opens | Notes |
|---|---|---|
| PPTX Viewer | `.pptx` | native QPainter renderer, thumbnails, notes, find, present mode, PNG/PDF export |
| CSV Viewer | `.csv` | async loading, encoding/delimiter detection, sort/filter, light editing, tabs |
| *planned* | `.docx`, `.tif/.tiff`, more | see [docs/ADDING_A_FORMAT.md](docs/ADDING_A_FORMAT.md) |

## Layout
```
core/viewing_core/   shared: theme, recent files, drag-drop, worker thread, resource lookup
apps/<format>/       one viewer: parser/model + renderer/view + ui + main
tools/build.ps1      builds any app into a one-folder exe
samples/             test files
```

## Develop
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m apps.pptx.main samples/pptx/sample.pptx
python -m apps.csv.main samples/csv/semicolon.csv
pytest
```

## Build an exe
```powershell
.\tools\build.ps1 -App pptx   # -> app\PPTX Viewer\PPTX Viewer.exe
.\tools\build.ps1 -App csv    # -> app\CSV Viewer\CSV Viewer.exe
```

## License
MIT
