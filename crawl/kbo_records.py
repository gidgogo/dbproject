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
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.aspnet import PostbackClient, form_fields, find_name, select_options, selected_value  # noqa: E402
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
             *sorted((set(HITTER_COLUMNS.values()) | set(PITCHER_COLUMNS.values())) - {"name", "team_name"})]


def select_regular_season(client: PostbackClient, season: int) -> None:
    """시리즈를 먼저 바꾼다. 한국시리즈 상태에서 Basic2 연도를 먼저 바꾸면 KBO가 에러를 반환한다."""
    if find_name(form_fields(client.html), "ddlSeries$ddlSeries"):
        if selected_value(client.html, "ddlSeries$ddlSeries") != "0":
            client.postback("ddlSeries$ddlSeries", {"ddlSeries$ddlSeries": "0"})
    client.postback("ddlSeason$ddlSeason", {"ddlSeason$ddlSeason": str(season)})
    if selected_value(client.html, "ddlSeason$ddlSeason") != str(season):
        raise RuntimeError(f"요청 시즌 {season}이 선택되지 않았습니다")
    if selected_value(client.html, "ddlSeries$ddlSeries") not in (None, "0"):
        raise RuntimeError("정규시즌 선택이 유지되지 않았습니다")


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
    overrides = {"hfOrderByCol": SORT_COLUMN, "hfOrderBy": "DESC"}
    # 팀을 바꾸어도 이전 팀의 마지막 페이지가 hidden 필드에 남는다.
    if find_name(fields, "hfPage"):
        overrides["hfPage"] = "1"
    client.postback("lbtnOrderBy", overrides)
    return True


def collect_pages(client: PostbackClient, colmap: dict, raw_prefix: Path) -> list[dict]:
    """현재 화면(1페이지)부터 마지막 페이지까지 행을 모은다."""
    rows, seen_ids, page = [], set(), 1
    advertised_page = False
    while page <= MAX_PAGES:
        save_text(raw_prefix.with_name(f"{raw_prefix.name}_p{page}.html"), client.html)
        headers, page_rows = parse_record_table(client.html, colmap)
        if "선수명" not in headers:
            raise RuntimeError(f"{raw_prefix}: {page}페이지에 선수 기록 표가 없습니다")
        new = [r for r in page_rows if r["player_id"] not in seen_ids]
        if not new:
            if page > 1 and advertised_page:
                raise RuntimeError(f"{raw_prefix}: 안내된 {page}페이지에 새 선수 행이 없습니다")
            if page == 1 and "기록이 없습니다" not in client.html:
                raise RuntimeError(f"{raw_prefix}: 첫 페이지에서 선수 행을 읽지 못했습니다")
            if page_rows:
                raise RuntimeError(f"{raw_prefix}: {page}페이지에 이전 선수만 반복됩니다")
            break
        rows += new
        seen_ids |= {r["player_id"] for r in new}
        nxt = page + 1
        advertised_page = nxt in pager_pages(client.html)
        if advertised_page:
            client.postback(f"ucPager$btnNo{nxt}")
        elif find_name(form_fields(client.html), "hfPage") and len(page_rows) >= 20:
            client.postback("lbtnOrderBy", {"hfPage": str(nxt), "hfOrderByCol": SORT_COLUMN, "hfOrderBy": "DESC"})
        else:
            break
        page = nxt
    else:
        raise RuntimeError(f"{raw_prefix}: 최대 페이지 수 {MAX_PAGES} 초과 (완료 처리하지 않음)")
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
                select_regular_season(client, season)
                if teams_filter == ["ALL"]:
                    units = [("", "ALL")]
                else:
                    units = [(v, c) for v, c in team_options(client.html, ref, season)
                             if not teams_filter or c in teams_filter]
                    if not units:
                        raise RuntimeError(f"{season} {path}: 요청한 팀 목록을 찾지 못함")
                for value, code in units:
                    key = f"{season}|{code}|{kind}|{page_name}"
                    if key in ckpt:
                        continue
                    log.info("수집: %s", key)
                    raw_prefix = OUT_DIR / str(season) / f"{code}_{kind}_{page_name}"
                    for attempt in range(3):
                        try:
                            if attempt:
                                client = PostbackClient(session, path)
                                client.get()
                                select_regular_season(client, season)
                            client.postback("ddlTeam$ddlTeam", {"ddlSeason$ddlSeason": str(season),
                                                                "ddlTeam$ddlTeam": value})
                            if not sort_by_games(client):
                                raise RuntimeError("전체 선수 조회를 위한 경기수 정렬 실패")
                            if (selected_value(client.html, "ddlSeason$ddlSeason") != str(season)
                                    or selected_value(client.html, "ddlTeam$ddlTeam") != value):
                                raise RuntimeError("요청한 시즌·팀 선택이 유지되지 않았습니다")
                            rows = collect_pages(client, colmap, raw_prefix)
                            if not rows and "기록이 없습니다" not in client.html:
                                raise RuntimeError("빈 수집 결과를 완료 처리할 수 없습니다")
                            break
                        except (RuntimeError, KeyError) as exc:
                            if attempt == 2:
                                raise
                            log.warning("%s: %s → 새 폼에서 재시도 (%d/3)", key, exc, attempt + 2)
                    now = datetime.now().isoformat(timespec="seconds")
                    for r in rows:
                        r.update(season=season, crawled_at=now,
                                 team_id=code if code != "ALL" else ref.team_id(r.get("team_name"), season))
                        if code != "ALL" and ref.team_id(r.get("team_name"), season) not in (None, code):
                            log.warning("팀 불일치: %s 필터인데 %s(%s)", code, r.get("name"), r.get("team_name"))
                    write_csv(raw_prefix.with_suffix(".csv"), rows, UNIT_COLS)
                    ckpt.mark(key)
                    log.info("  → %d명 (요청 누계 %d)", len(rows), session.count)


