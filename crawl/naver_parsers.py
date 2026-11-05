"""네이버 스포츠 KBO 문자중계(relay) JSON → 투구 행 (순수 함수, 네트워크 없음)

API 구조 근거 (공개 오픈소스에서 확인, 맥에서 crawl/naver_probe.py 로 재확인 필요)
  일정:  GET https://api-gw.sports.naver.com/schedule/games
           ?fields=basic,schedule,baseball&upperCategoryId=kbaseball&categoryId=kbo
           &fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD&size=..&page=..
         → result.games[]: gameId, gameDate, homeTeamCode, awayTeamCode, statusCode, statusInfo('9회말'),
           roundCode('kbo_r' 정규시즌), cancel ...   (result.gameTotalCount 로 페이지 계산)
  중계:  GET https://api-gw.sports.naver.com/schedule/games/{gameId}/relay?inning={n}
         → result.textRelayData: textRelays[] (블록, 한 이닝 안에서 최신순),
           homeLineup/awayLineup {batter[], pitcher[]} (pcode, name, batOrder ...)
  블록:  title('3번타자 홍길동'), homeOrAway('0' 원정 공격/'1' 홈 공격), textOptions[], ptsOptions[]
  이벤트(textOptions[]): seqno, type, text, currentGameState{ball, strike, out, base1~3, homeScore, awayScore,
           batter, pitcher}(이벤트 *후* 상태, 값은 문자열), 투구면 pitchNum, pitchResult, stuff(구종), speed(km/h),
           ptsPitchId
           type: 0 이닝 시작, 1 투구, 2 교체, 7 투수 이벤트, 8 타자 등장, 13 타석 결과, 14 주루,
                 23 득점이 난 타석 결과, 24 득점, 44 실책 주석, 99 경기 종료 문구
  트래킹(ptsOptions[]): pitchId(=ptsPitchId), crossPlateX(ft), topSz, bottomSz, x0,y0,z0, vx0,vy0,vz0,
           ax,ay,az, stance — PITCHf/x 형식(피트 단위). 높이(plate_z)는 따로 없어서 궤적으로 계산한다.

경기ID: 네이버 gameId = KBO G_ID + 시즌 (예: 20250601OBWO02025)
        → 우리 game_id = 'YYYYMMDD_' + 원정 + 홈 + 더블헤더 (일정의 팀 코드로 만든다)
"""
from __future__ import annotations

import re
from typing import Any

PITCH, BATTER, OUTCOME, OUTCOME_RUN = 1, 8, 13, 23
OUTCOMES = (OUTCOME, OUTCOME_RUN)

# 공개 분석(kbo_pbp_naver_sports)에서 crossPlateX를 재현하는 기준면이 플레이트 중간(0.7083ft = 8.5인치)
# 으로 확인됨. 일부 경기는 crossPlateY 값이 이와 달라 상수를 쓴다.
PLATE_Y_FT = 0.7083
PTS_FIELDS = ("crossPlateX", "topSz", "bottomSz", "x0", "y0", "z0", "vx0", "vy0", "vz0", "ax", "ay", "az", "stance")


# ---------------------------------------------------------------------------
# 경기 ID / 일정
# ---------------------------------------------------------------------------
def our_game_id(naver_game: dict) -> str | None:
    """일정 항목 → 'YYYYMMDD_AWAYHOME0'. 날짜·팀코드·더블헤더 숫자를 따로 읽어 조합한다
    (네이버 gameId의 팀 순서가 뒤집힌 경기가 있다는 보고가 있어 문자열을 그대로 자르지 않음)."""
    gid = str(naver_game.get("gameId", ""))
    m = re.match(r"^(\d{8})([A-Z]{2})([A-Z]{2})(\d)", gid)
    if not m:
        return None
    date = m.group(1)
    home = naver_game.get("homeTeamCode") or m.group(3)
    away = naver_game.get("awayTeamCode") or m.group(2)
    return f"{date}_{away}{home}{m.group(4)}"


def final_inning(status_info: Any) -> int | None:
    m = re.match(r"^\s*(\d+)\s*회", str(status_info or ""))
    return int(m.group(1)) if m else None


def playable(game: dict, team: str | None = None, rounds: tuple[str, ...] = ("kbo_r",)) -> bool:
    """끝난 경기인가: statusInfo 가 'N회…' 이거나 statusCode 가 RESULT (취소 제외)"""
    if rounds and game.get("roundCode") not in rounds:
        return False
    finished = final_inning(game.get("statusInfo")) is not None or game.get("statusCode") == "RESULT"
    if game.get("cancel") or not finished:
        return False
    return team is None or team in (game.get("homeTeamCode"), game.get("awayTeamCode"))


# ---------------------------------------------------------------------------
# 중계 → 이벤트 흐름
# ---------------------------------------------------------------------------
def flatten(innings: dict[int, dict]) -> list[dict]:
    """{이닝: textRelayData} → 시간순 이벤트 목록 (각 이벤트에 inning, half 추가)

    한 이닝 안의 블록은 최신순이라 뒤집는다. 같은 반이닝이 다시 전송되어 seqno가 뒤로
    돌아가면 그 뒤는 중복으로 보고 버린다."""
    out = []
    for inning in sorted(innings):
        highest: dict[str, int] = {}
        stopped: set[str] = set()
        for block in reversed(innings[inning].get("textRelays") or []):
            opts = block.get("textOptions") or []
            half = "T" if str(block.get("homeOrAway", "0")) == "0" else "B"
            if not opts or half in stopped:
                continue
            first = _int(opts[0].get("seqno"))
            if first is not None and first < highest.get(half, -1):
                stopped.add(half)
                continue
            highest[half] = max([_int(o.get("seqno")) or 0 for o in opts] + [highest.get(half, -1)])
            for o in opts:
                out.append({**o, "inning": inning, "half": half})
    return out


