"""ExperimentPlotter class: generates Matplotlib evaluation and scaling charts."""
from __future__ import annotations

from pathlib import Path

from Experiments.evaluation_wardens import WARDENS

SERIES_COLORS: dict[str, str] = {
    "W0": "#2a78d6",
    "W1": "#eb6834",
    "W2": "#1baf7a",
    "W3": "#eda100",
}


class ExperimentPlotter:
    """Generates PNG charts for Warden comparisons and complexity scaling."""

    @staticmethod
    def _apply_axis_style(ax, title: str, ylabel: str) -> None:
        ax.set_title(title, loc="left", fontsize=12, color="#1a1a19", pad=12)
        ax.set_ylabel(ylabel, color="#5f5e5a")
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
        ax.set_axisbelow(True)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color("#c3c2b7")
        ax.tick_params(colors="#5f5e5a", length=0)

    @classmethod
    def plot_by_warden(
        cls,
        rows: list[dict],
        metric: str,
        title: str,
        ylabel: str,
        out_path: Path,
        pct: bool = False,
    ) -> None:
        """Render a grouped bar chart comparing Wardens across simulated bots."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        bots = sorted({r["bot"] for r in rows})
        wardens = sorted({r["warden"] for r in rows})
        fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=150)
        bar_width = 0.8 / len(wardens)

        for i, w_key in enumerate(wardens):
            for j, b_key in enumerate(bots):
                rec = next((r for r in rows if r["warden"] == w_key and r["bot"] == b_key), None)
                if rec is None:
                    continue
                val = rec[metric] * (100 if pct else 1)
                x = j + (i - (len(wardens) - 1) / 2) * bar_width
                label = f"{w_key} {WARDENS[w_key].label}" if j == 0 else None
                ax.bar(
                    x,
                    val,
                    bar_width - 0.03,
                    color=SERIES_COLORS.get(w_key, "#888"),
                    label=label,
                )
                val_text = f"{val:.0f}" if pct else f"{val:.1f}"
                ax.text(x, val, val_text, ha="center", va="bottom", fontsize=8, color="#5f5e5a")

        ax.set_xticks(range(len(bots)), [b.title() for b in bots])
        cls._apply_axis_style(ax, title, ylabel)
        ax.legend(
            frameon=False,
            ncols=len(wardens),
            loc="upper center",
            bbox_to_anchor=(0.5, -0.1),
            fontsize=9,
        )
        fig.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)

    @classmethod
    def plot_all_evaluation_charts(cls, summary: list[dict], out_dir: Path) -> bool:
        """Generate all four evaluation charts into `out_dir`. Returns False if matplotlib is missing."""
        try:
            cls.plot_by_warden(
                summary,
                "turns",
                "Turns the player needed to reach the treasure (higher is better for the Warden)",
                "turns",
                out_dir / "turns.png",
            )
            if any(r["player_win_rate"] < 1 for r in summary):
                cls.plot_by_warden(
                    summary,
                    "player_win_rate",
                    "Player win rate (lower is better for the Warden)",
                    "% games won by player",
                    out_dir / "win_rate.png",
                    pct=True,
                )
            cls.plot_by_warden(
                summary,
                "path_increase",
                "Path-length increase forced on the player",
                "extra steps vs shortest path",
                out_dir / "path_increase.png",
            )
            cls.plot_by_warden(
                summary,
                "belief_precision",
                "Belief precision (mean 1/|B_t|)",
                "precision",
                out_dir / "belief_precision.png",
            )
            return True
        except ImportError:
            return False

    @classmethod
    def plot_scaling_chart(cls, rows: list[dict], out_path: Path) -> bool:
        """Render the indexed runtime scaling curve vs theoretical complexity estimate."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            xs = [r["n"] for r in rows]
            base_ms = rows[0]["ms_mean"] or 1e-9
            base_est = rows[0]["estimate"]
            measured = [r["ms_mean"] / base_ms for r in rows]
            estimate = [r["estimate"] / base_est for r in rows]

            fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=150)
            ax.plot(
                xs,
                measured,
                color=SERIES_COLORS["W0"],
                linewidth=2,
                marker="o",
                markersize=5,
                label="measured time per move",
            )
            ax.plot(
                xs,
                estimate,
                color=SERIES_COLORS["W1"],
                linewidth=2,
                marker="s",
                markersize=5,
                linestyle="--",
                label="estimate b^(d/2)·V·log V",
            )
            ax.annotate(
                "measured",
                (xs[-1], measured[-1]),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=9,
                color="#1a1a19",
            )
            ax.annotate(
                "estimate",
                (xs[-1], estimate[-1]),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=9,
                color="#1a1a19",
            )
            ax.set_xticks(xs, [f"{n}x{n}" for n in xs])
            cls._apply_axis_style(
                ax,
                f"W2 cost per move vs grid size (indexed, {xs[0]}x{xs[0]} = 1)",
                "relative to smallest grid",
            )
            ax.legend(frameon=False, loc="upper left", fontsize=9)
            fig.tight_layout()
            fig.savefig(out_path)
            plt.close(fig)
            return True
        except ImportError:
            return False

