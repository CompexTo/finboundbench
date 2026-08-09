"""Headline figure (phase 5): AUR + UIR-above-floor per study, frozen/confirmed data only.

Reads the two per-study statistical reports (primary + replication) and renders
a 2x2 figure: rows = studies, columns = AUR panel | UIR-by-condition panel.
Output bound to the frozen reports via provenance JSON.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
PRIMARY = ROOT / "results/v4/statistics/primary-statistical-report.json"
REPLICATION = ROOT / "results/v4/statistics/replication-statistical-report.json"
OUT_DIR = ROOT / "results/v4/figures"
OUT_PNG = OUT_DIR / "headline-figure.png"
OUT_PDF = OUT_DIR / "headline-figure.pdf"
PROV = OUT_DIR / "headline-figure-provenance.json"

reports = [json.loads(PRIMARY.read_text(encoding="utf-8")),
           json.loads(REPLICATION.read_text(encoding="utf-8"))]
labels = ["primary\ndeepseek × hardship\n(n=100 pairs)", "replication\nkimi × fraud\n(n=113–120 pairs)"]

fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.2))

for i, (r, ax_aur, ax_uir) in enumerate(zip(reports, axes[:, 0], axes[:, 1])):
    m_ = r["metrics"]
    h2 = r["results"]["H2"]
    h3 = r["results"]["H3"]
    label = labels[i]

    # AUR panel
    aur, lo, hi = h2["aur"], h2["ci95_lo"], h2["ci95_hi"]
    ax_aur.axhspan(0.60, 0.80, color="tab:orange", alpha=0.08)
    ax_aur.axhline(0.80, color="tab:orange", ls="--", lw=1.2)
    ax_aur.axhline(0.60, color="tab:orange", ls=":", lw=1.2)
    if aur is not None:
        ax_aur.errorbar([aur], [0], xerr=[[max(aur - lo, 0)], [max(hi - aur, 0)]], fmt="o", ms=10,
                        color="#14532d", capsize=6, ecolor="#14532d", elinewidth=2,
                        label=f"AUR {aur:.2f} [{lo:.2f}, {hi:.2f}]")
        ax_aur.text(0.965, 0.985, f"{h2['decision']}", transform=ax_aur.transAxes, ha="right", va="top",
                    fontsize=10, fontweight="bold",
                    color=("green" if h2["decision"] == "PASS" else "red"))
    ax_aur.set_xlim(0.3, 1.15)
    ax_aur.set_ylim(0.0, 1.05)
    ax_aur.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax_aur.set_ylabel("AUR" if i == 0 else "")
    ax_aur.set_title(f"AUR — {label}", fontsize=9)
    ax_aur.legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax_aur.grid(axis="y", alpha=0.25)

    # UIR panel
    conds = ["ND", "P2", "P3", "P0"]
    uir = [m_["nd_floor"], m_["uir_rates"]["P2"], m_["uir_rates"]["P3"], m_["uir_rates"]["P0"]]
    colors = ["#8a8f98"] + ["#2e7d32"] * 2 + ["#c62828"]
    bars = ax_uir.bar(conds, uir, color=colors, alpha=0.85, width=0.62)
    for b, v in zip(bars, uir):
        ax_uir.text(b.get_x() + b.get_width() / 2, (v or 0) + 0.02, f"{v:.2f}", ha="center", fontsize=9)
    ax_uir.axhline(m_["nd_floor"], color="#8a8f98", ls=":", lw=1.2)
    ax_uir.annotate(f"Net UI = {h3['netui_point']:.2f}",
                    xy=(3, m_["uir_rates"]["P0"]), xytext=(1.55, 0.85),
                    fontsize=9, arrowprops=dict(arrowstyle="->", color="black", lw=1.0))
    ax_uir.text(0.965, 0.985, f"{h3['decision']}/{r['results']['H5']['decision']}/{r['results']['H6']['decision']}",
                transform=ax_uir.transAxes, ha="right", va="top",
                fontsize=9, fontweight="bold",
                color=("green" if h3["decision"] == "PASS" else "red"))
    ax_uir.set_ylim(-0.05, 1.1)
    ax_uir.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax_uir.set_ylabel("UIR (unauthed influence rate)" if i == 0 else "")
    ax_uir.set_title(f"Unauthorized influence — {label}", fontsize=9)
    ax_uir.grid(axis="y", alpha=0.25)

fig.suptitle(
    "Confirmatory protocol-v4 — both studies (frozen) · H2 badge = AUR decision; H3/H5/H6 badges = chain-2 decisions",
    fontsize=10, color="#333",
)
fig.tight_layout(rect=(0, 0, 1, 0.96))

OUT_DIR.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT_PNG, dpi=200)
fig.savefig(OUT_PDF)
prov = {
    "phase": "5-headline-figure",
    "sources": [str(PRIMARY.relative_to(ROOT)), str(REPLICATION.relative_to(ROOT))],
    "report_shas": {PRIMARY.name: reports[0]["report_sha256"],
                    REPLICATION.name: reports[1]["report_sha256"]},
    "data_only_frozen": True,
    "files": [OUT_PNG.name, OUT_PDF.name],
}
PROV.write_text(json.dumps(prov, indent=2, sort_keys=True), encoding="utf-8")
print("wrote", OUT_PNG, "and", OUT_PDF)
print("provenance:", PROV)