def merge(*, require_complete: bool = False) -> dict[str, int]:
    """ID 목록은 부분 수집도 반영하되 시즌 기록은 완료된 Basic1/2 쌍만 갱신한다."""
    ckpt = Checkpoint(OUT_DIR / "_done.json")
    units: dict[tuple[str, str, str], dict[str, list[dict]]] = defaultdict(dict)
    incomplete = []
    for path in sorted(OUT_DIR.glob("*/*.csv")):
        match = re.fullmatch(r"([A-Z]{2}|ALL)_(hitter|pitcher)_(basic[12])", path.stem)
        if not match:
            continue
        team, kind, page = match.groups()
        season = path.parent.name
        if f"{season}|{team}|{kind}|{page}" not in ckpt:
            incomplete.append(f"{season}/{team}/{kind}/{page}: 완료 표시 없음")
            continue
        rows = read_csv(path)
        keys = [(r.get("team_id"), r.get("player_id")) for r in rows]
        if (len(keys) != len(set(keys)) or any(not all(k) for k in keys)
                or any(r.get("season") != season or (team != "ALL" and r.get("team_id") != team)
                       for r in rows)):
            raise RuntimeError(f"{path}: 중복·빈 키 또는 시즌/팀 불일치")
        units[(season, team, kind)][page] = rows

    if require_complete and not units:
        raise RuntimeError("병합할 완료 단위 CSV가 없습니다")

    # 부분 수집에서 기존 타자/투수 역할을 false로 되돌리지 않는다.
    pst = {(r["season"], r["team_id"], r["player_id"]): r
           for r in read_csv(DATA / "player_season_team.csv")}
    complete: dict[str, dict[tuple, dict]] = {"hitter": {}, "pitcher": {}}
    for (season, team, kind), pages in units.items():
        for rows in pages.values():
            for r in rows:
                key = (season, r["team_id"], r["player_id"])
                current = pst.setdefault(key, dict(season=season, team_id=r["team_id"],
                                                   player_id=r["player_id"], is_batter=0, is_pitcher=0))
                current.update(name=r.get("name", ""))
                current["is_batter" if kind == "hitter" else "is_pitcher"] = 1
        if set(pages) != {"basic1", "basic2"}:
            incomplete.append(f"{season}/{team}/{kind}: Basic1/2 중 일부만 완료")
            continue
        one, two = ({(r["team_id"], r["player_id"]): r for r in pages[p]}
                    for p in ("basic1", "basic2"))
        if one.keys() != two.keys():
            incomplete.append(f"{season}/{team}/{kind}: Basic1/2 선수 목록 불일치")
            continue
        combined = []
        for key in one:
            left, right = one[key], two[key]
            shared = {k for k in left.keys() & right.keys()
                      if k not in {"crawled_at", "detail_kind"} and left[k] != "" and right[k] != ""}
            if any(left[k] != right[k] for k in shared):
                incomplete.append(f"{season}/{team}/{kind}: Basic1/2 공통 값 불일치")
                break
            combined.append({**left, **{k: v for k, v in right.items() if v != ""}})
        else:
            for r in combined:
                complete[kind][(season, r["team_id"], r["player_id"])] = r

    bat_rows, pit_rows = [], []
    for kind, cols, output in (("hitter", BAT_COLS, bat_rows), ("pitcher", PIT_COLS, pit_rows)):
        for r in complete[kind].values():
            out = {k: r.get(k) for k in cols}
            for k in cols[4:-1]:
                if k != "ip_text":
                    out[k] = to_number(r.get(k))
            if kind == "pitcher":
                out["outs_recorded"] = ip_to_outs(r.get("ip_text"))
            output.append(out)

    key = ("season", "team_id", "player_id")
    counts = {
        "player_season_team": upsert_csv(DATA / "player_season_team.csv", list(pst.values()), key, PST_COLS),
        "season_batting": upsert_csv(DATA / "season_batting.csv", bat_rows, key, BAT_COLS),
        "season_pitching": upsert_csv(DATA / "season_pitching.csv", pit_rows, key, PIT_COLS),
    }
    if incomplete:
        message = "시즌 기록 갱신 보류: " + "; ".join(incomplete)
        if require_complete:
            raise RuntimeError(message)
        log.warning(message)
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", default="2025", help="예: 2025 / 2021-2025 / 2023,2025")
    ap.add_argument("--teams", default="", help="팀코드 쉼표 구분(OB,LG). ALL = 팀 구분 없이 리그 전체")
    ap.add_argument("--kinds", default="hitter,pitcher")
    ap.add_argument("--pages", default="basic1,basic2", help="basic1만 받으면 ID 목록만 갱신; 시즌 기록은 Basic1/2 완료 후 갱신")
    ap.add_argument("--merge-only", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    setup_logging(args.verbose)
    status = 0
    try:
        if not args.merge_only:
            teams = [t.strip() for t in args.teams.split(",") if t.strip()] or None
            crawl(season_list(args.seasons), teams, args.kinds.split(","), args.pages.split(","), Reference.load())
    except (RuntimeError, KeyError, requests.RequestException) as exc:
        log.error("수집 미완료: %s (성공한 단위는 보존, 같은 명령으로 재시도)", exc)
        status = 1
    finally:
        try:
            counts = merge(require_complete=set(args.pages.split(",")) == {"basic1", "basic2"})
            for name, n in counts.items():
                log.info("%-20s %6d행 → data/%s.csv", name, n, name)
        except (RuntimeError, KeyError) as exc:
            log.error("병합 미완료: %s", exc)
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
