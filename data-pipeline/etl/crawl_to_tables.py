"""크롤링 결과(data/*.csv) → DB 적재용 CSV (data/load/*.csv)

입력 (crawl/ 스크립트가 만든 파일, 없는 파일은 건너뜀)
    data/player_season_team.csv  season,team_id,player_id,name,is_batter,is_pitcher
    data/players.csv             선수 상세 (crawl/kbo_profiles.py)
    data/season_batting.csv      기록실 타자 (crawl/kbo_records.py)
    data/season_pitching.csv     기록실 투수
    data/team_rank.csv           팀 순위 (crawl/kbo_team_rank.py)
출력
    data/load/player.csv, player_season.csv, player_salary.csv,
    season_batting_official.csv, season_pitching_official.csv, team_rank_official.csv

선수 상세를 아직 못 받은 선수도 경기 기록을 적재할 수 있도록, 목록에 있는 선수는
이름만 채운 player 행을 만든다(나중에 상세를 받으면 덮어씀).

사용 예: python etl/crawl_to_tables.py --data data --out data/load
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PLAYER_COLS = ["player_id", "player_name", "birth_date", "height_cm", "weight_kg", "throws", "bats",
               "position", "career", "draft_info", "draft_year", "join_info", "join_year",
               "signing_bonus_10k", "is_retired", "profile_crawled_at",
               "current_team_name", "current_uniform_no", "profile_source_url"]
PLAYER_SEASON_COLS = ["player_id", "season", "team_id", "name_in_season", "is_batter", "is_pitcher", "uniform_no"]
SALARY_COLS = ["player_id", "season", "salary_10k_krw", "salary_usd", "source_text"]
BAT_COLS = ["player_id", "season", "team_id", "games", "plate_appearances", "at_bats", "runs", "hits",
            "doubles", "triples", "home_runs", "total_bases", "rbi", "sac_bunts", "sac_flies", "walks",
            "intentional_walks", "hbp", "strikeouts", "gidp", "avg", "obp", "slg", "ops", "crawled_at"]
PIT_COLS = ["player_id", "season", "team_id", "games", "wins", "losses", "saves", "holds", "outs_recorded",
            "hits_allowed", "home_runs_allowed", "walks", "hbp", "strikeouts", "runs_allowed", "earned_runs",
            "batters_faced", "pitches", "complete_games", "shutouts", "quality_starts", "blown_saves",
            "era", "whip", "crawled_at"]
RANK_COLS = ["season", "team_id", "as_of_date", "rank", "games", "wins", "losses", "draws", "win_pct",
             "games_behind", "last10", "streak", "crawled_at"]


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) in (None, "None", "nan") else r.get(c)) for c in cols})


def truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "t", "y", "yes")


def build(data_dir: Path, out_dir: Path) -> dict[str, int]:
    pst = read(data_dir / "player_season_team.csv")
    profiles = {r["player_id"]: r for r in read(data_dir / "players.csv")}
    bats = read(data_dir / "season_batting.csv")
    pits = read(data_dir / "season_pitching.csv")
    ranks = read(data_dir / "team_rank.csv")

    # player: 상세가 있으면 상세, 없으면 목록 이름으로 최소 행 --------------------
    players: dict[str, dict] = {}
    latest_name: dict[str, tuple[int, str]] = {}
    for r in pst + bats + pits:
        if not r.get("player_id"):
            continue
        season = int(r["season"])
        if r["player_id"] not in latest_name or season >= latest_name[r["player_id"]][0]:
            latest_name[r["player_id"]] = (season, r.get("name") or r.get("player_name") or "")
    for pid, (_, name) in latest_name.items():
        players[pid] = {"player_id": pid, "player_name": name, "is_retired": "false"}
    for pid, p in profiles.items():
        players[pid] = {**players.get(pid, {}), **{k: p.get(k) for k in PLAYER_COLS if k in p},
                        "player_id": pid, "player_name": p.get("player_name") or p.get("name")
                        or players.get(pid, {}).get("player_name")}
        players[pid]["is_retired"] = "true" if truthy(p.get("is_retired")) else "false"
        players[pid]["profile_crawled_at"] = p.get("crawled_at") or p.get("profile_crawled_at")
        # 이전 수집 CSV의 KBO 미등록 표기(0cm/0kg)도 NULL로 적재한다.
        for field in ("height_cm", "weight_kg"):
            if str(players[pid].get(field, "")).strip() == "0":
                players[pid][field] = None
        players[pid]["current_team_name"] = p.get("team_name")
        players[pid]["current_uniform_no"] = p.get("uniform_no")
        players[pid]["profile_source_url"] = p.get("source_url")

    # player_season: 목록(+기록실) 합치기. 현재 프로필을 과거 시즌에 소급하지 않는다 -------
    ps: dict[tuple, dict] = {}
    for r in pst:
        key = (r["player_id"], r["season"], r["team_id"])
        cur = ps.setdefault(key, {"player_id": r["player_id"], "season": r["season"], "team_id": r["team_id"],
                                  "name_in_season": r["name"], "is_batter": False, "is_pitcher": False})
        cur["is_batter"] |= truthy(r.get("is_batter"))
        cur["is_pitcher"] |= truthy(r.get("is_pitcher"))
    for rows, flag in ((bats, "is_batter"), (pits, "is_pitcher")):
        for r in rows:
            key = (r["player_id"], r["season"], r["team_id"])
            cur = ps.setdefault(key, {"player_id": r["player_id"], "season": r["season"], "team_id": r["team_id"],
                                      "name_in_season": r.get("name", ""), "is_batter": False, "is_pitcher": False})
            cur[flag] = True
    for v in ps.values():
        v["is_batter"] = "true" if v["is_batter"] else "false"
        v["is_pitcher"] = "true" if v["is_pitcher"] else "false"

    # player_salary -----------------------------------------------------------
    salaries = []
    for p in profiles.values():
        if p.get("salary_season") and (p.get("salary_10k_krw") or p.get("salary_usd")):
            salaries.append({"player_id": p["player_id"], "season": p["salary_season"],
                             "salary_10k_krw": p.get("salary_10k_krw"), "salary_usd": p.get("salary_usd"),
                             "source_text": p.get("salary_text")})

    write(out_dir / "player.csv", PLAYER_COLS, list(players.values()))
    write(out_dir / "player_season.csv", PLAYER_SEASON_COLS, list(ps.values()))
    write(out_dir / "player_salary.csv", SALARY_COLS, salaries)
    write(out_dir / "season_batting_official.csv", BAT_COLS, bats)
    write(out_dir / "season_pitching_official.csv", PIT_COLS, pits)
    write(out_dir / "team_rank_official.csv", RANK_COLS, ranks)
    return {"player": len(players), "player_season": len(ps), "player_salary": len(salaries),
            "season_batting_official": len(bats), "season_pitching_official": len(pits),
            "team_rank_official": len(ranks)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "load")
    args = ap.parse_args(argv)
    counts = build(args.data, args.out)
    for k, v in counts.items():
        print(f"{k:28s} {v:6d}행")
    return 0


if __name__ == "__main__":
    if __package__ in (None, ""):
        sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
