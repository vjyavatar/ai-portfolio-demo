#!/usr/bin/env python3
"""
install_routers.py — Auto-patches api.py to register smart_money_router + earnings_router.

USAGE:
    cd /path/to/your/celesys/repo    # the folder containing api.py
    python install_routers.py

WHAT IT DOES:
    1. Verifies api.py exists in current folder
    2. Verifies smart_money_router.py + earnings_router.py exist (next to api.py)
    3. Creates a backup at api.py.backup
    4. Adds the import lines after the existing imports in api.py
    5. Adds app.include_router() calls right after `app = FastAPI(...)`
    6. Verifies the patched file parses as valid Python
    7. Reports what was changed

After it succeeds, you only need to run:
    git add api.py smart_money_router.py earnings_router.py
    git commit -m "register smart-money + earnings routers"
    git push origin main

Running this script twice is safe — it detects already-installed routers and skips.
"""

import os
import sys
import re
import ast
import shutil
from pathlib import Path


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
END = "\033[0m"


def log(emoji, msg, color=""):
    print(f"{color}{emoji} {msg}{END}")


def main() -> int:
    cwd = Path.cwd()
    log("📂", f"Working directory: {cwd}")

    # ─── 1. Verify required files exist ──────────────────────────────
    api_py = cwd / "api.py"
    smart = cwd / "smart_money_router.py"
    earnings = cwd / "earnings_router.py"

    missing = []
    if not api_py.exists():
        missing.append("api.py (your main FastAPI file)")
    if not smart.exists():
        missing.append("smart_money_router.py (from the deploy zip)")
    if not earnings.exists():
        missing.append("earnings_router.py (from the deploy zip)")

    if missing:
        log("❌", "Required files are missing in this folder:", RED)
        for m in missing:
            print(f"   - {m}")
        print("\nFix: cd into the folder that contains api.py, then copy")
        print("smart_money_router.py and earnings_router.py from the r63.93.0 zip")
        print("into the same folder. Then run this script again.")
        return 1

    log("✅", "Found api.py + smart_money_router.py + earnings_router.py", GREEN)

    # ─── 2. Read api.py ──────────────────────────────────────────────
    content = api_py.read_text(encoding="utf-8")
    original_lines = content.count("\n")
    log("📄", f"api.py is {len(content):,} bytes / {original_lines:,} lines")

    # ─── 3. Idempotency check ────────────────────────────────────────
    has_smart_import = "from smart_money_router import" in content
    has_earnings_import = "from earnings_router import" in content
    has_smart_include = "include_router(smart_money_router)" in content
    has_earnings_include = "include_router(earnings_router)" in content

    if all([has_smart_import, has_earnings_import, has_smart_include, has_earnings_include]):
        log("✅", "Both routers are already installed in api.py. Nothing to do.", GREEN)
        log("ℹ", "If /api/smart-money-scanner still returns 404 after this, the issue is")
        print("   that your last git push did not include all 3 files. Run:")
        print("   git status     # see what's untracked")
        print("   git add api.py smart_money_router.py earnings_router.py")
        print("   git commit -m 'register routers'")
        print("   git push origin main")
        return 0

    # ─── 4. Find insertion points ────────────────────────────────────
    # Find the existing FastAPI import
    app_creation_match = re.search(r"^(\s*)(app\s*=\s*FastAPI\b[^)]*\))", content, re.MULTILINE)
    if not app_creation_match:
        log("❌", "Could not find `app = FastAPI(...)` in api.py", RED)
        log("ℹ", "Your app instance must be named `app`. If it's named something else,")
        print("   edit this script (search for 'app_creation_match') or manually add:")
        print("       from smart_money_router import router as smart_money_router")
        print("       from earnings_router import router as earnings_router")
        print("       <your_app_var>.include_router(smart_money_router)")
        print("       <your_app_var>.include_router(earnings_router)")
        return 1

    app_indent = app_creation_match.group(1)
    log("✅", f"Found `app = FastAPI(...)` at line {content[:app_creation_match.start()].count(chr(10)) + 1}", GREEN)

    # Find the last existing `from X import Y` line near the top of the file
    # (so we add our imports next to existing ones, not at the very top)
    import_lines = list(re.finditer(r"^(from\s+\S+\s+import|import\s+\S+).*$", content, re.MULTILINE))
    if not import_lines:
        log("❌", "Could not find any `from ... import ...` or `import ...` lines", RED)
        return 1

    last_import_in_first_500_lines = None
    for m in import_lines:
        line_no = content[:m.start()].count("\n") + 1
        if line_no <= 500:  # only consider imports in the top portion
            last_import_in_first_500_lines = m

    if not last_import_in_first_500_lines:
        last_import_in_first_500_lines = import_lines[0]

    # ─── 5. Create backup ────────────────────────────────────────────
    backup = cwd / "api.py.backup"
    shutil.copy2(api_py, backup)
    log("💾", f"Backup created: {backup.name}", GREEN)

    # ─── 6. Build the patch ──────────────────────────────────────────
    new_imports = []
    if not has_smart_import:
        new_imports.append("from smart_money_router import router as smart_money_router")
    if not has_earnings_import:
        new_imports.append("from earnings_router import router as earnings_router")

    new_includes = []
    if not has_smart_include:
        new_includes.append(f"{app_indent}app.include_router(smart_money_router)")
    if not has_earnings_include:
        new_includes.append(f"{app_indent}app.include_router(earnings_router)")

    # Insert imports: right after the last import in the first 500 lines
    import_block = "\n# r63.93.0: smart-money + earnings routers\n" + "\n".join(new_imports)
    import_insert_pos = last_import_in_first_500_lines.end()

    # Insert include_router calls: right after `app = FastAPI(...)` line ends
    # Find the end of the line containing the app creation
    app_line_end = content.find("\n", app_creation_match.end())
    if app_line_end == -1:
        app_line_end = len(content)
    include_block = "\n\n# r63.93.0: register the new routers\n" + "\n".join(new_includes)

    # Apply the patches IN REVERSE ORDER (so positions don't shift)
    if app_line_end > import_insert_pos:
        # Patch includes first (it's later in the file)
        patched = content[:app_line_end] + include_block + content[app_line_end:]
        # Then patch imports
        patched = patched[:import_insert_pos] + import_block + patched[import_insert_pos:]
    else:
        patched = content[:import_insert_pos] + import_block + content[import_insert_pos:]
        # Recompute app_line_end in patched
        m2 = re.search(r"^(\s*)(app\s*=\s*FastAPI\b[^)]*\))", patched, re.MULTILINE)
        app_line_end_new = patched.find("\n", m2.end()) if m2 else -1
        if app_line_end_new != -1:
            patched = patched[:app_line_end_new] + include_block + patched[app_line_end_new:]

    # ─── 7. Verify patched file parses as valid Python ───────────────
    try:
        ast.parse(patched)
    except SyntaxError as e:
        log("❌", f"Patched api.py has a syntax error at line {e.lineno}: {e.msg}", RED)
        log("ℹ", "Restoring backup. No changes applied.", YELLOW)
        return 1

    # ─── 8. Write patched file ───────────────────────────────────────
    api_py.write_text(patched, encoding="utf-8")
    new_lines = patched.count("\n")
    log("✅", f"api.py patched successfully (+{new_lines - original_lines} lines)", GREEN)
    print()
    print(f"{BOLD}Added imports:{END}")
    for line in new_imports:
        print(f"   {line}")
    print(f"\n{BOLD}Added registrations:{END}")
    for line in new_includes:
        print(f"   {line.strip()}")
    print()

    # ─── 9. Tell user what to do next ────────────────────────────────
    log("🚀", "DEPLOY NOW:", BOLD)
    print("   git add api.py smart_money_router.py earnings_router.py")
    print("   git commit -m 'r63.93.0: register smart-money + earnings routers'")
    print("   git push origin main")
    print()
    log("🔍", "Verify after ~90s Render deploy:")
    print("   Open https://celesys.ai/api/smart-money-scanner?region=US&mcap=large")
    print("   Expected: JSON response (first call takes 30-90 seconds — yfinance fetches)")
    print()
    log("↩", "If something goes wrong, restore the backup:")
    print(f"   copy api.py.backup api.py    (Windows)")
    print(f"   cp api.py.backup api.py      (Mac/Linux)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
