"""기준 데이터 CSV(data-pipeline/data/reference) → Flyway 마이그레이션 SQL

Flyway 파일에는 psql 메타명령(\\copy)을 쓸 수 없어서 CSV를 INSERT 문으로 바꿔 넣는다.
모든 문장이 INSERT ... ON CONFLICT DO UPDATE 라서 여러 번 적용해도 결과가 같다.

  처음 한 번:   python tools/gen_reference_migration.py            → V2__reference_data.sql
  CSV를 고친 뒤: python tools/gen_reference_migration.py --version 5 --name reference_data_update
               (이미 머지된 V2는 고치지 않고 새 버전 파일을 만든다)
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data-pipeline/data/reference"
MIGRATION_DIR = ROOT / "backend/src/main/resources/db/migration"


def lit(v: str | None, kind: str = "text") -> str:
    if v is None or v == "":
        return "NULL"
    if kind == "int":
        return str(int(v))
    if kind == "bool":
        return "TRUE" if v.strip().lower() in ("1", "true", "t", "y") else "FALSE"
    return "'" + v.replace("'", "''") + "'"


# 테이블, CSV, (컬럼, 형식) 목록, 충돌 키 — CSV의 메모 컬럼(note, needs_check, aliases)은 넣지 않는다
SPECS = [
    ("team", "team.csv", [("team_id", "text"), ("team_name", "text"), ("city", "text"), ("first_season", "int")],
     ["team_id"]),
    ("stadium", "stadium.csv", [("stadium_id", "int"), ("stadium_name", "text"), ("city", "text"),
                                ("is_dome", "bool"), ("capacity", "int")], ["stadium_id"]),
    ("team_season", "team_season.csv", [("team_id", "text"), ("season", "int"), ("team_name", "text"),
                                        ("short_name", "text"), ("home_stadium_id", "int")], ["team_id", "season"]),
    ("pa_result_type", "pa_result_type.csv",
     [("result_type", "text"), ("result_type_name", "text"), ("batted_ball", "text"), ("is_at_bat", "bool"),
      ("is_hit", "bool"), ("total_bases", "int"), ("is_walk", "bool"), ("is_hbp", "bool"), ("is_sac_fly", "bool"),
      ("is_sac_bunt", "bool"), ("is_strikeout", "bool"), ("is_double_play", "bool")], ["result_type"]),
    ("pa_result_code", "pa_result_code.csv", [("result_code", "int"), ("result_name", "text"),
                                              ("result_type", "text"), ("fielder_pos", "int"), ("spray_dir", "text")],
     ["result_code"]),
    ("match_event_type", "match_event_type.csv", [("event_type", "text"), ("name_en", "text")], ["event_type"]),
]


def build() -> str:
    out = ["-- 기준 데이터 (팀, 구장, 팀시즌, 타석결과 코드표, 경기이벤트 종류)",
           "-- tools/gen_reference_migration.py 가 data-pipeline/data/reference/*.csv 에서 자동 생성. 직접 고치지 말 것.",
           ""]
    for table, file, cols, key in SPECS:
        with open(REF / file, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        names = [c for c, _ in cols]
        values = [f"    ({', '.join(lit(r[c], k) for c, k in cols)})" for r in rows]
        upd = [c for c in names if c not in key]
        out.append(f"-- {table} ({len(rows)}행, {file})")
        out.append(f"INSERT INTO {table} ({', '.join(names)}) VALUES")
        out.append(",\n".join(values))
        out.append(f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET "
                   + ", ".join(f"{c} = EXCLUDED.{c}" for c in upd) + ";")
        out.append("")
    out += ["-- 구장ID를 직접 넣었으므로 자동 증가 시작값을 최댓값 다음으로 맞춘다",
            "SELECT setval(pg_get_serial_sequence('stadium', 'stadium_id'), (SELECT max(stadium_id) FROM stadium));",
            ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="2")
    ap.add_argument("--name", default="reference_data")
    ap.add_argument("--stdout", action="store_true", help="파일 대신 화면에 출력")
    args = ap.parse_args()
    sql = build()
    if args.stdout:
        print(sql)
        return 0
    dst = MIGRATION_DIR / f"V{args.version}__{args.name}.sql"
    dst.write_text(sql, encoding="utf-8")
    print(f"→ {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
