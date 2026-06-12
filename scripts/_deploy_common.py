"""Shared helpers for VPS deploy scripts (git-first policy)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent


def repo_root() -> Path:
    return _REPO


def enforce_git_first() -> str:
    """Run git deploy gate; exit 1 if not clean and pushed."""
    gate_path = _SCRIPTS / "git_deploy_gate.py"
    spec = importlib.util.spec_from_file_location("git_deploy_gate", gate_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Missing {gate_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["git_deploy_gate"] = mod
    spec.loader.exec_module(mod)
    return mod.require_git_pushed()
