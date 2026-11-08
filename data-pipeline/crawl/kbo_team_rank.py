"""2-3  KBO 팀 순위 (기준일별) → data/team_rank.csv

페이지: /Record/TeamRank/TeamRankDaily.aspx (날짜 선택 = hfSearchDate + '조회' 버튼)
근거: 공개 크롤러 icedo724/kbo-bayes (fetch_team_standings). ❓ probe 로 확인.

기준일을 안 주면 그 시즌 마지막 경기일을 쓴다.
  1) data/load/match.csv (kbodata 변환 결과)에 그 시즌 경기가 있으면 마지막 경기일
  2) 없으면 10월 31일 (페이지가 그 날짜 기준 순위를 보여 주는지 ❓ 확인 필요)

사용 예:
    python crawl/kbo_team_rank.py --seasons 2025
    python crawl/kbo_team_rank.py --dates 2025-06-01,2025-07-01
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.aspnet import PostbackClient, form_fields, find_name  # noqa: E402
from crawl.common import DATA, RAW, PoliteSession, log, read_csv, save_text, season_list, setup_logging, upsert_csv  # noqa: E402,E501
from crawl.kbo_parsers import parse_team_rank, to_number  # noqa: E402
from etl.reference import Reference  # noqa: E402

BASE = "https://www.koreabaseball.com"
PATH = "/Record/TeamRank/TeamRankDaily.aspx"
COLS = ["season", "as_of_date", "rank", "team_id", "team_name", "games", "wins", "losses", "draws", "win_pct",
        "games_behind", "last10", "streak", "home_record", "away_record", "crawled_at"]


def last_game_date(season: int) -> date:
    dates = [r["match_date"] for r in read_csv(DATA / "load" / "match.csv") if r["match_date"].startswith(str(season))]
    return date.fromisoformat(max(dates)) if dates else date(season, 10, 31)


def validate_rank(rows: list[dict], season: int, ref: Reference) -> None:
    expected = ref.teams_for_season(season)
    teams = [r["team_id"] for r in rows]
    if not expected or set(teams) != expected or len(teams) != len(expected):
        raise ValueError(f"{season} 순위표 팀 누락·중복·기준 정보 없음: 예상 {sorted(expected)}, 실제 {teams}")
    for row in rows:
        for field in ("rank", "games", "wins", "losses", "draws"):
            value = row.get(field)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{row['team_id']}: 필수 정수 {field} 누락/오류")
        if not 1 <= row["rank"] <= len(expected):
            raise ValueError(f"{row['team_id']}: 순위 범위 오류")
        if row["wins"] + row["losses"] + row["draws"] != row["games"]:
            raise ValueError(f"{row['team_id']}: 경기 수와 승패무 합계 불일치")
        rate, gb = row.get("win_pct"), row.get("games_behind")
        if (rate is None and row["wins"] + row["losses"] > 0
                or rate is not None and not 0 <= rate <= 1 or gb is None or not gb >= 0):
            raise ValueError(f"{row['team_id']}: 승률/게임차 누락 또는 범위 오류")


def fetch(session: PoliteSession, d: date, ref: Reference) -> list[dict]:
    client = PostbackClient(session, PATH)
    client.get()
    ymd = d.strftime("%Y%m%d")
    # 달력 '조회'는 submit 버튼 → __EVENTTARGET 비우고 버튼 이름=값을 함께 보낸다
    extra = {"btnCalendarSelect": ""} if find_name(client.html, "btnCalendarSelect") else None
    html = client.postback(None, {"hfSearchDate": ymd}, extra=extra)
    save_text(RAW / "kbo" / "team_rank" / f"{ymd}.html", html)
    shown = form_fields(html).get(find_name(form_fields(html), "hfSearchDate") or "", "")
    if shown != ymd:
        raise ValueError(f"요청 기준일 {ymd} 확인 실패: {shown!r}")
    as_of = d
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    rows = []
    for r in parse_team_rank(html):
        team_id = ref.team_id(r.get("team_name"), as_of.year)
        if not team_id:
            raise ValueError(f"팀명 해석 실패: {r.get('team_name')}")
        gb = r.get("games_behind", "")
        rows.append({**r, "season": as_of.year, "as_of_date": as_of.isoformat(), "team_id": team_id,
                     "rank": to_number(r.get("rank")), "games": to_number(r.get("games")),
                     "wins": to_number(r.get("wins")), "losses": to_number(r.get("losses")),
                     "draws": to_number(r.get("draws")), "win_pct": to_number(r.get("win_pct")),
                     "games_behind": 0.0 if gb in ("", "-", "0") else to_number(gb), "crawled_at": now})
    validate_rank(rows, as_of.year, ref)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", default="", help="시즌 마지막 기준일 순위 (예: 2021-2025)")
    ap.add_argument("--dates", default="", help="기준일 직접 지정 (YYYY-MM-DD, 쉼표 구분)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    setup_logging(args.verbose)
    days = [date.fromisoformat(x.strip()) for x in args.dates.split(",") if x.strip()]
    days += [last_game_date(s) for s in season_list(args.seasons)] if args.seasons else []
    if not days:
        ap.error("--seasons 또는 --dates 가 필요합니다")
    ref, session, all_rows = Reference.load(), PoliteSession(BASE), []
    try:
        for d in days:
            rows = fetch(session, d, ref)
            log.info("%s 기준 %d개 팀", d, len(rows))
            all_rows += rows
    except (RuntimeError, ValueError, KeyError, requests.RequestException) as exc:
        log.error("순위 수집 미완료: %s (기존 CSV 보존)", exc)
        return 1
    n = upsert_csv(DATA / "team_rank.csv", all_rows, ("season", "as_of_date", "team_id"), COLS)
    log.info("data/team_rank.csv 총 %d행", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
