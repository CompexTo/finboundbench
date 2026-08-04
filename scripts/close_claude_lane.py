"""Write the reproducible Claude/OpenRouter closure artifact."""

from __future__ import annotations

import json
from pathlib import Path

from purposebench.v2.claude_closure import build_claude_closure_report
from purposebench.v2.pilots import write_new_v2_artifact


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = build_claude_closure_report(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    destination = write_new_v2_artifact(
        root,
        Path("results/v2/derived/openrouter-claude-closure.json"),
        report,
    )
    print(json.dumps({"artifact": destination.relative_to(root).as_posix(), **report["budget"]}))


if __name__ == "__main__":
    main()
