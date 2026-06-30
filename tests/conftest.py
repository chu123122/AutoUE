from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

@pytest.fixture
def tmp_path(request):
    """Workspace-local replacement for pytest tmp_path.

    The managed sandbox used by Codex can deny access to the OS-level pytest
    temp root.  Keep tests deterministic by allocating per-test scratch space
    inside the writable repository instead.
    """

    root = Path(__file__).resolve().parents[1] / "test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name)[:80]
    path = root / f"{safe_name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path
