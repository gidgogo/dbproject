"""2-2 ① / 2-3  KBO 기록실 → 선수 목록(playerId 매핑표) + 시즌 기록

한 번의 수집으로 두 가지 결과를 만든다(같은 페이지를 두 번 받지 않으려고 합쳤다).
  data/player_season_team.csv   season, team_id, player_id, name, is_batter, is_pitcher
                                → 배인표 전처리용 "이름+팀+시즌 → playerId" 매핑표
  data/season_batting.csv       기록실 타자 시즌 기록 (Basic1 + Basic2)
  data/season_pitching.csv      기록실 투수 시즌 기록 (Basic1 + Basic2)

수집 단위 = (시즌, 팀, 타자/투수, 페이지종류). 끝난 단위는 data/raw/kbo/records/_done.json 에
기록되므로 중간에 끊겨도 같은 명령을 다시 실행하면 이어서 받는다.

규정타석 문제: 기록실은 타율(기본 정렬) 순으로 볼 때 규정타석 이상인 선수만 보여 준다.
경기 수(GAME_CN)로 정렬하면 전체 선수가 나온다(공개 크롤러 kbo-data-portal 근거,
❓ crawl/probe_kbo.py 결과로 확인).

사용 예 (레포 최상위 폴더, 맥 venv에서):
    python crawl/kbo_records.py --seasons 2025 --teams OB        # 프로토타입: 2025 두산만
    python crawl/kbo_records.py --seasons 2025                   # 2025 전체 팀
    python crawl/kbo_records.py --seasons 2021-2024 --pages basic1   # ID만 빨리
    python crawl/kbo_records.py --merge-only                      # 받은 원본으로 결과 CSV만 다시 만들기
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.aspnet import PostbackClient, form_fields, find_name, select_options  # noqa: E402
from crawl.common import (DATA, RAW, Checkpoint, PoliteSession, log, read_csv, save_text,  # noqa: E402
                          season_list, setup_logging, upsert_csv, write_csv)
from crawl.kbo_parsers import (HITTER_COLUMNS, PITCHER_COLUMNS, ip_to_outs, pager_pages,  # noqa: E402
                               parse_record_table, to_number)
from etl.reference import Reference  # noqa: E402

BASE = "https://www.koreabaseball.com"
PAGES = {
    "hitter": {"basic1": "/Record/Player/HitterBasic/Basic1.aspx",
               "basic2": "/Record/Player/HitterBasic/Basic2.aspx"},
    "pitcher": {"basic1": "/Record/Player/PitcherBasic/Basic1.aspx",
                "basic2": "/Record/Player/PitcherBasic/Basic2.aspx"},
}
SORT_COLUMN = "GAME_CN"
OUT_DIR = RAW / "kbo" / "records"
MAX_PAGES = 40

PST_COLS = ["season", "team_id", "player_id", "name", "is_batter", "is_pitcher"]
BAT_COLS = ["season", "team_id", "player_id", "name", "games", "plate_appearances", "at_bats", "runs", "hits",
            "doubles", "triples", "home_runs", "total_bases", "rbi", "sac_bunts", "sac_flies", "walks",
            "intentional_walks", "hbp", "strikeouts", "gidp", "avg", "obp", "slg", "ops", "multi_hits",
            "risp_avg", "pinch_hit_avg", "crawled_at"]
PIT_COLS = ["season", "team_id", "player_id", "name", "games", "wins", "losses", "saves", "holds", "win_pct",
            "ip_text", "outs_recorded", "hits_allowed", "home_runs_allowed", "walks", "hbp", "strikeouts",
            "runs_allowed", "earned_runs", "batters_faced", "pitches", "complete_games", "shutouts",
            "quality_starts", "blown_saves", "era", "whip", "opp_avg", "wild_pitches", "balks", "crawled_at"]
UNIT_COLS = ["season", "team_id", "player_id", "name", "team_name", "detail_kind", "crawled_at",
             *sorted(set(HITTER_COLUMNS.values()) | set(PITCHER_COLUMNS.values()) - {"name", "team_name"})]


def team_options(html: str, ref: Reference, season: int) -> list[tuple[str, str]]:
    """팀 select → [(option value, 팀코드)] ('전체'는 제외)"""
    out = []
    for value, text in select_options(html, "ddlTeam$ddlTeam"):
        if not value or text in ("전체", "팀 선택"):
            continue
        code = value if value in ref.team_ids else ref.team_id(text, season)
        if code:
            out.append((value, code))
        else:
            log.warning("팀 옵션 해석 실패: value=%s text=%s", value, text)
    return out


def sort_by_games(client: PostbackClient) -> bool:
    fields = form_fields(client.html)
    if not find_name(fields, "hfOrderByCol"):
        log.warning("정렬용 hidden 필드(hfOrderByCol)가 없음 → 기본 정렬 유지 (규정타석 선수만 나올 수 있음 ❓)")
        return False
    client.postback("lbtnOrderBy", {"hfOrderByCol": SORT_COLUMN, "hfOrderBy": "DESC"})
    return True


def collect_pages(client: PostbackClient, colmap: dict, raw_prefix: Path) -> list[dict]:
    """현재 화면(1페이지)부터 마지막 페이지까지 행을 모은다."""
    rows, seen_ids, page = [], set(), 1
    while page <= MAX_PAGES:
        save_text(raw_prefix.with_name(f"{raw_prefix.name}_p{page}.html"), client.html)
        _, page_rows = parse_record_table(client.html, colmap)
        new = [r for r in page_rows if r["player_id"] not in seen_ids]
        if not new:
            break
        rows += new
        seen_ids |= {r["player_id"] for r in new}
        nxt = page + 1
        if nxt in pager_pages(client.html):
            client.postback(f"ucPager$btnNo{nxt}")
        elif find_name(form_fields(client.html), "hfPage") and len(page_rows) >= 20:
            client.postback("lbtnOrderBy", {"hfPage": str(nxt), "hfOrderByCol": SORT_COLUMN, "hfOrderBy": "DESC"})
        else:
            break
        page = nxt
    return rows


def crawl(seasons: list[int], teams_filter: list[str] | None, kinds: list[str], pages: list[str],
          ref: Reference) -> None:
    session = PoliteSession(BASE)
    ckpt = Checkpoint(OUT_DIR / "_done.json")
    for season in seasons:
        for kind in kinds:
            colmap = HITTER_COLUMNS if kind == "hitter" else PITCHER_COLUMNS
            for page_name in pages:
                path = PAGES[kind][page_name]
                client = PostbackClient(session, path)
                client.get()
                season_values = {"ddlSeason$ddlSeason": str(season)}
                if find_name(form_fields(client.html), "ddlSeries$ddlSeries"):
                    season_values["ddlSeries$ddlSeries"] = "0"  # 정규시즌
                client.postback("ddlSeason$ddlSeason", season_values)
                if teams_filter == ["ALL"]:
                    units = [("", "ALL")]
                else:
                    units = [(v, c) for v, c in team_options(client.html, ref, season)
                             if not teams_filter or c in teams_filter]
                    if not units:
                        log.error("%s %s: 팀 목록을 찾지 못함", season, path)
                for value, code in units:
                    key = f"{season}|{code}|{kind}|{page_name}"
                    if key in ckpt:
                        continue
                    log.info("수집: %s", key)
                    client.postback("ddlTeam$ddlTeam", {"ddlSeason$ddlSeason": str(season),
                                                        "ddlTeam$ddlTeam": value})
                    sort_by_games(client)
                    raw_prefix = OUT_DIR / str(season) / f"{code}_{kind}_{page_name}"
                    rows = collect_pages(client, colmap, raw_prefix)
                    now = datetime.now().isoformat(timespec="seconds")
                    for r in rows:
                        r.update(season=season, crawled_at=now,
                                 team_id=code if code != "ALL" else ref.team_id(r.get("team_name"), season))
                        if code != "ALL" and ref.team_id(r.get("team_name"), season) not in (None, code):
                            log.warning("팀 불일치: %s 필터인데 %s(%s)", code, r.get("name"), r.get("team_name"))
                    write_csv(raw_prefix.with_suffix(".csv"), rows, UNIT_COLS)
                    ckpt.mark(key)
                    log.info("  → %d명 (요청 누계 %d)", len(rows), session.count)


def merge() -> dict[str, int]:
    """단위별 CSV → data/player_season_team.csv, season_batting.csv, season_pitching.csv"""
    merged: dict[str, dict[tuple, dict]] = {"hitter": {}, "pitcher": {}}
    for csv_path in sorted(OUT_DIR.glob("*/*.csv")):
        kind = "pitcher" if "_pitcher_" in csv_path.name else "hitter"
        for r in read_csv(csv_path):
            key = (r["season"], r["team_id"], r["player_id"])
            merged[kind].setdefault(key, {}).update({k: v for k, v in r.items() if v != ""})

    pst: dict[tuple, dict] = defaultdict(dict)
    for kind, flag in (("hitter", "is_batter"), ("pitcher", "is_pitcher")):
        for (season, team, pid), r in merged[kind].items():
            row = pst[(season, team, pid)]
            row.update(season=season, team_id=team, player_id=pid, name=r.get("name", ""))
            row.setdefault("is_batter", 0)
            row.setdefault("is_pitcher", 0)
            row[flag] = 1

    bat_rows = []
    for r in merged["hitter"].values():
        out = {k: r.get(k) for k in BAT_COLS}
        for k in BAT_COLS[4:-1]:
            out[k] = to_number(r.get(k))
        bat_rows.append(out)
    pit_rows = []
    for r in merged["pitcher"].values():
        out = {k: r.get(k) for k in PIT_COLS}
        for k in PIT_COLS[4:-1]:
            if k != "ip_text":
                out[k] = to_number(r.get(k))
        out["outs_recorded"] = ip_to_outs(r.get("ip_text"))
        pit_rows.append(out)

    key = ("season", "team_id", "player_id")
    return {
        "player_season_team": upsert_csv(DATA / "player_season_team.csv", list(pst.values()), key, PST_COLS),
        "season_batting": upsert_csv(DATA / "season_batting.csv", bat_rows, key, BAT_COLS),
        "season_pitching": upsert_csv(DATA / "season_pitching.csv", pit_rows, key, PIT_COLS),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", default="2025", help="예: 2025 / 2021-2025 / 2023,2025")
    ap.add_argument("--teams", default="", help="팀코드 쉼표 구분(OB,LG). ALL = 팀 구분 없이 리그 전체")
    ap.add_argument("--kinds", default="hitter,pitcher")
    ap.add_argument("--pages", default="basic1,basic2", help="basic1만 받으면 playerId 목록과 기본 기록")
    ap.add_argument("--merge-only", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    setup_logging(args.verbose)
    if not args.merge_only:
        teams = [t.strip() for t in args.teams.split(",") if t.strip()] or None
        crawl(season_list(args.seasons), teams, args.kinds.split(","), args.pages.split(","), Reference.load())
    for name, n in merge().items():
        log.info("%-20s %6d행 → data/%s.csv", name, n, name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
