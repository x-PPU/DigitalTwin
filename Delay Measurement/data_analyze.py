# -*- coding: utf-8 -*-
"""
Delay Measurement Analyzer (xPPU_DT)

This script analyzes delay/latency logs exported as CSV files from three folders
that are located at the same directory level as this script:

1) WorkStation/  (IPC-side ADS -> WebSocket RTT measurement)
   - Expected columns: t0_ns, t_return_ns (optionally seq, var_name)
   - Per CSV file:
       * Use rows where BOTH t0_ns and t_return_ns are present.
       * Compute RTT in milliseconds: RTT_ms = (t_return_ns - t0_ns) / 1e6
       * Compute ONE per-file mean RTT (average of all valid RTT_ms in that file).
   - Missing-return check (noise-tolerant):
       * Find the first row where BOTH t0_ns and t_return_ns are present (the first valid pair).
       * If there exists any row BELOW that row where t0_ns is present but t_return_ns is missing,
         print the CSV name and those row indices (needs investigation).
       * If such missing rows only appear ABOVE the first valid pair, do NOT print.
   - Optional integrity check (if seq exists):
       * start = first valid pair row
       * end   = last row with non-empty var_name (or last row if var_name not present)
       * Compare (end_row - start_row) vs (end_seq - start_seq); if different, print mismatch.

2) PutServer/
   - Expected columns:
       var_name,value,seq,t0_ns,t_receive_ns,mapped_name,t_req0_ns,t_resp_ns,http_status
   - Per CSV file:
       * Parse time (ms):  (t_req0_ns - t_receive_ns) / 1e6  for rows with both timestamps
       * PUT time   (ms):  (t_resp_ns - t_req0_ns) / 1e6     for rows with both timestamps
       * Compute ONE per-file mean parse time and ONE per-file mean PUT time.
   - Status check:
       * If any http_status is non-empty and not "204", print CSV name and the status values.
       * Otherwise, print: all PUT succeeded.

3) Unity/
   - Expected columns:
       var_name,seq,value,t0_ns,unity_recv_ns,unity_event,unity_time_ns,kind
   - Per CSV file:
       * Skip rows where kind == "Received"
       * Scene update time (ms): (unity_time_ns - unity_recv_ns) / 1e6
       * Compute ONE per-file mean scene update time.

Plot output:
- Create ONE PNG: pipeline_latency_violin.png
- Four separate violin subplots (independent y-axis):
    WorkStation RTT, PutServer Parse, PutServer PUT, Unity Scene Update
- No grid lines.
- No median/box/scatter overlays.
- Mean is shown as a red 'x' marker with a legend in the upper-right of each subplot.

"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Any

import csv
import math
import statistics

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


# =============================================================================
# Helpers
# =============================================================================
def to_int_or_none(x: Any) -> Optional[int]:
    """Convert a CSV cell to int if possible; return None for empty/invalid values."""
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    try:
        # tolerate "123.0" produced by some tools
        return int(float(s))
    except Exception:
        return None


def to_str(x: Any) -> str:
    """Convert a CSV cell to stripped string (never None)."""
    if x is None:
        return ""
    return str(x).strip()


def is_nan(x: float) -> bool:
    """NaN check (used to guard statistics results)."""
    return isinstance(x, float) and math.isnan(x)


class CsvScanner:
    """List all *.csv files in a given folder (sorted by name)."""

    def __init__(self, folder: Path):
        self.folder = folder

    def list_csv_files(self) -> List[Path]:
        if not self.folder.exists():
            print(f"[WARN] Folder not found: {self.folder}")
            return []
        files = sorted(p for p in self.folder.glob("*.csv") if p.is_file())
        print(f"[SCAN] {len(files)} CSV files in {self.folder}")
        return files


# =============================================================================
# WorkStation Analyzer
# =============================================================================
@dataclass
class WorkStationFileResult:
    filename: str
    rtt_mean_ms: Optional[float]
    n_samples: int
    late_missing_return_rows: List[int]
    first_valid_row: Optional[int]
    seq_row_diff: Optional[int]
    seq_val_diff: Optional[int]


class WorkStationAnalyzer:
    """
    WorkStation/ CSV:
    - Compute per-file mean RTT (ms) from rows where both t0_ns and t_return_ns exist.
    - Apply missing-return check described in the header docstring.
    - Optional seq integrity check.
    """

    @staticmethod
    def _read_csv(csv_path: Path) -> List[dict]:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def analyze_file(self, csv_path: Path) -> WorkStationFileResult:
        rows = self._read_csv(csv_path)

        # Locate first valid pair row (t0_ns and t_return_ns both present)
        first_valid_idx0: Optional[int] = None
        for i, r in enumerate(rows):
            t0 = to_int_or_none(r.get("t0_ns"))
            tr = to_int_or_none(r.get("t_return_ns"))
            if t0 is not None and tr is not None:
                first_valid_idx0 = i
                break

        # Collect RTT samples (ms), only from rows where both t0_ns and t_return_ns are present
        samples_ms: List[float] = []
        for r in rows:
            t0 = to_int_or_none(r.get("t0_ns"))
            tr = to_int_or_none(r.get("t_return_ns"))
            if t0 is None or tr is None:
                continue
            samples_ms.append((tr - t0) / 1_000_000.0)

        rtt_mean_ms = statistics.mean(samples_ms) if samples_ms else None

        # Missing logic: detect t0-present / return-missing rows AFTER first valid pair
        late_missing_return_rows: List[int] = []
        if first_valid_idx0 is not None:
            for i, r in enumerate(rows):
                t0 = to_int_or_none(r.get("t0_ns"))
                tr = to_int_or_none(r.get("t_return_ns"))
                if t0 is not None and tr is None and i > first_valid_idx0:
                    # 1-based row index for data rows (excluding header)
                    late_missing_return_rows.append(i + 1)

        # Optional seq consistency check
        seq_row_diff: Optional[int] = None
        seq_val_diff: Optional[int] = None
        if rows and "seq" in rows[0] and first_valid_idx0 is not None:
            # Determine end row: last non-empty var_name if available, otherwise last row
            end_idx0 = None
            if "var_name" in rows[0]:
                for j in range(len(rows) - 1, -1, -1):
                    if to_str(rows[j].get("var_name")) != "":
                        end_idx0 = j
                        break
            if end_idx0 is None:
                end_idx0 = len(rows) - 1

            if end_idx0 >= first_valid_idx0:
                start_seq = to_int_or_none(rows[first_valid_idx0].get("seq"))
                end_seq = to_int_or_none(rows[end_idx0].get("seq"))
                if start_seq is not None and end_seq is not None:
                    seq_row_diff = end_idx0 - first_valid_idx0
                    seq_val_diff = end_seq - start_seq

        return WorkStationFileResult(
            filename=csv_path.name,
            rtt_mean_ms=rtt_mean_ms,
            n_samples=len(samples_ms),
            late_missing_return_rows=late_missing_return_rows,
            first_valid_row=(first_valid_idx0 + 1) if first_valid_idx0 is not None else None,
            seq_row_diff=seq_row_diff,
            seq_val_diff=seq_val_diff,
        )

    def analyze_folder(self, folder: Path) -> Tuple[List[WorkStationFileResult], List[float]]:
        files = CsvScanner(folder).list_csv_files()

        results: List[WorkStationFileResult] = []
        per_file_means: List[float] = []

        for p in files:
            r = self.analyze_file(p)
            results.append(r)

            # Print only when missing-return occurs AFTER the first valid pair
            if r.late_missing_return_rows:
                print(
                    f"[WS-LATE-MISSING-RETURN] {r.filename}: "
                    f"rows={r.late_missing_return_rows} "
                    f"(first_valid_row={r.first_valid_row}) -> please investigate"
                )

            # Print only when seq integrity mismatch happens
            if (
                r.seq_row_diff is not None
                and r.seq_val_diff is not None
                and r.seq_row_diff != r.seq_val_diff
            ):
                print(
                    f"[WS-SEQ-MISMATCH] {r.filename}: "
                    f"(end_row-start_row)={r.seq_row_diff}, (end_seq-start_seq)={r.seq_val_diff}"
                )

            if r.rtt_mean_ms is not None and not is_nan(r.rtt_mean_ms):
                per_file_means.append(r.rtt_mean_ms)

        return results, per_file_means


# =============================================================================
# PutServer Analyzer
# =============================================================================
@dataclass
class PutServerFileResult:
    filename: str
    parse_mean_ms: Optional[float]
    put_mean_ms: Optional[float]
    n_parse_samples: int
    n_put_samples: int
    non_204_statuses: List[str]


class PutServerAnalyzer:
    """
    PutServer/ CSV:
    - Parse time: (t_req0_ns - t_receive_ns) / 1e6
    - PUT time:   (t_resp_ns - t_req0_ns)   / 1e6
    - Compute per-file means for parse and put.
    - Print non-204 http_status values, or success summary.
    """

    @staticmethod
    def _read_csv(csv_path: Path) -> List[dict]:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def analyze_file(self, csv_path: Path) -> PutServerFileResult:
        rows = self._read_csv(csv_path)

        parse_samples: List[float] = []
        put_samples: List[float] = []
        non_204: List[str] = []

        for r in rows:
            trecv = to_int_or_none(r.get("t_receive_ns"))
            treq = to_int_or_none(r.get("t_req0_ns"))
            tresp = to_int_or_none(r.get("t_resp_ns"))
            status = to_str(r.get("http_status"))

            if status != "" and status != "204":
                non_204.append(status)

            if trecv is not None and treq is not None:
                parse_samples.append((treq - trecv) / 1_000_000.0) # parse time in ms
 
            if treq is not None and tresp is not None:
                put_samples.append((tresp - treq) / 1_000_000.0) # put time in ms

        return PutServerFileResult(
            filename=csv_path.name,
            parse_mean_ms=statistics.mean(parse_samples) if parse_samples else None,
            put_mean_ms=statistics.mean(put_samples) if put_samples else None,
            n_parse_samples=len(parse_samples),
            n_put_samples=len(put_samples),
            non_204_statuses=sorted(set(non_204)),
        )

    def analyze_folder(self, folder: Path) -> Tuple[List[PutServerFileResult], List[float], List[float]]:
        files = CsvScanner(folder).list_csv_files()

        results: List[PutServerFileResult] = []
        parse_means: List[float] = []
        put_means: List[float] = []
        any_non204 = False

        for p in files:
            r = self.analyze_file(p)
            results.append(r)

            if r.non_204_statuses:
                any_non204 = True
                print(f"[PUTSERVER-NON204] {r.filename}: {r.non_204_statuses}")

            if r.parse_mean_ms is not None and not is_nan(r.parse_mean_ms):
                parse_means.append(r.parse_mean_ms)
            if r.put_mean_ms is not None and not is_nan(r.put_mean_ms):
                put_means.append(r.put_mean_ms)

        if not any_non204 and files:
            print("[PUTSERVER] all values put successfully (http_status == 204)")

        return results, parse_means, put_means


# =============================================================================
# Unity Analyzer
# =============================================================================
@dataclass
class UnityFileResult:
    filename: str
    scene_mean_ms: Optional[float]
    n_samples: int


class UnityAnalyzer:
    """
    Unity/ CSV:
    - Skip rows where kind == "Received"
    - Scene update time: (unity_time_ns - unity_recv_ns) / 1e6
    - Compute per-file mean scene update time.
    """

    @staticmethod
    def _read_csv(csv_path: Path) -> List[dict]:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def analyze_file(self, csv_path: Path) -> UnityFileResult:
        rows = self._read_csv(csv_path)

        samples: List[float] = []
        for r in rows:
            if to_str(r.get("kind")) == "Received":
                continue

            recv = to_int_or_none(r.get("unity_recv_ns"))
            ut = to_int_or_none(r.get("unity_time_ns"))
            if recv is None or ut is None:
                continue

            samples.append((ut - recv) / 1_000_000.0)

        return UnityFileResult(
            filename=csv_path.name,
            scene_mean_ms=statistics.mean(samples) if samples else None,
            n_samples=len(samples),
        )

    def analyze_folder(self, folder: Path) -> Tuple[List[UnityFileResult], List[float]]:
        files = CsvScanner(folder).list_csv_files()

        results: List[UnityFileResult] = []
        means: List[float] = []

        for p in files:
            r = self.analyze_file(p)
            results.append(r)
            if r.scene_mean_ms is not None and not is_nan(r.scene_mean_ms):
                means.append(r.scene_mean_ms)

        return results, means


# =============================================================================
# Plotter: 4 violin subplots + mean marker legend
# =============================================================================
class ViolinPlotter:
    def __init__(self, out_path: Path):
        self.out_path = out_path

        # ===== Font sizes (paper-ready) =====
        self.label_fs = 12     # y-axis label: "Latency (ms)"
        self.tick_fs = 12      # x/y tick labels
        self.legend_fs = 12    # legend text
        self.title_fs = 12     # stage name under each violin

        # Reusable legend handle (so every subplot has same legend style)
        self.mean_handle = Line2D(
            [0], [0],
            marker="x",
            color="red",
            linestyle="None",
            markersize=9,
            markeredgewidth=2,
            label="Mean",
        )

    def violin_one(self, ax, data: List[float], stage_name: str, ylabel: str):
        """Draw one violin plot with mean marker and a small legend in the upper-right."""

        # ---- X / Y labels ----
        ax.set_xticks([1])
        ax.set_xticklabels([stage_name], fontsize=self.title_fs)
        ax.set_ylabel(ylabel, fontsize=self.label_fs)

        # ---- Tick font size ----
        ax.tick_params(axis="x", labelsize=self.tick_fs)
        ax.tick_params(axis="y", labelsize=self.tick_fs)

        ax.grid(False)

        if not data:
            ax.text(
                0.5, 0.5, "No data",
                ha="center", va="center",
                transform=ax.transAxes,
                fontsize=self.label_fs
            )
            ax.legend(
                handles=[self.mean_handle],
                loc="upper right",
                frameon=True,
                fontsize=self.legend_fs
            )
            return

        # ---- Violin plot ----
        ax.violinplot(
            data,
            positions=[1],
            widths=0.85,
            showmeans=False,
            showmedians=False,
            showextrema=True,
        )

        # ---- Mean marker (red X) ----
        mean_v = statistics.mean(data)
        ax.scatter(
            [1], [mean_v],
            marker="x",
            s=90,
            c="red",
            linewidths=2,
            zorder=5
        )

        # ---- Legend ----
        ax.legend(
            handles=[self.mean_handle],
            loc="upper right",
            frameon=True,
            fontsize=self.legend_fs
        )

    def plot_all(
        self,
        ws_rtt_ms: List[float],
        ps_parse_ms: List[float],
        ps_put_ms: List[float],
        unity_scene_ms: List[float],
    ):
        fig, axes = plt.subplots(1, 4, figsize=(9, 3.5), sharey=False)

        self.violin_one(axes[0], ws_rtt_ms, "RTT time", "Latency (ms)")
        self.violin_one(axes[1], ps_parse_ms, "Local Parsing time", "Latency (ms)")
        self.violin_one(axes[2], ps_put_ms, "Request-Response latency", "Latency (ms)")
        self.violin_one(axes[3], unity_scene_ms, "Scene Update latency", "Latency (ms)")

        fig.tight_layout()
        fig.savefig(self.out_path, dpi=300)
        print(f"[PLOT SAVED] {self.out_path}")

# =============================================================================
# Orchestrator
# =============================================================================
class DelayPipelineAnalyzer:
    """High-level runner: analyze folders and generate a single violin figure."""

    def __init__(self, root: Path):
        self.root = root

        # Folders are at the same level as this script
        self.ws_folder = root / "WorkStation"
        self.ps_folder = root / "PutServer"
        self.unity_folder = root / "Unity"

        self.out_path = root / "latency_violin.png"

        self.ws = WorkStationAnalyzer()
        self.ps = PutServerAnalyzer()
        self.unity = UnityAnalyzer()

    @staticmethod
    def _median_or_nan(vals: List[float]) -> float:
        """Used only for console summary output."""
        return statistics.median(vals) if vals else float("nan")

    def run(self):
        ws_results, ws_means = self.ws.analyze_folder(self.ws_folder)
        ps_results, ps_parse_means, ps_put_means = self.ps.analyze_folder(self.ps_folder)
        unity_results, unity_means = self.unity.analyze_folder(self.unity_folder)

        # Console summary (median is robust for quick sanity check)
        print(
            "[SUMMARY] "
            f"WorkStation_files={len(ws_results)}, WorkStation_used={len(ws_means)}, WorkStation_median_ms={self._median_or_nan(ws_means)} | "
            f"PutServer_files={len(ps_results)}, PutServer_parse_used={len(ps_parse_means)}, PutServer_put_used={len(ps_put_means)}, PutServer_parse_median_ms={self._median_or_nan(ps_parse_means)}, PutServer_put_median_ms={self._median_or_nan(ps_put_means)} | "
            f"Unity_files={len(unity_results)}, Unity_used={len(unity_means)}, Unity_median_ms={self._median_or_nan(unity_means)}"
        )

        # Plot
        ViolinPlotter(self.out_path).plot_all(ws_means, ps_parse_means, ps_put_means, unity_means)


def main():
    # Dynamic root: the directory where this script is located
    root = Path(__file__).resolve().parent
    DelayPipelineAnalyzer(root).run()


if __name__ == "__main__":
    main()