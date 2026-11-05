"""2-4  네이버 문자중계 투구 데이터 수집 → data/pitches_<시즌>_<팀>.csv

1) 시즌 일정을 받아 그 팀의 정규시즌 완료 경기를 고른다      (data/raw/naver/<시즌>/schedule.json)
2) 경기마다 1회~마지막 이닝 중계 JSON을 받는다                 (data/raw/naver/<시즌>/games/<gameId>.json)
   - 모든 이닝을 받은 뒤에 파일을 쓰므로, 끊기면 그 경기만 다시 받는다(이어받기)
   - 요청 사이 1~2초 → 한 팀 144경기 ≈ 1,400요청 ≈ 35~45분
3) 투구 단위로 펼쳐 KBO playerId·우리 game_id를 붙여 CSV로 저장
   - 네이버 pcode가 KBO playerId와 같으면 그대로(근거: 공개 코드 주석 'KBO 숫자 pcode', ❓ 확인 필요)
   - 아니면 이름+팀+시즌으로 매핑(etl/player_mapper.py), 실패는 리포트에 남김

사용 예:
    python crawl/naver_relay.py --season 2025 --team OB --max-games 3    # 시험
    python crawl/naver_relay.py --season 2025 --team OB                  # 한 팀 시즌 전체
    python crawl/naver_relay.py --season 2025 --team OB --parse-only     # 받은 원본으로 CSV만 다시
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.common import DATA, RAW, PoliteSession, log, save_text, setup_logging, write_csv  # noqa: E402
from crawl.naver_parsers import final_inning, lineup_names, our_game_id, pitch_rows, playable  # noqa: E402
from etl.player_mapper import PlayerMapper  # noqa: E402

API = "https://api-gw.sports.naver.com"
HEADERS = {"Origin": "https://m.sports.naver.com", "Referer": "https://m.sports.naver.com/",
           "Accept": "application/json, text/plain, */*"}
PAGE_SIZE = 500  # 1024 이상이면 10건만 오는 문제가 보고됨
COLS = ["game_id", "pitch_seq", "inning", "half", "at_bat_no", "pitch_no", "pitcher_id", "batter_id",
        "balls", "strikes", "outs", "pitch_type_ko", "speed_kmh", "pitch_result_code", "plate_x", "plate_z",
        "sz_top", "sz_bot", "batter_stance", "pa_result_text", "naver_pitch_id",
        # 아래는 확인용(DB에는 안 들어감)
        "naver_game_id", "pitcher_pcode", "pitcher_name", "batter_pcode", "batter_name", "description"]


def api_get(session: PoliteSession, path: str, **params) -> dict:
    r = session.get(API + path, params=params)
    body = r.json()
    if not body.get("success", True) or body.get("result") is None:
        raise RuntimeError(f"API 오류 {path}: {str(body)[:200]}")
    return body["result"]


def fetch_schedule(session: PoliteSession, season: int, refresh: bool = False) -> list[dict]:
    path = RAW / "naver" / str(season) / "schedule.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    games, page, total = [], 1, None
    while total is None or len(games) < total:
        res = api_get(session, "/schedule/games", fields="basic,schedule,baseball", upperCategoryId="kbaseball",
                      categoryId="kbo", fromDate=f"{season}-01-01", toDate=f"{season}-12-31", roundCodes="",
                      size=PAGE_SIZE, page=page)
        total = int(res.get("gameTotalCount") or 0)
        batch = res.get("games") or []
        if not batch:
            break
        games += batch
        page += 1
    save_text(path, json.dumps(games, ensure_ascii=False))
    log.info("%d 일정 %d경기 저장", season, len(games))
    return games


def game_file(season: int, naver_gid: str) -> Path:
    return RAW / "naver" / str(season) / "games" / f"{naver_gid}.json"


def fetch_game(session: PoliteSession, season: int, game: dict) -> dict[int, dict]:
    path = game_file(season, game["gameId"])
    if path.exists():
        return {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    innings = {}
    first = api_get(session, f"/schedule/games/{game['gameId']}/relay", inning=1)
    innings[1] = first.get("textRelayData") or {}
    # 마지막 이닝: 일정의 statusInfo('12회말') → 없으면 1회 응답의 inn(현재·마지막 이닝) → 없으면 9
    last = final_inning(game.get("statusInfo")) or int(innings[1].get("inn") or 9)
    for inn in range(2, last + 1):
        res = api_get(session, f"/schedule/games/{game['gameId']}/relay", inning=inn)
        innings[inn] = res.get("textRelayData") or {}
    save_text(path, json.dumps(innings, ensure_ascii=False))
    return innings


class IdResolver:
    """네이버 pcode → KBO playerId"""

    def __init__(self, season: int, mapper: PlayerMapper | None, known_ids: set[int]):
        self.season, self.mapper, self.known = season, mapper, known_ids
        self.methods: Counter = Counter()
        self.unmatched: dict[tuple, int] = Counter()

    def resolve(self, pcode: str, name: str, team: str, kind: str, date: str) -> int | None:
        if pcode.isdigit() and int(pcode) in self.known:
            self.methods["pcode"] += 1
            return int(pcode)
        if self.mapper:
            r = self.mapper.match(self.season, team, name, kind, date)
            if r.player_id:
                self.methods[f"name_{r.method}"] += 1
                return r.player_id
        self.methods["unmatched"] += 1
        self.unmatched[(pcode, name, team, kind)] += 1
        return None


def to_csv_rows(game: dict, innings: dict[int, dict], resolver: IdResolver) -> list[dict]:
    gid = our_game_id(game)
    names = lineup_names(innings)
    home, away = game.get("homeTeamCode"), game.get("awayTeamCode")
    date = str(game.get("gameDate", ""))[:10]
    out = []
    for r in pitch_rows(innings):
        bat_team = away if r["half"] == "T" else home
        pit_team = home if r["half"] == "T" else away
        pname, _ = names.get(r["pitcher_pcode"], ("", ""))
        bname, _ = names.get(r["batter_pcode"], ("", ""))
        out.append({**r, "game_id": gid, "naver_game_id": game["gameId"], "pitcher_name": pname, "batter_name": bname,
                    "pitcher_id": resolver.resolve(r["pitcher_pcode"], pname, pit_team, "pitcher", date),
                    "batter_id": resolver.resolve(r["batter_pcode"], bname, bat_team, "batter", date)})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--team", required=True, help="KBO 팀코드 (OB, LG, HT ...)")
    ap.add_argument("--max-games", type=int, default=0)
    ap.add_argument("--include-postseason", action="store_true")
    ap.add_argument("--parse-only", action="store_true", help="새로 받지 않고 받은 원본만 변환")
    ap.add_argument("--refresh-schedule", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    setup_logging(args.verbose)

    session = PoliteSession(headers=HEADERS)
    rounds = ("kbo_r", "kbo_ps_wd", "kbo_ps_sp", "kbo_ps_po", "kbo_ps_ks") if args.include_postseason else ("kbo_r",)
    sched_path = RAW / "naver" / str(args.season) / "schedule.json"
    if args.parse_only and sched_path.exists():
        schedule = json.loads(sched_path.read_text(encoding="utf-8"))
    else:
        schedule = fetch_schedule(session, args.season, args.refresh_schedule)
    games = sorted([g for g in schedule if playable(g, args.team, rounds)], key=lambda g: g["gameId"])
    if args.max_games:
        games = games[: args.max_games]
    log.info("%s %d시즌 대상 %d경기", args.team, args.season, len(games))

    pst = DATA / "player_season_team.csv"
    mapper = PlayerMapper.from_files(pst) if pst.exists() else None
    known = {cand.player_id for cands in (mapper.by_team.values() if mapper else []) for cand in cands}
    resolver = IdResolver(args.season, mapper, known)

    rows, failed = [], []
    for i, g in enumerate(games, 1):
        try:
            if args.parse_only and not game_file(args.season, g["gameId"]).exists():
                continue
            innings = fetch_game(session, args.season, g)
        except Exception as e:  # 한 경기 실패로 전체를 멈추지 않는다 → 다시 실행하면 그 경기만 재시도
            log.warning("%s 실패: %s", g["gameId"], e)
            failed.append(g["gameId"])
            continue
        rows += to_csv_rows(g, innings, resolver)
        if i % 10 == 0:
            log.info("%d/%d경기 (요청 누계 %d, 투구 %d)", i, len(games), session.count, len(rows))

    out = DATA / f"pitches_{args.season}_{args.team}.csv"
    write_csv(out, rows, COLS)
    report = [f"# 네이버 투구 수집 리포트 {args.season} {args.team}", "",
              f"- 경기 {len(games)} (실패 {len(failed)}), 투구 {len(rows)}",
              f"- 좌표(plate_x) 있는 투구: {sum(1 for r in rows if r['plate_x'] is not None)}",
              f"- 구속 있는 투구: {sum(1 for r in rows if r['speed_kmh'])}",
              "", "## 선수 매핑 방법", "", *[f"- {k}: {v}" for k, v in resolver.methods.most_common()],
              "", "## 매핑 실패 (pcode, 이름, 팀, 구분: 횟수)", "",
              *[f"- {k}: {v}" for k, v in resolver.unmatched.most_common(100)],
              "", "## 실패 경기 (다시 실행하면 재시도)", "", *[f"- {g}" for g in failed]]
    save_text(RAW / "naver" / str(args.season) / f"_report_{args.team}.md", "\n".join(report) + "\n")
    log.info("저장: %s (%d투구), 리포트: data/raw/naver/%d/_report_%s.md", out, len(rows), args.season, args.team)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
