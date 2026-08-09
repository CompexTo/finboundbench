"""Figure 2 (paper): FinBoundBench conditions schematic.

Same case, seven purpose-paired renderings. The confidential field is green
(authorized/visible), red (prohibited/visible), or gray (masked). ND repeats
the identical input x3 (floor estimate).

Standalone: matplotlib only. Outputs results/v4/figures/conditions-schematic.{pdf,png}
"""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "v4" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONDITIONS = [
    ("A0", "no purpose", "baseline", "gray", "none"),
    ("A1", "purpose", "authorized", "green", "governed=false"),
    ("A3", "purpose", "authorized", "green", "governed"),
    ("P0", "prohibited", "prohibited", "red", "governed=false"),
    ("P2", "prohibited", "prohibited", "gray", "masked"),
    ("P3", "prohibited", "prohibited", "gray", "masked+governed"),
]

COLORS = {"green": "#2e9e5b", "red": "#d64545", "gray": "#b8b8b8"}

fig, ax = plt.subplots(figsize=(7.0, 2.6), dpi=200)
ax.set_xlim(0, 100)
ax.set_ylim(0, 10)
ax.axis("off")

box_w, box_h = 12.5, 6.0
gap = 2.2
x0 = 2.0
y0 = 2.2

for i, (code, purpose, field_state, color, mode) in enumerate(CONDITIONS):
    x = x0 + i * (box_w + gap)
    face = COLORS[color] if color != "gray" else "white"
    edge = "#555555" if color == "gray" else COLORS[color]
    fc = "white"
    rect = plt.Rectangle((x, y0), box_w, box_h, facecolor=fc, edgecolor=edge, linewidth=1.6)
    ax.add_patch(rect)
    ax.text(x + box_w / 2, y0 + box_h - 1.1, code, ha="center", va="center", fontsize=13, fontweight="bold")
    ax.text(x + box_w / 2, y0 + box_h - 3.0, purpose, ha="center", va="center", fontsize=7.5, color="#444444")
    # field chip
    chip_w, chip_h = 8.5, 1.5
    cx = x + box_w / 2 - chip_w / 2
    cy = y0 + 0.75
    chip = plt.Rectangle((cx, cy), chip_w, chip_h, facecolor=face, edgecolor=edge, linewidth=1.2)
    ax.add_patch(chip)
    label = "field" if color == "green" else ("field" if color == "red" else "masked")
    ax.text(x + box_w / 2, cy + chip_h / 2, label, ha="center", va="center", fontsize=7, color="black")
    ax.text(x + box_w / 2, y0 - 1.3, mode, ha="center", va="center", fontsize=7, color="#555555")

# ND column (repeated x3)
x_nd = x0 + 6 * (box_w + gap)
for k in range(3):
    x = x_nd + k * (box_w / 2 + 0.8)
    rect = plt.Rectangle((x, y0), box_w / 2, box_h, facecolor="white", edgecolor="#888888", linewidth=1.4, linestyle="--")
    ax.add_patch(rect)
    ax.text(x + box_w / 4, y0 + box_h / 2, "ND", ha="center", va="center", fontsize=10, color="#555555")
ax.text(x_nd + box_w / 2, y0 - 1.3, "same input x3 (floor)", ha="center", va="center", fontsize=7, color="#555555")

# Decision arrows
for i in range(len(CONDITIONS)):
    x = x0 + i * (box_w + gap)
    ax.annotate("", xy=(x + box_w / 2, y0 - 0.4), xytext=(x + box_w / 2, y0 - 0.05),
                arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.2))
    ax.text(x + box_w / 2, y0 - 2.6, "decision", ha="center", va="center", fontsize=6.5, color="#333333")
for k in range(3):
    x = x_nd + k * (box_w / 2 + 0.8)
    ax.annotate("", xy=(x + box_w / 4, y0 - 0.4), xytext=(x + box_w / 4, y0 - 0.05),
                arrowprops=dict(arrowstyle="-|>", color="#999999", lw=1.0))

# Legend annotations
ax.text(2.0, 9.1, "same case, same public features, same label", fontsize=9, color="#222222")
ax.annotate("authorized: field visible + purpose", xy=(x0 + box_w + gap + box_w / 2, 9.1),
            xytext=(x0 + box_w + gap + box_w / 2, 8.5),
            fontsize=7, ha="center", color=COLORS["green"])
ax.annotate("prohibited: field visible (failure mode)", xy=(x0 + 3 * (box_w + gap) + box_w / 2, 9.1),
            xytext=(x0 + 3 * (box_w + gap) + box_w / 2, 8.5),
            fontsize=7, ha="center", color=COLORS["red"])

plt.tight_layout()
fig.savefig(OUT_DIR / "conditions-schematic.pdf", bbox_inches="tight")
fig.savefig(OUT_DIR / "conditions-schematic.png", bbox_inches="tight")
print(f"wrote {OUT_DIR / 'conditions-schematic.pdf'}")
