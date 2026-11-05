"""kbodata 경기 JSON(raw.json) → DB 적재용 CSV (data/load/*.csv)

※ 참고 구현: kbodata 결과 정리·변환은 배인표 담당이다. 이 스크립트는 ERD가
  kbodata 데이터를 빠짐없이 담을 수 있는지 검증하려고 만든 것이고,
  배인표의 전처리 결과와 컬럼을 맞추는 기준(인터페이스)으로 쓰면 된다.

사용 예 (레포 최상위 폴더에서):
    python etl/kbodata_to_tables.py ~/Desktop/data/test/raw.json \\
        --players data/player_season_team.csv --out data/load

    # 매핑 검증만 (2-2 검증: 2025-06-01 타자 124명·투수 53명이 모두 1명으로 매칭되는지)
    python etl/kbodata_to_tables.py ~/Desktop/data/test/raw.json \\
        --players data/player_season_team.csv --check-only

결과:
    data/load/game.csv, team_game.csv, inning_score.csv, batter_game.csv,
    plate_appearance.csv, pitcher_game.csv, game_event.csv, game_umpire_stage.csv
    data/load/_kbodata_report.md       변환 요약·경고
    data/load/_unmatched_players.csv   선수ID를 못 찾은 이름 (+ 후보 ID)
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.kbodata_parse import (  # noqa: E402
    DECISION_TEXT, ETC_NON_EVENT_KEYS, duration_minutes, etc_items, is_raw_format,
    load_games, load_result_name_map, outs_from_kbodata_inning, outs_from_text_inning,
    parse_etc_item, parse_game_id, parse_hhmm, position_code, split_pa_codes,
    text_to_codes, to_int,
)
from etl.player_mapper import PlayerMapper  # noqa: E402
from etl.reference import Reference  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

COLUMNS = {
    "game": ["game_id", "game_date", "away_team_id", "home_team_id", "doubleheader_no", "series_id",
             "stadium_id", "attendance", "start_time", "end_time", "duration_min"],
    "team_game": ["game_id", "team_id", "home_away", "result", "runs", "hits", "errors", "walks_hbp"],
    "inning_score": ["game_id", "team_id", "inning", "runs"],
    "batter_game": ["game_id", "player_id", "team_id", "lineup_seq", "batting_order", "positions",
                    "at_bats", "hits", "rbi", "runs"],
    "plate_appearance": ["game_id", "player_id", "inning", "seq_in_inning", "result_code"],
    "pitcher_game": ["game_id", "player_id", "team_id", "appearance_seq", "decision", "outs_recorded",
                     "batters_faced", "at_bats", "pitches", "hits_allowed", "home_runs_allowed",
                     "walks_hbp", "strikeouts", "runs_allowed", "earned_runs"],
    "game_event": ["game_id", "event_type", "seq", "player_id", "team_id", "player_name_raw",
                   "inning", "detail", "raw_text"],
    "game_umpire_stage": ["game_id", "umpire_name", "listed_order"],
}


@dataclass
class Report:
    games: int = 0
    raw_format_games: int = 0
    warnings: list[str] = field(default_factory=list)
    match_methods: Counter = field(default_factory=Counter)
    unmatched: list[dict] = field(default_factory=list)
    decision_suspect_games: list[str] = field(default_factory=list)
    decision_counts: Counter = field(default_factory=Counter)
    unknown_places: Counter = field(default_factory=Counter)
    unknown_event_types: Counter = field(default_factory=Counter)
    batters_total: int = 0
    pitchers_total: int = 0

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


class Converter:
    def __init__(self, ref: Reference, mapper: PlayerMapper | None):
        self.ref = ref
        self.mapper = mapper
        self.rows: dict[str, list[dict]] = defaultdict(list)
        self.report = Report()
        self.name_map = load_result_name_map()

    # ------------------------------------------------------------------
    def convert(self, game: dict) -> None:
        gid = game["id"]
        c = game["contents"]
        gdate, away, home, dh = parse_game_id(gid)
        season = gdate.year
        raw = is_raw_format(game)
        self.report.games += 1
        self.report.raw_format_games += raw
        etc = c.get("ETC_info") or {}

        # 경기 ---------------------------------------------------------
        place = str(etc.get("구장", "")).strip()
        sid = self.ref.stadium_id(place, season)
        if place and sid is None:
            self.report.unknown_places[f"{place} ({season})"] += 1
        self.rows["game"].append({
            "game_id": gid, "game_date": gdate.isoformat(), "away_team_id": away, "home_team_id": home,
            "doubleheader_no": dh, "series_id": 0, "stadium_id": sid,
            "attendance": to_int(etc.get("관중"), None),
            "start_time": parse_hhmm(etc.get("개시")), "end_time": parse_hhmm(etc.get("종료")),
            "duration_min": duration_minutes(etc.get("경기시간")),
        })

        # 팀 경기 / 이닝 득점 -------------------------------------------
        board = c.get("scoreboard") or []
        if len(board) != 2:
            self.report.warn(f"{gid}: 스코어보드 행 수 {len(board)} (2가 아님) → 건너뜀")
            return
        team_result = {}
        for side, row, tid in (("A", board[0], away), ("H", board[1], home)):
            name = row.get("팀" if raw else "team")
            mapped = self.ref.team_id(name, season)
            if mapped and mapped != tid:
                self.report.warn(f"{gid}: 스코어보드 팀명 {name}→{mapped} 가 경기ID 팀 {tid} 와 다름")
            if raw:
                res = {"승": "W", "패": "L", "무": "D"}.get(str(row.get("승패", "")).strip())
                r, h, e, b = (to_int(row.get(k)) for k in ("R", "H", "E", "B"))
                inning_vals = {i: row.get(str(i)) for i in range(1, 19)}
            else:
                res = {1: "W", 0: "D", -1: "L"}.get(to_int(row.get("result"), None))
                r, h, e, b = (to_int(row.get(k)) for k in ("r", "h", "e", "b"))
                inning_vals = {i: row.get(f"i_{i}") for i in range(1, 19)}
            if res is None:
                self.report.warn(f"{gid}: {tid} 승패 값 해석 불가")
                res = "D"
            team_result[tid] = res
            self.rows["team_game"].append({"game_id": gid, "team_id": tid, "home_away": side, "result": res,
                                           "runs": r, "hits": h, "errors": e, "walks_hbp": b})
            for inn, v in inning_vals.items():
                runs = to_int(v, None)
                if runs is not None and str(v).strip() not in ("-", ""):
                    self.rows["inning_score"].append({"game_id": gid, "team_id": tid, "inning": inn, "runs": runs})

        # 타자 / 타석 -----------------------------------------------------
        name_to_ids: dict[str, set[tuple[int, str]]] = defaultdict(set)
        for key, tid in (("away_batter", away), ("home_batter", home)):
            for seq, row in enumerate(c.get(key) or [], start=1):
                self.report.batters_total += 1
                name = str(row.get("선수명" if raw else "name", "")).strip()
                pid = self._map(season, tid, name, "batter", gdate.isoformat(), gid)
                if pid is None:
                    continue
                name_to_ids[name].add((pid, tid))
                order = to_int(row.get("bat_order", row.get("타순")), None)
                self.rows["batter_game"].append({
                    "game_id": gid, "player_id": pid, "team_id": tid, "lineup_seq": seq,
                    "batting_order": order if order and 1 <= order <= 9 else None,
                    "positions": position_code(row.get("포지션" if raw else "position")),
                    "at_bats": to_int(row.get("타수" if raw else "bat_num")),
                    "hits": to_int(row.get("안타" if raw else "hit")),
                    "rbi": to_int(row.get("타점" if raw else "hit_get")),
                    "runs": to_int(row.get("득점" if raw else "own_get")),
                })
                for inn in range(1, 19):
                    cell = row.get(str(inn)) if raw else row.get(f"i_{inn}")
                    try:
                        codes = text_to_codes(cell, self.name_map) if raw else split_pa_codes(cell)
                    except ValueError as e:
                        self.report.warn(f"{gid} {name} {inn}회: {e}")
                        continue
                    for k, code in enumerate(codes, start=1):
                        if code not in self.ref.pa_codes:
                            self.report.warn(f"{gid} {name} {inn}회: 코드표에 없는 결과코드 {code}")
                            continue
                        self.rows["plate_appearance"].append({"game_id": gid, "player_id": pid, "inning": inn,
                                                              "seq_in_inning": k, "result_code": code})

        # 투수 -----------------------------------------------------------
        game_pitchers = []
        for key, tid in (("away_pitcher", away), ("home_pitcher", home)):
            for seq, row in enumerate(c.get(key) or [], start=1):
                self.report.pitchers_total += 1
                name = str(row.get("선수명" if raw else "name", "")).strip()
                if raw:
                    is_starter = str(row.get("등판", "")).strip() == "선발"
                    decision = DECISION_TEXT.get(str(row.get("결과", "")).strip())
                    outs = outs_from_text_inning(row.get("이닝"))
                    vals = {k: to_int(row.get(s)) for k, s in (
                        ("batters_faced", "타자"), ("at_bats", "타수"), ("pitches", "투구수"),
                        ("hits_allowed", "피안타"), ("home_runs_allowed", "홈런"), ("walks_hbp", "4사구"),
                        ("strikeouts", "삼진"), ("runs_allowed", "실점"), ("earned_runs", "자책"))}
                else:
                    is_starter = str(row.get("mound", "")).strip() in ("1", "1.0", "True", "true")
                    decision = str(row.get("result") or "").strip() or None
                    if decision not in ("W", "L", "S", "H"):
                        decision = None
                    try:
                        outs = outs_from_kbodata_inning(row.get("inning"))
                    except ValueError as e:
                        self.report.warn(f"{gid} {name}: {e}")
                        outs = 0
                    vals = {k: to_int(row.get(s)) for k, s in (
                        ("batters_faced", "batternum"), ("at_bats", "battednum"), ("pitches", "pitchnum"),
                        ("hits_allowed", "hitted"), ("home_runs_allowed", "homerun"), ("walks_hbp", "dead4ball"),
                        ("strikeouts", "strikeout"), ("runs_allowed", "losescore"), ("earned_runs", "earnedrun"))}
                if is_starter != (seq == 1):
                    self.report.warn(f"{gid} {tid} {name}: 선발 표시({is_starter})와 등판순서({seq})가 맞지 않음")
                pid = self._map(season, tid, name, "pitcher", gdate.isoformat(), gid)
                if pid is None:
                    continue
                name_to_ids[name].add((pid, tid))
                if vals["pitches"] == 0 and vals["batters_faced"] > 0:
                    vals["pitches"] = None  # 과거 경기 투구수 누락
                game_pitchers.append({"game_id": gid, "player_id": pid, "team_id": tid, "appearance_seq": seq,
                                      "decision": decision, "outs_recorded": outs, **vals})
        self._fix_decisions(gid, game_pitchers, team_result, trust=raw)
        self.rows["pitcher_game"].extend(game_pitchers)

        # 기타 기록 -------------------------------------------------------
        for etype, value in etc.items():
            if etype in ETC_NON_EVENT_KEYS:
                continue
            if etype not in self.ref.event_types:
                self.report.unknown_event_types[etype] += 1
                continue
            seq = 0
            for item in etc_items(value):
                parsed = parse_etc_item(item)
                ids = name_to_ids.get(parsed["name"], set())
                pid, tid = next(iter(ids)) if len(ids) == 1 else (None, None)
                for inn in (parsed["innings"] or [None]):
                    seq += 1
                    self.rows["game_event"].append({
                        "game_id": gid, "event_type": etype, "seq": seq, "player_id": pid, "team_id": tid,
                        "player_name_raw": parsed["name"][:30], "inning": inn,
                        "detail": (parsed["detail"] or None) and parsed["detail"][:100], "raw_text": item[:200]})

        # 심판 -----------------------------------------------------------
        umps = etc.get("심판") or []
        if isinstance(umps, str):
            umps = umps.split()
        for i, u in enumerate([u for u in umps if str(u).strip()][:6], start=1):
            self.rows["game_umpire_stage"].append({"game_id": gid, "umpire_name": str(u).strip(), "listed_order": i})

    # ------------------------------------------------------------------
    def _map(self, season: int, team_id: str, name: str, kind: str, game_date: str, gid: str) -> int | None:
        if self.mapper is None:
            return None
        res = self.mapper.match(season, team_id, name, kind, game_date)
        self.report.match_methods[res.method] += 1
        if res.player_id is None:
            self.report.unmatched.append({"game_id": gid, "season": season, "team_id": team_id, "name": name,
                                          "kind": kind, "reason": res.method,
                                          "candidates": " ".join(map(str, res.candidates))})
        return res.player_id

    def _fix_decisions(self, gid: str, pitchers: list[dict], team_result: dict, trust: bool) -> None:
        """kbodata 0.2.3 의 change_result 는 결정이 없는 투수까지 'L'로 바꾼다.
        패전 투수는 진 팀에 1명뿐이어야 하므로 그렇지 않은 'L'은 지우고 경기를 기록해 둔다."""
        for p in pitchers:
            self.report.decision_counts[p["decision"] or "-"] += 1
        if trust:
            return
        losses_by_team = Counter(p["team_id"] for p in pitchers if p["decision"] == "L")
        suspect = any(team_result.get(t) != "L" or n > 1 for t, n in losses_by_team.items())
        if not suspect:
            return
        self.report.decision_suspect_games.append(gid)
        for p in pitchers:
            if p["decision"] == "L" and (team_result.get(p["team_id"]) != "L" or losses_by_team[p["team_id"]] > 1):
                p["decision"] = None

    # ------------------------------------------------------------------
    def write(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for table, cols in COLUMNS.items():
            with open(out_dir / f"{table}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for r in self.rows[table]:
                    w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})
        with open(out_dir / "_unmatched_players.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["game_id", "season", "team_id", "name", "kind", "reason", "candidates"])
            w.writeheader()
            w.writerows(self.report.unmatched)
        (out_dir / "_kbodata_report.md").write_text(self.render_report(), encoding="utf-8")

    def render_report(self) -> str:
        r = self.report
        total = sum(r.match_methods.values())
        matched = total - r.match_methods.get("unmatched", 0) - r.match_methods.get("ambiguous", 0)
        lines = [
            "# kbodata 변환 리포트", "",
            f"- 경기 수: {r.games} (변환 전 원본 형식 {r.raw_format_games}경기)",
            f"- 타자 행: {r.batters_total}, 투수 행: {r.pitchers_total}",
            f"- 선수ID 매칭: {matched}/{total}" + (f" ({100 * matched / total:.1f}%)" if total else ""),
            "", "## 매칭 방법별 건수", "",
            "| 방법 | 건수 |", "|---|---:|",
            *[f"| {k} | {v} |" for k, v in r.match_methods.most_common()],
            "", "## 생성 행 수", "", "| 테이블 | 행 |", "|---|---:|",
            *[f"| {t} | {len(self.rows[t])} |" for t in COLUMNS],
            "", "## 투수 결정(decision) 분포", "",
            " / ".join(f"{k}: {v}" for k, v in sorted(r.decision_counts.items())) or "(없음)",
            "",
            f"- 승패 결정이 의심스러운 경기: {len(r.decision_suspect_games)}경기"
            + (" — kbodata change_result 버그(결정 없는 투수를 'L'로 바꿈) 영향. "
               "crawl/kbodata_patch.py 적용 후 다시 수집하는 것을 권장" if r.decision_suspect_games else ""),
        ]
        if r.decision_suspect_games:
            lines.append(f"  - 예: {', '.join(r.decision_suspect_games[:10])}")
        if r.unknown_places:
            lines += ["", "## 구장 매핑 실패 (data/reference/stadium_place_map.csv 에 추가 필요)", "",
                      *[f"- {k}: {v}경기" for k, v in r.unknown_places.most_common()]]
        if r.unknown_event_types:
            lines += ["", "## 모르는 기타기록 항목 (data/reference/game_event_type.csv 에 추가 필요)", "",
                      *[f"- {k}: {v}" for k, v in r.unknown_event_types.most_common()]]
        if r.unmatched:
            lines += ["", f"## 선수ID 매칭 실패 {len(r.unmatched)}건 (_unmatched_players.csv)", "",
                      "| 경기 | 팀 | 이름 | 구분 | 사유 | 후보 |", "|---|---|---|---|---|---|",
                      *[f"| {u['game_id']} | {u['team_id']} | {u['name']} | {u['kind']} | {u['reason']} | {u['candidates']} |"
                        for u in r.unmatched[:200]]]
        if r.warnings:
            lines += ["", f"## 경고 {len(r.warnings)}건", "", *[f"- {w}" for w in r.warnings[:300]]]
        return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", nargs="+", type=Path, help="kbodata raw.json 파일(여러 개 가능)")
    ap.add_argument("--players", type=Path, default=ROOT / "data" / "player_season_team.csv",
                    help="선수 매핑표 (crawl/kbo_records.py 결과)")
    ap.add_argument("--overrides", type=Path, default=ROOT / "data" / "reference" / "player_name_overrides.csv")
    ap.add_argument("--game-dates", type=Path, default=ROOT / "data" / "player_game_dates.csv",
                    help="동명이인 구분용 선수별 출전 일자 (crawl/kbo_gamelogs.py 결과, 없으면 생략)")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "load")
    ap.add_argument("--check-only", action="store_true", help="CSV를 쓰지 않고 매핑 결과만 출력")
    args = ap.parse_args(argv)

    mapper = None
    if args.players.exists():
        mapper = PlayerMapper.from_files(args.players, args.overrides, args.game_dates)
    else:
        print(f"[경고] 선수 매핑표가 없음: {args.players} → 선수 관련 행은 만들지 않음", file=sys.stderr)

    conv = Converter(Reference.load(), mapper)
    for g in load_games(args.raw):
        conv.convert(g)
    if args.check_only:
        print(conv.render_report())
    else:
        conv.write(args.out)
        print(f"변환 완료 → {args.out} (리포트: {args.out / '_kbodata_report.md'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
