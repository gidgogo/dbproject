"""2-3  KBO 팀 순위 (기준일별) → data/team_rank.csv

페이지: /Record/TeamRank/TeamRankDaily.aspx (날짜 선택 = hfSearchDate + '조회' 버튼)
근거: 공개 크롤러 icedo724/kbo-bayes (fetch_team_standings). ❓ probe 로 확인.

기준일을 안 주면 그 시즌 마지막 경기일을 쓴다.
  1) data/load/game.csv (kbodata 변환 결과)에 그 시즌 경기가 있으면 마지막 경기일
  2) 없으면 10월 31일 (페이지가 그 날짜 기준 순위를 보여 주는지 ❓ 확인 필요)

사용 예:
    python crawl/kbo_team_rank.py --seasons 2025
    python crawl/kbo_team_rank.py --dates 2025-06-01,2025-07-01
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

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
    dates = [r["game_date"] for r in read_csv(DATA / "load" / "game.csv") if r["game_date"].startswith(str(season))]
    return date.fromisoformat(max(dates)) if dates else date(season, 10, 31)


def fetch(session: PoliteSession, d: date, ref: Reference) -> list[dict]:
    client = PostbackClient(session, PATH)
    client.get()
    ymd = d.strftime("%Y%m%d")
    # 달력 '조회'는 submit 버튼 → __EVENTTARGET 비우고 버튼 이름=값을 함께 보낸다
    extra = {"btnCalendarSelect": ""} if find_name(client.html, "btnCalendarSelect") else None
    html = client.postback(None, {"hfSearchDate": ymd}, extra=extra)
    save_text(RAW / "kbo" / "team_rank" / f"{ymd}.html", html)
    shown = form_fields(html).get(find_name(form_fields(html), "hfSearchDate") or "", "")
    as_of = date(int(shown[:4]), int(shown[4:6]), int(shown[6:8])) if re.fullmatch(r"\d{8}", shown) else d
    if as_of != d:
        log.warning("요청 기준일 %s 대신 %s 기준 순위가 왔음", d, as_of)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    rows = []
    for r in parse_team_rank(html):
        team_id = ref.team_id(r.get("team_name"), as_of.year)
        if not team_id:
            log.warning("팀명 해석 실패: %s", r.get("team_name"))
            continue
        gb = r.get("games_behind", "")
        rows.append({**r, "season": as_of.year, "as_of_date": as_of.isoformat(), "team_id": team_id,
                     "rank": to_number(r.get("rank")), "games": to_number(r.get("games")),
                     "wins": to_number(r.get("wins")), "losses": to_number(r.get("losses")),
                     "draws": to_number(r.get("draws")), "win_pct": to_number(r.get("win_pct")),
                     "games_behind": 0.0 if gb in ("", "-", "0") else to_number(gb), "crawled_at": now})
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
    for d in days:
        rows = fetch(session, d, ref)
        log.info("%s 기준 %d개 팀", d, len(rows))
        all_rows += rows
    n = upsert_csv(DATA / "team_rank.csv", all_rows, ("season", "as_of_date", "team_id"), COLS)
    log.info("data/team_rank.csv 총 %d행", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
