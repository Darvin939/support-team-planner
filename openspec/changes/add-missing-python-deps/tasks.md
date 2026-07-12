## 1. Dependencies

- [x] 1.1 Added `itsdangerous` to `requirements.txt`.
- [x] 1.2 Added `python-multipart` to `requirements.txt`.

## 2. Documentation

- [x] 2.1 Removed the "Важно" callout in README.md's "Быстрый старт" section about manually installing
      `itsdangerous`/`python-multipart` (no longer needed).
- [x] 2.2 Removed the matching "Known gaps, both undeclared" paragraph in CLAUDE.md, rewording the surrounding
      `requirements.txt` description to list all 9 dependencies (including the two just added) as the current,
      accurate state rather than documenting a historical gap.

## 3. Verification

- [x] 3.1 Uninstalled both packages from the project's real `.venv` (`pip uninstall -y itsdangerous
      python-multipart`), then ran `pip install -r requirements.txt` — both reinstalled correctly from the
      updated file.
- [x] 3.2 **Confirmed the original gap was real, and worse than documented**: with both packages uninstalled,
      starting the app failed immediately at import time (`ModuleNotFoundError: No module named 'itsdangerous'`,
      raised from `starlette.middleware.sessions`'s own top-level `import itsdangerous`) — a full startup crash,
      not just an `AssertionError` on first login as originally described. After reinstalling via
      `requirements.txt`, the app started cleanly and `POST /login` with valid credentials returned
      `200 {"success": true}`.
