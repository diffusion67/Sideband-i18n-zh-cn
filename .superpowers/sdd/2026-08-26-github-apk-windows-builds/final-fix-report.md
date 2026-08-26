# Final-review fix report

## Finding addressed

`sbapp/main.py` imported `localize_kv` only with `from .i18n import localize_kv`. Android executes `sbapp/main.py` as source-root `__main__`, where that relative import has no package context and fails before the UI can start.

## Test-driven evidence

Added `tests/test_main_imports.py`, a standard-library `unittest` that parses `sbapp/main.py` with `ast` and verifies the Android platform branch uses the absolute `from i18n import localize_kv` import while its `else` branch retains `from .i18n import localize_kv`.

The test was run before the production change:

```text
python -m unittest tests.test_main_imports
F
AssertionError: 0 != 1
Ran 1 test in 0.086s
FAILED (failures=1)
```

The failure was the expected missing platform-conditional import branch.

## Implementation

At the existing Kivy import site in `sbapp/main.py`, the import is now selected with `RNS.vendor.platformutils.is_android()`:

```python
if RNS.vendor.platformutils.is_android():
    from i18n import localize_kv
else:
    from .i18n import localize_kv
```

This is the minimal change required for Android source-root execution and preserves package-relative imports on desktop platforms.

## Verification

All requested checks passed after the change:

```text
python -m unittest tests.test_main_imports
.
Ran 1 test in 0.119s
OK

python -m unittest discover -s tests -p 'test_*.py'
.......
Ran 7 tests in 0.088s
OK

python -m py_compile sbapp/main.py
exit_code=0
```

`git diff --check` reported no whitespace errors.
