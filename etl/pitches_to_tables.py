"""네이버 투구 CSV(data/pitches_*.csv) → DB 적재용 data/load/pitch.csv

선수ID를 못 찾은 투구는 FK를 만족할 수 없어 빼고, 몇 개를 뺐는지 출력한다.
적재: psql -d kbo -f erd/ddl/08_load_pitch.sql (레포 최상위 폴더에서)

사용 예: python etl/pitches_to_tables.py data/pitches_2025_OB.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLS = ["game_id", "pitch_seq", "inning", "half", "at_bat_no", "pitch_no", "pitcher_id", "batter_id", "balls",
        "strikes", "outs", "pitch_type_ko", "speed_kmh", "pitch_result_code", "plate_x", "plate_z", "sz_top",
        "sz_bot", "batter_stance", "pa_result_text", "naver_pitch_id"]


def convert(inputs: list[Path], out: Path, known_pitch_types: set[str]) -> dict[str, int]:
    kept, dropped_ids, unknown_type = [], 0, 0
    for path in inputs:
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if not r.get("pitcher_id") or not r.get("batter_id"):
                    dropped_ids += 1
                    continue
                if r.get("pitch_type_ko") and r["pitch_type_ko"] not in known_pitch_types:
                    unknown_type += 1
                    r["pitch_type_ko"] = ""  # 기준표(data/reference/pitch_type.csv)에 추가하면 다시 살릴 수 있음
                if r.get("speed_kmh") and not (50 <= float(r["speed_kmh"]) <= 175):
                    r["speed_kmh"] = ""
                kept.append({c: r.get(c, "") for c in COLS})
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(kept)
    return {"kept": len(kept), "dropped_no_player_id": dropped_ids, "unknown_pitch_type": unknown_type}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "load" / "pitch.csv")
    args = ap.parse_args(argv)
    inputs = args.inputs or sorted((ROOT / "data").glob("pitches_*.csv"))
    with open(ROOT / "data" / "reference" / "pitch_type.csv", encoding="utf-8") as f:
        known = {r["pitch_type_ko"] for r in csv.DictReader(f)}
    stats = convert(inputs, args.out, known)
    print(f"{args.out}: {stats}")
    return 0


if __name__ == "__main__":
    if __package__ in (None, ""):
        sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
