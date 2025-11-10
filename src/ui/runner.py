"""Helper entrypoint to launch the Streamlit UI via `poetry run ui`."""

from __future__ import annotations

import sys
from pathlib import Path

from streamlit.web.cli import main as streamlit_main


def main() -> int:
    """Invoke Streamlit with the bundled app."""
    app_path = Path(__file__).with_name("app.py")
    sys.argv = ["streamlit", "run", str(app_path)]
    return streamlit_main()


if __name__ == "__main__":  # pragma: no cover - convenience entry
    raise SystemExit(main())
