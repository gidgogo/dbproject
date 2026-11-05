"""2-2 ②  KBO 선수 상세 페이지 → 선수 마스터 (data/players.csv)

입력: data/player_season_team.csv (crawl/kbo_records.py 결과)의 playerId
페이지:
  현역 타자  /Record/Player/HitterDetail/Basic.aspx?playerId=
  현역 투수  /Record/Player/PitcherDetail/Basic.aspx?playerId=
  은퇴 선수  /Record/Retire/Hitter.aspx?playerId=, /Record/Retire/Pitcher.aspx?playerId=
             (현역 페이지에 프로필이 없으면 차례로 시도)
받는 항목: 이름, 등번호, 생년월일, 포지션, 투타, 신장·체중, 경력(출신교), 입단 계약금, 연봉,
           지명 순위, 입단년도, 현재 소속팀

연봉·등번호는 "지금" 값만 보인다 → --salary-season 으로 몇 시즌 값인지 기록한다
(기본: 3월 이후면 올해, 1~2월이면 작년).

이어받기: 이미 data/players.csv 에 있는 선수는 건너뛴다(--refresh 로 다시 받기).
20명마다 결과를 저장하므로 중간에 끊겨도 받은 만큼은 남는다.

사용 예:
    python crawl/kbo_profiles.py --seasons 2025 --limit 20     # 샘플 20명
    python crawl/kbo_profiles.py --seasons 2025                # 2025 시즌 선수 전원
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.common import DATA, RAW, PoliteSession, log, read_csv, save_text, season_list, setup_logging, upsert_csv  # noqa: E402,E501
from crawl.kbo_parsers import parse_profile  # noqa: E402
from etl.reference import Reference  # noqa: E402

BASE = "https://www.koreabaseball.com"
URLS = {
    "hitter": "/Record/Player/HitterDetail/Basic.aspx?playerId={}",
    "pitcher": "/Record/Player/PitcherDetail/Basic.aspx?playerId={}",
    "retire_hitter": "/Record/Retire/Hitter.aspx?playerId={}",
    "retire_pitcher": "/Record/Retire/Pitcher.aspx?playerId={}",
}
COLS = ["player_id", "player_name", "uniform_no", "birth_date", "position", "position_text", "throws", "bats",
        "height_cm", "weight_kg", "career", "signing_bonus_text", "signing_bonus_10k", "salary_season",
        "salary_text", "salary_10k_krw", "salary_usd", "draft_info", "draft_year", "join_info", "join_year",
        "team_name", "team_id", "is_retired", "source_url", "crawled_at"]
OUT = DATA / "players.csv"
RAW_DIR = RAW / "kbo" / "profiles"


def default_salary_season(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 3 else today.year - 1


def targets(seasons: list[int] | None) -> list[tuple[int, str]]:
    """(player_id, 'hitter'|'pitcher') — 투수 목록에만 있으면 투수 페이지부터"""
    kinds: dict[int, set[str]] = {}
    for r in read_csv(DATA / "player_season_team.csv"):
        if seasons and int(r["season"]) not in seasons:
            continue
        k = kinds.setdefault(int(r["player_id"]), set())
        if r.get("is_batter") in ("1", "true", "True"):
            k.add("hitter")
        if r.get("is_pitcher") in ("1", "true", "True"):
            k.add("pitcher")
    return [(pid, "pitcher" if k == {"pitcher"} else "hitter") for pid, k in sorted(kinds.items())]


def fetch_one(session: PoliteSession, pid: int, kind: str) -> tuple[dict, str]:
    order = [kind, "pitcher" if kind == "hitter" else "hitter", f"retire_{kind}",
             "retire_pitcher" if kind == "hitter" else "retire_hitter"]
    for k in order:
        url = URLS[k].format(pid)
        html = session.get(url).text
        prof = parse_profile(html)
        if prof:
            save_text(RAW_DIR / f"{pid}.html", html)
            prof["is_retired"] = k.startswith("retire")
            return prof, url
    return {}, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", default="", help="이 시즌에 기록이 있는 선수만 (비우면 매핑표 전체)")
    ap.add_argument("--player-ids", default="", help="특정 선수만 (쉼표 구분)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true", help="이미 받은 선수도 다시 받기")
    ap.add_argument("--salary-season", type=int, default=default_salary_season())
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    setup_logging(args.verbose)

    ref = Reference.load()
    if args.player_ids:
        todo = [(int(x), "hitter") for x in args.player_ids.split(",") if x.strip()]
    else:
        todo = targets(season_list(args.seasons) if args.seasons else None)
    done = {int(r["player_id"]) for r in read_csv(OUT)} if not args.refresh else set()
    todo = [t for t in todo if t[0] not in done]
    if args.limit:
        todo = todo[: args.limit]
    log.info("받을 선수 %d명 (이미 받은 %d명 건너뜀)", len(todo), len(done))

    session = PoliteSession(BASE)
    buf, failed = [], []
    for i, (pid, kind) in enumerate(todo, 1):
        try:
            prof, url = fetch_one(session, pid, kind)
        except Exception as e:  # 한 명 실패로 전체를 멈추지 않는다
            log.warning("%s 실패: %s", pid, e)
            failed.append(pid)
            continue
        if not prof:
            log.warning("%s: 프로필을 찾지 못함", pid)
            failed.append(pid)
            continue
        prof.update(player_id=pid, salary_season=args.salary_season, source_url=BASE + url,
                    team_id=ref.team_id(prof.get("team_name"), args.salary_season) if prof.get("team_name") else None,
                    crawled_at=datetime.now().astimezone().isoformat(timespec="seconds"))
        buf.append(prof)
        if len(buf) >= 20 or i == len(todo):
            upsert_csv(OUT, buf, ("player_id",), COLS)
            log.info("%d/%d 저장 (요청 누계 %d)", i, len(todo), session.count)
            buf = []
    if buf:
        upsert_csv(OUT, buf, ("player_id",), COLS)
    if failed:
        save_text(RAW_DIR / "_failed.txt", "\n".join(map(str, failed)) + "\n")
        log.warning("실패 %d명 → %s", len(failed), RAW_DIR / "_failed.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
