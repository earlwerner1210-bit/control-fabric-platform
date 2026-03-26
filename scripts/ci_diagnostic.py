#!/usr/bin/env python3
"""CI diagnostic script — run before tests to verify environment."""

import importlib
import os
import sys
import traceback


def check_import(module_name: str) -> bool:
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, "__version__", "no version attr")
        print(f"  OK  {module_name} ({version})")
        return True
    except Exception as exc:
        print(f"  FAIL {module_name}: {exc}")
        return False


def main():
    print("=" * 60)
    print("CI DIAGNOSTIC")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"Executable: {sys.executable}")
    print(f"CWD: {os.getcwd()}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', '<not set>')}")
    print(f"sys.path:")
    for p in sys.path:
        print(f"  {p}")

    print()
    print("── External packages ──")
    externals = [
        "pydantic",
        "pydantic_settings",
        "fastapi",
        "sqlalchemy",
        "structlog",
        "httpx",
        "pgvector",
        "temporalio",
        "jose",
        "passlib",
        "redis",
        "asyncpg",
        "alembic",
        "prometheus_client",
        "pytest",
        "pytest_asyncio",
        "pytest_cov",
    ]
    failed = []
    for mod in externals:
        if not check_import(mod):
            failed.append(mod)

    print()
    print("── Project packages ──")
    project_mods = [
        "app",
        "app.core.config",
        "app.db.base",
        "app.db.models",
        "app.schemas.common",
        "domain_packs",
        "domain_packs.contract_margin",
        "domain_packs.contract_margin.rules.billability_rules",
        "shared",
    ]
    for mod in project_mods:
        if not check_import(mod):
            failed.append(mod)

    print()
    print("── Pytest collection test ──")
    try:
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/unit/"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PYTHONPATH": os.getcwd()},
        )
        print(f"  Exit code: {result.returncode}")
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            # Print last 10 lines of stdout
            for line in lines[-10:]:
                print(f"  {line}")
        if result.returncode != 0 and result.stderr:
            lines = result.stderr.strip().split("\n")
            for line in lines[-20:]:
                print(f"  STDERR: {line}")
    except Exception as exc:
        print(f"  FAIL: {exc}")
        traceback.print_exc()

    print()
    if failed:
        print(f"FAILED IMPORTS: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
