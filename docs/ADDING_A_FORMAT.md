# Adding a format (docx, tiff, ...)

Every viewer has the same three layers so apps stay interchangeable:

1. **Parser / model** (`parser.py` or `loader.py` + `model.py`): file path -> plain data. No widgets, no window state; unit-testable.
2. **Renderer / view** (`render.py` or a Qt model/view): data -> pixels or a Qt view.
3. **UI** (`ui.py`): a `QMainWindow` subclass that mixes in `viewing_core.DropOpenMixin`, sets `drop_suffixes`, and implements `open_file(path)`.

## Steps
1. `apps/<fmt>/` with `__init__.py`, `main.py`, `ui.py`, parser, tests, `resources/app.ico` + `generate_icon.py`.
2. `main.py`: create `QApplication`, call `viewing_core.apply_theme(app, mode)`, show the window, open the first CLI argument.
3. Keep recents with `viewing_core.RecentFiles(QSettings("<Name>", "<Name>"))`.
4. Load slow files off the UI thread with `viewing_core.run_in_thread(fn, on_done, on_error)`.
5. Add the package to `pyproject.toml` (`packages`) and the app name to `tools/build.ps1` (`ValidateSet` and `$names`).
6. Add `samples/<fmt>/` and tests under `apps/<fmt>/tests/`.

## Planned
- **docx**: `zipfile` + XML -> block/run model -> `QTextDocument` (view first, edit later).
- **tiff**: Qt image reader / Pillow -> multi-page `QImage` list -> zoomable page canvas with a thumbnail sidebar (reuse the pptx sidebar).
