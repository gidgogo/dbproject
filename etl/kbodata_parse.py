"""kbodata 경기 JSON → DB 테이블 행 변환에 쓰는 순수 함수 모음 (네트워크·DB 접근 없음).

kbodata(get_game_data)가 돌려주는 경기 하나의 모양:
    {"id": "20250601_OBWO0",
     "contents": {"scoreboard": [원정행, 홈행], "ETC_info": {...},
                  "away_batter": [...], "home_batter": [...],
                  "away_pitcher": [...], "home_pitcher": [...]}}

kbodata는 수집 직후 *_modify 함수로 값을 바꿔 둔다(아래 "변환 후" 형식).
혹시 변환 전 원본(parsing_single_game 결과, 한글 키)을 저장했어도 읽을 수 있게
두 형식을 모두 지원한다.

  변환 후 타자 : name, team, position('H8'), i_1~i_18('1013', '10137000', '-'), hit, bat_num, hit_get, own_get
  변환 후 투수 : name, team, mound('1'/'0'), inning('61'=6⅓), result('W'/'L'/'S'/'H'),
                 strikeout, dead4ball, losescore, earnedrun, pitchnum, hitted, homerun, battednum, batternum
  변환 전 타자 : 선수명, 포지션('타중'), '1'~'n'('좌안', '삼진/유땅'), 타수, 안타, 타점, 득점, 팀
  변환 전 투수 : 선수명, 등판('선발'), 결과('승'), 이닝('6 1/3'), 타자, 투구수, 타수, 피안타, 홈런, 4사구, 삼진, 실점, 자책, 팀
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
GAME_ID_RE = re.compile(r"^(\d{8})_([A-Z]{2})([A-Z]{2})(\d)$")
ETC_NON_EVENT_KEYS = {"구장", "관중", "개시", "종료", "경기시간", "심판"}

# kbodata batter.change_position 과 같은 규칙
POSITION_CHARS = {"一": "3", "二": "4", "三": "5", "투": "1", "포": "2", "유": "6",
                  "좌": "7", "중": "8", "우": "9", "지": "D", "주": "R", "타": "H"}
DECISION_TEXT = {"승": "W", "패": "L", "세": "S", "세이브": "S", "홀드": "H", "홀": "H"}


# ---------------------------------------------------------------------------
# 입력 파일 읽기
# ---------------------------------------------------------------------------
def iter_games(obj: Any) -> Iterator[dict]:
    """raw.json 의 최상위 모양이 리스트/단일 경기/{키: 리스트} 어느 쪽이든 경기만 꺼낸다."""
    if isinstance(obj, dict) and "id" in obj and "contents" in obj:
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from iter_games(x)
    elif isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, (list, dict)):
                yield from iter_games(v)


def load_games(paths: list[Path]) -> list[dict]:
    games: dict[str, dict] = {}
    for p in paths:
        text = Path(p).read_text(encoding="utf-8")
        try:
            objs = [json.loads(text)]
        except json.JSONDecodeError:  # JSON Lines
            objs = [json.loads(line) for line in text.splitlines() if line.strip()]
        for o in objs:
            for g in iter_games(o):
                games[g["id"]] = g  # 같은 경기가 여러 파일에 있으면 마지막 것
    return [games[k] for k in sorted(games)]


# ---------------------------------------------------------------------------
# 값 변환
# ---------------------------------------------------------------------------
def parse_game_id(game_id: str) -> tuple[date, str, str, int]:
    m = GAME_ID_RE.match(game_id)
    if not m:
        raise ValueError(f"경기ID 형식 오류: {game_id}")
    d = m.group(1)
    return date(int(d[:4]), int(d[4:6]), int(d[6:])), m.group(2), m.group(3), int(m.group(4))


def to_int(v: Any, default: int | None = 0) -> int | None:
    if v is None:
        return default
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "nan", "None"):
        return default
    try:
        return int(float(s))
    except ValueError:
        return default


def parse_hhmm(v: Any) -> str | None:
    """'18:30' → '18:30', 빈 값 → None"""
    s = str(v or "").strip()
    return s if re.fullmatch(r"\d{1,2}:\d{2}", s) else None


def duration_minutes(v: Any) -> int | None:
    """'3:05' → 185"""
    s = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def outs_from_kbodata_inning(v: Any) -> int:
    """kbodata 변환 후 이닝 '61' → 19 (마지막 자리 = 나머지 아웃, 앞자리 = 이닝)"""
    s = str(v).strip()
    if not s.isdigit():
        raise ValueError(f"이닝 값 오류: {v!r}")
    if len(s) == 1:  # '0' 같은 값
        return int(s) * 3
    return int(s[:-1]) * 3 + int(s[-1])


def outs_from_text_inning(v: Any) -> int:
    """원본 표기 '6 1/3' → 19, '2/3' → 2, '5' → 15"""
    s = str(v).strip()
    if s in ("", "0", "-", "nan"):
        return 0
    whole, frac = 0, 0
    for part in s.split():
        if "/" in part:
            frac = int(part.split("/")[0])
        else:
            whole = int(float(part))
    return whole * 3 + frac


def split_pa_codes(v: Any) -> list[int]:
    """kbodata 이닝 칸 값 → 4자리 결과코드 목록. '10137000' → [1013, 7000], '-' → []"""
    if v is None:
        return []
    if isinstance(v, float):
        v = int(v)
    s = str(v).strip()
    if not s.isdigit():
        return []
    codes, i = [], 0
    while i < len(s):
        if s[i] == "0":  # '0' / 'NONE' 은 한 글자 0으로 들어온다 → 타석 아님
            i += 1
            continue
        chunk = s[i:i + 4]
        if len(chunk) < 4:
            raise ValueError(f"결과코드 길이 오류: {v!r}")
        codes.append(int(chunk))
        i += 4
    return codes


def position_code(v: Any) -> str | None:
    """'H8' 그대로, 원본 '타중' → 'H8'. 해석 불가면 None"""
    s = str(v or "").strip()
    if not s or s in ("0", "nan"):
        return None
    out = "".join(POSITION_CHARS.get(ch, ch) for ch in s)
    return out if re.fullmatch(r"[1-9DHR]+", out) else None


# ---------------------------------------------------------------------------
# 기타 기록(ETC_info) 파싱
# ---------------------------------------------------------------------------
_ETC_ITEM = re.compile(r"^\s*(?P<name>[^\d(]+?)\s*(?P<num>\d+)?(?P<ho>호)?\s*(?:\((?P<detail>[^)]*)\)?)?\s*$")


def etc_items(value: Any) -> list[str]:
    """kbodata는 ') ' 기준으로 잘라 리스트로 주거나(2개 이상일 때) 문자열 하나로 준다."""
    if value is None:
        return []
    if isinstance(value, list):
        parts = [str(x) for x in value]
    else:
        parts = str(value).split(") ")
    items = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if "(" in p and not p.endswith(")"):
            p += ")"  # 잘려 나간 닫는 괄호 복원
        items.append(p)
    return items


def parse_etc_item(text: str) -> dict:
    """'임종성2(4 6회)' → {'name': '임종성', 'innings': [4, 6], 'count': 2, 'detail': '4 6회'}
       '양의지12호(4회2점 김광현)' → {'name': '양의지', 'innings': [4], 'count': 1, ...}"""
    m = _ETC_ITEM.match(text)
    if not m:
        return {"name": text.strip(), "innings": [], "count": 1, "detail": None}
    detail = (m.group("detail") or "").strip() or None
    innings: list[int] = []
    if detail:
        lead = re.match(r"^([\d\s,]+)회", detail)
        if lead:
            innings += [int(x) for x in re.findall(r"\d+", lead.group(1))]
        for x in re.findall(r"(\d+)회", detail):
            if int(x) not in innings:
                innings.append(int(x))
    num = m.group("num")
    if num and not m.group("ho"):
        count = int(num)
    else:
        count = max(1, len(innings))
    return {"name": m.group("name").strip(), "innings": innings, "count": count, "detail": detail}


# ---------------------------------------------------------------------------
# 형식 판별
# ---------------------------------------------------------------------------
def is_raw_format(game: dict) -> bool:
    """변환 전(한글 키) 형식이면 True"""
    c = game["contents"]
    rows = (c.get("away_batter") or []) + (c.get("scoreboard") or [])
    return any("선수명" in r or "팀" in r for r in rows)


# ---------------------------------------------------------------------------
# 변환 전(한글) 타격 결과 → 코드 (kbodata batter.trans_code 와 같은 규칙)
# ---------------------------------------------------------------------------
def load_result_name_map(ini_path: Path | None = None) -> dict[str, int]:
    ini_path = ini_path or ROOT / "data" / "reference" / "kbodata_batter_codes.ini"
    out, on = {}, False
    for raw in Path(ini_path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("["):
            on = line == "[BATTER]"
            continue
        if on and ":" in line:
            k, v = (x.strip() for x in line.split(":", 1))
            out[k] = int(v)
    return out


def text_to_codes(text: Any, name_map: dict[str, int]) -> list[int]:
    """'좌안/삼진' → [1019, 2000]. 모르는 표기는 ValueError"""
    s = str(text or "").strip()
    if s in ("", "-", "0", "nan"):
        return []
    codes = []
    for tok in re.split(r"\W", s):
        if not tok:
            continue
        tok = tok.replace("一", "1").replace("二", "2").replace("三", "3")
        if tok not in name_map:
            raise ValueError(f"모르는 타격 결과 표기: {tok!r}")
        if name_map[tok] != 0:
            codes.append(name_map[tok])
    return codes
