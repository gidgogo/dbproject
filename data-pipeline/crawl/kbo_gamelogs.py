"""동명이인 구분용: 선수별 출전 일자 → data/player_game_dates.csv

같은 시즌·같은 팀에 같은 이름의 선수가 둘 이상이면 박스스코어 이름만으로는 누구인지 알 수 없다
(예: 같은 팀 투수 두 명이 같은 이름). 선수별 "일자별 기록" 페이지에서 출전 날짜를 받아 두면
etl/player_mapper.py 가 그 경기 날짜에 출전한 선수를 골라낸다(gamelog 단계).

페이지: /Record/Player/HitterDetail/Daily.aspx?playerId=  (투수는 PitcherDetail)
        연도는 ddlYear 포스트백 (근거: icedo724/kbo-bayes fetch_player_gamelog)

사용 예:
    # 변환 리포트의 '매칭 실패(ambiguous)' 후보만 받기
    python crawl/kbo_gamelogs.py --from-unmatched data/load/_unmatched_players.csv
    python crawl/kbo_gamelogs.py --player-ids 12345,23456 --season 2025 --kind pitcher
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.aspnet import PostbackClient, selected_value  # noqa: E402
from crawl.common import DATA, RAW, PoliteSession, log, read_csv, save_text, setup_logging, upsert_csv  # noqa: E402
from crawl.kbo_parsers import parse_gamelog_dates  # noqa: E402

BASE = "https://www.koreabaseball.com"
URLS = {"hitter": "/Record/Player/HitterDetail/Daily.aspx?playerId={}",
        "pitcher": "/Record/Player/PitcherDetail/Daily.aspx?playerId={}"}


def fetch_dates(session: PoliteSession, pid: int, season: int, kind: str) -> list[str]:
    client = PostbackClient(session, URLS[kind].format(pid))
    html = client.get()
    if selected_value(html, "ddlYear") not in (None, str(season)):
        html = client.postback("ddlYear", {"ddlYear": str(season)})
    save_text(RAW / "kbo" / "gamelogs" / f"{pid}_{season}_{kind}.html", html)
    return parse_gamelog_dates(html, season)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-unmatched", type=Path, help="etl 변환 리포트의 _unmatched_players.csv")
    ap.add_argument("--player-ids", default="")
    ap.add_argument("--season", type=int)
    ap.add_argument("--kind", default="hitter", choices=["hitter", "pitcher"])
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    setup_logging(args.verbose)

    jobs: set[tuple[int, int, str]] = set()
    if args.from_unmatched:
        for r in read_csv(args.from_unmatched):
            if r["reason"] == "ambiguous":
                kind = "pitcher" if r["kind"] == "pitcher" else "hitter"
                jobs |= {(int(c), int(r["season"]), kind) for c in r["candidates"].split()}
    if args.player_ids:
        if not args.season:
            ap.error("--player-ids 에는 --season 이 필요합니다")
        jobs |= {(int(x), args.season, args.kind) for x in args.player_ids.split(",") if x.strip()}
    if not jobs:
        log.info("받을 선수가 없습니다")
        return 0

    session, rows = PoliteSession(BASE), []
    for pid, season, kind in sorted(jobs):
        dates = fetch_dates(session, pid, season, kind)
        log.info("%s %s %s: %d경기", pid, season, kind, len(dates))
        rows += [{"player_id": pid, "game_date": d} for d in dates]
    n = upsert_csv(DATA / "player_game_dates.csv", rows, ("player_id", "game_date"), ["player_id", "game_date"])
    log.info("data/player_game_dates.csv 총 %d행", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