def tracking(innings: dict[int, dict]) -> dict[str, dict]:
    """pitchId → 트래킹 값 (+ 계산한 plate_z)"""
    out = {}
    for relay in innings.values():
        for block in relay.get("textRelays") or []:
            for p in block.get("ptsOptions") or []:
                if p.get("pitchId"):
                    rec = {k: p.get(k) for k in PTS_FIELDS if k in p}
                    rec["plate_z"] = plate_z(p)
                    out[str(p["pitchId"])] = rec
    return out


def plate_z(p: dict) -> float | None:
    """등가속도 궤적에서 y = PLATE_Y_FT 를 지나는 시각 t를 구해 그때의 높이 z(t) (피트)"""
    try:
        y0, vy0, ay = float(p["y0"]), float(p["vy0"]), float(p["ay"])
        z0, vz0, az = float(p["z0"]), float(p["vz0"]), float(p["az"])
    except (KeyError, TypeError, ValueError):
        return None
    disc = vy0 * vy0 - 2 * ay * (y0 - PLATE_Y_FT)
    if ay == 0 or disc < 0:
        return None
    t = (-vy0 - disc ** 0.5) / ay
    return round(z0 + vz0 * t + 0.5 * az * t * t, 4)


def lineup_names(innings: dict[int, dict]) -> dict[str, tuple[str, str]]:
    """pcode → (이름, 'home'|'away') — 라인업은 누적이라 마지막 이닝 것을 쓴다"""
    out: dict[str, tuple[str, str]] = {}
    for inning in sorted(innings):
        relay = innings[inning]
        for side in ("home", "away"):
            lu = relay.get(f"{side}Lineup") or {}
            for p in (lu.get("batter") or []) + (lu.get("pitcher") or []):
                if p.get("pcode"):
                    out[str(p["pcode"])] = (str(p.get("name", "")), side)
    return out


def pitch_rows(innings: dict[int, dict]) -> list[dict]:
    """타석은 결과(13/23) 이벤트까지 이어진다. 결과 전에 새 타자(8)가 나오면 대타로 보고 같은 타석으로 둔다."""
    pts = tracking(innings)
    rows: list[dict] = []
    pa: dict | None = None
    prev_state: dict = {}
    at_bat_no = 0
    for ev in flatten(innings):
        state = ev.get("currentGameState") or {}
        etype = _int(ev.get("type"))
        if pa is not None and ((ev["inning"], ev["half"]) != (pa["inning"], pa["half"])
                               or (etype == BATTER and pa["outcome"] is not None)):
            pa = None
        if etype == BATTER and pa is None:
            at_bat_no += 1
            pa = {"inning": ev["inning"], "half": ev["half"], "no": at_bat_no, "outs": _int(state.get("out")) or 0,
                  "seen": set(), "outcome": None, "rows": []}
            prev_state = {**state, "ball": "0", "strike": "0"}  # 새 타석은 0-0 에서 시작
            continue
        if pa is not None and etype == PITCH:
            num = _int(ev.get("pitchNum")) or 0
            if num and num in pa["seen"]:  # 같은 투구가 다시 전송된 경우
                continue
            pa["seen"].add(num)
            t = pts.get(str(ev.get("ptsPitchId") or ""), {})
            row = {
                "inning": ev["inning"], "half": ev["half"], "at_bat_no": pa["no"], "pitch_no": num,
                "pitcher_pcode": str(state.get("pitcher") or ""), "batter_pcode": str(state.get("batter") or ""),
                "balls": min(_int(prev_state.get("ball")) or 0, 3), "strikes": min(_int(prev_state.get("strike")) or 0, 2),
                "outs": min(pa["outs"], 2),
                "pitch_type_ko": ev.get("stuff") or None, "speed_kmh": _int(ev.get("speed")),
                "pitch_result_code": ev.get("pitchResult") or None, "description": ev.get("text"),
                "plate_x": t.get("crossPlateX"), "plate_z": t.get("plate_z"),
                "sz_top": t.get("topSz"), "sz_bot": t.get("bottomSz"),
                "batter_stance": t.get("stance") if t.get("stance") in ("L", "R") else None,
                "naver_pitch_id": ev.get("ptsPitchId") or None, "pa_result_text": None,
            }
            pa["rows"].append(row)
            rows.append(row)
        elif pa is not None and etype in OUTCOMES:
            pa["outcome"] = ev.get("text")
            if pa["rows"]:
                pa["rows"][-1]["pa_result_text"] = ev.get("text")
        # 이벤트의 상태는 '이벤트 후' 값이므로, 다음 투구의 '직전 카운트'로 쓴다.
        # (타석 중간에 대타가 들어와도 카운트는 이어진다)
        prev_state = state
    for i, r in enumerate(rows, 1):
        r["pitch_seq"] = i
    return rows


def _int(v: Any) -> int | None:
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None
