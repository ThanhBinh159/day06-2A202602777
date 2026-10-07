"""Dashboard cơ bản về sức khoẻ point cloud cho topic E."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from starter.data_health import point_stats
from starter.datasets import list_frames, load_points


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export point cloud health CSV and dashboard"
    )
    parser.add_argument("--data-root", default="data/synthetic", help="KITTI or nuScenes data directory")
    parser.add_argument("--out-csv", default="results/topic_e_health.csv", help="output CSV path")
    parser.add_argument(
        "--out-plot",
        default="results/figures/topic_e_dashboard.png",
        help="output dashboard image path",
    )
    parser.add_argument(
        "--out-failure",
        default="results/figures/fail_topic_e_low_point_count.png",
        help="output low-count review image path",
    )
    args = parser.parse_args()

    rows = []
    range_chunks = []
    intensity_chunks = []
    for frame_id in list_frames(args.data_root):
        points = load_points(args.data_root, frame_id)
        rows.append({"frame_id": frame_id, **point_stats(points)})

        valid = points[np.isfinite(points).all(axis=1)]
        if len(valid):
            range_chunks.append(np.linalg.norm(valid[:, :2], axis=1))
            intensity_chunks.append(valid[:, 3])

    if not rows:
        raise SystemExit("No frames found. Check --data-root.")

    csv_path = Path(args.out_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    ranges = np.concatenate(range_chunks) if range_chunks else np.array([])
    intensities = np.concatenate(intensity_chunks) if intensity_chunks else np.array([])
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    _histogram(axes[0, 0], ranges, "Point range", "Range (m)")
    _histogram(axes[0, 1], intensities, "Intensity", "Intensity")

    _histogram(
        axes[1, 0],
        np.asarray([row["n_points"] for row in rows]),
        "Points per frame",
        "Points / frame",
    )
    _histogram(
        axes[1, 1],
        np.asarray([100 * row["invalid_ratio"] for row in rows]),
        "Invalid ratio per frame",
        "Invalid (%)",
    )

    plot_path = Path(args.out_plot)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    _save_low_count_candidate(rows, Path(args.out_failure))
    print(f"Processed {len(rows)} frames.")
    print("CSV, dashboard, and review image saved to the requested paths.")


def _histogram(ax, values: np.ndarray, title: str, xlabel: str) -> None:
    if values.size:
        ax.hist(values, bins=50, color="#3977a8", edgecolor="white")
    else:
        ax.text(0.5, 0.5, "No valid points", ha="center", va="center", transform=ax.transAxes)
    ax.set(title=title, xlabel=xlabel, ylabel="Count")


def _save_low_count_candidate(rows: list[dict], path: Path) -> None:
    # ponytail: lowest count can reflect a sparse scene; add azimuth/time context before auto-discard.
    counts = np.asarray([row["n_points"] for row in rows])
    candidate_index = int(np.argmin(counts))
    median = float(np.median(counts))
    candidate = rows[candidate_index]
    below_median = (median - counts[candidate_index]) / median if median else 0.0

    fig, ax = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
    colors = ["#c45a52" if i == candidate_index else "#3977a8" for i in range(len(rows))]
    ax.bar([row["frame_id"] for row in rows], counts, color=colors)
    ax.axhline(median, color="#555555", linestyle="--", label=f"median = {median:.0f}")
    fig.suptitle(
        f"Review candidate: frame {candidate['frame_id']} has {counts[candidate_index]:,} points, "
        f"{below_median:.1%} below median ({median:.0f})",
        fontsize=12,
    )
    ax.set(
        title="Point count by frame; cause is unconfirmed",
        xlabel="Frame",
        ylabel="Points",
    )
    ax.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
