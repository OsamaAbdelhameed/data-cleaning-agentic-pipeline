"""
Generate LangGraph pipeline diagram using the graph's built-in draw methods.
Run from project root: python scripts/generate_diagram.py

Outputs:
  - pipeline_diagram.mmd   Mermaid source (paste into README or mermaid.live)
  - pipeline_diagram.png   PNG image (if mermaid.ink API is reachable)
  - ASCII diagram printed to stdout
"""

import sys
from pathlib import Path

# Run from project root so pipeline is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import build_graph

def main() -> None:
    graph = build_graph().compile()
    drawable = graph.get_graph()

    out_dir = PROJECT_ROOT / "docs"
    out_dir.mkdir(exist_ok=True)

    # 1. Mermaid source
    mermaid_syntax = drawable.draw_mermaid()
    mmd_path = out_dir / "pipeline_diagram.mmd"
    mmd_path.write_text(mermaid_syntax, encoding="utf-8")
    print(f"Mermaid source written to: {mmd_path}")
    print("\n--- Mermaid (copy into README or https://mermaid.live) ---\n")
    print(mermaid_syntax)
    print("\n--- end Mermaid ---\n")

    # 2. ASCII (optional; requires grandalf)
    try:
        ascii_diagram = drawable.draw_ascii()
        print("ASCII diagram:\n")
        print(ascii_diagram)
    except ImportError as e:
        print(f"ASCII skipped (install grandalf for ASCII): {e}")

    # 3. PNG (requires network for mermaid.ink by default)
    png_path = out_dir / "pipeline_diagram.png"
    try:
        png_bytes = drawable.draw_mermaid_png()
        if png_bytes:
            png_path.write_bytes(png_bytes)
            print(f"\nPNG written to: {png_path}")
        else:
            print("\nPNG not generated (draw_mermaid_png returned empty).")
    except Exception as e:
        print(f"\nPNG not generated: {e}")
        print("You can paste the Mermaid from pipeline_diagram.mmd into https://mermaid.live to export an image.")


if __name__ == "__main__":
    main()
