"""kbodata 타석 결과 코드표([BATTER]) → data/reference/pa_result_type.csv, pa_result_code.csv

kbodata는 박스스코어의 이닝별 타격 결과(예: '좌중안', '삼진', '유땅')를
4자리 숫자 코드로 바꿔서 i_1 ~ i_18 컬럼에 넣는다. 이 스크립트는 그 코드표를
두 테이블로 나눠 정리한다.

  PA_RESULT_TYPE : 결과 유형(안타, 2루타, 삼진, 땅볼 ...)과 집계 플래그(타수 여부, 루타 수 ...)
  PA_RESULT_CODE : 개별 코드(좌중안, 유땅 ...) → 유형(FK), 타구 방향

플래그(타수 여부 등)는 코드가 아니라 유형에 따라 정해진다. 한 테이블에 두면
'코드 → 유형 → 플래그' 이행 종속이 생겨 3NF를 위반하므로 분리했다.

코드 범위 규칙은 kbodata config.ini 주석을 그대로 따른다.
  1000~ 안타 / 1100~ 2루타 / 1200~ 3루타 / 1300~ 홈런 / 2000 삼진 / 2100 스낫
  3000 볼넷 / 3100 사구 / 3200 고의4구 / 4000~ 번트 / 4100~ 희생번트
  5000~ 희생플라이 / 6000~ 실책 / 6100~ 희생번트 실책 / 6200~ 희생번트 야수선택
  6300 야수선택 / 6400 타격방해 / 7000~ 플라이 / 7100~ 땅볼 / 7200~ 병살
  7300~ 직선타 / 7400~ 파울플라이

사용법:
    python tools/gen_pa_result_code.py            # 기본 입력/출력 경로 사용
    python tools/gen_pa_result_code.py IN.ini OUT.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "data" / "reference" / "kbodata_batter_codes.ini"
DEFAULT_OUT = ROOT / "data" / "reference" / "pa_result_code.csv"
DEFAULT_TYPE_OUT = ROOT / "data" / "reference" / "pa_result_type.csv"

# (시작, 끝(포함), 유형코드, 유형명, 타수, 안타, 루타, 볼넷, 사구, 희비, 희번, 삼진, 병살, 타구종류)
RANGES = [
    (1000, 1099, "SINGLE", "안타", 1, 1, 1, 0, 0, 0, 0, 0, 0, None),
    (1100, 1199, "DOUBLE", "2루타", 1, 1, 2, 0, 0, 0, 0, 0, 0, None),
    (1200, 1299, "TRIPLE", "3루타", 1, 1, 3, 0, 0, 0, 0, 0, 0, None),
    (1300, 1399, "HOME_RUN", "홈런", 1, 1, 4, 0, 0, 0, 0, 0, 0, None),
    (2000, 2000, "STRIKEOUT", "삼진", 1, 0, 0, 0, 0, 0, 0, 1, 0, None),
    (2100, 2100, "STRIKEOUT_NOT_OUT", "스트라이크 낫아웃", 1, 0, 0, 0, 0, 0, 0, 1, 0, None),
    (3000, 3000, "WALK", "볼넷", 0, 0, 0, 1, 0, 0, 0, 0, 0, None),
    (3100, 3100, "HIT_BY_PITCH", "몸에 맞는 공", 0, 0, 0, 0, 1, 0, 0, 0, 0, None),
    (3200, 3200, "INTENTIONAL_WALK", "고의4구", 0, 0, 0, 1, 0, 0, 0, 0, 0, None),
    (4000, 4099, "BUNT_OUT", "번트 아웃", 1, 0, 0, 0, 0, 0, 0, 0, 0, "BU"),
    (4100, 4199, "SAC_BUNT", "희생번트", 0, 0, 0, 0, 0, 0, 1, 0, 0, "BU"),
    (5000, 5099, "SAC_FLY", "희생플라이", 0, 0, 0, 0, 0, 1, 0, 0, 0, "FB"),
    (6000, 6099, "REACHED_ON_ERROR", "실책 출루", 1, 0, 0, 0, 0, 0, 0, 0, 0, None),
    (6100, 6199, "SAC_BUNT_ERROR", "희생번트 실책", 0, 0, 0, 0, 0, 0, 1, 0, 0, "BU"),
    (6200, 6299, "SAC_BUNT_FC", "희생번트 야수선택", 0, 0, 0, 0, 0, 0, 1, 0, 0, "BU"),
    (6300, 6300, "FIELDERS_CHOICE", "야수선택", 1, 0, 0, 0, 0, 0, 0, 0, 0, None),
    (6400, 6400, "INTERFERENCE", "타격방해", 0, 0, 0, 0, 0, 0, 0, 0, 0, None),
    (7000, 7099, "FLY_OUT", "플라이 아웃", 1, 0, 0, 0, 0, 0, 0, 0, 0, "FB"),
    (7100, 7199, "GROUND_OUT", "땅볼 아웃", 1, 0, 0, 0, 0, 0, 0, 0, 0, "GB"),
    (7200, 7299, "DOUBLE_PLAY", "병살타", 1, 0, 0, 0, 0, 0, 0, 0, 1, "GB"),
    (7300, 7399, "LINE_OUT", "직선타 아웃", 1, 0, 0, 0, 0, 0, 0, 0, 0, "LD"),
    (7400, 7499, "FOUL_OUT", "파울플라이 아웃", 1, 0, 0, 0, 0, 0, 0, 0, 0, "FB"),
]

# 결과명 앞부분의 방향 글자 → 수비 위치 번호(1 투수 ~ 9 우익수)
FIELDER = {"투": 1, "포": 2, "1": 3, "2": 4, "3": 5, "삼": 5, "유": 6, "좌": 7, "중": 8, "우": 9}
# 수비 위치 → 좌우 각도 점수(좌측 -2 ~ 우측 +2). 스프레이 차트용 5구역으로 묶는다.
ANGLE = {1: 0, 2: 0, 3: 2, 4: 1, 5: -2, 6: -1, 7: -2, 8: 0, 9: 2}
# 방향 뒤에 붙는 결과 표기(긴 것부터 검사)
SUFFIXES = ["삼중", "희번", "희실", "희선", "희비", "안", "2", "3", "홈", "번", "실", "선",
            "비", "땅", "병", "직", "파"]


def classify(code: int):
    for lo, hi, *rest in RANGES:
        if lo <= code <= hi:
            return rest
    raise ValueError(f"범위 밖 코드: {code}")


def split_direction(name: str) -> str:
    """'좌중안' → '좌중', '유2안' → '유2', '122' → '12', '삼진' → ''"""
    if name in ("삼진", "스낫", "4구", "사구", "고4", "야선", "타방"):
        return ""
    for suf in SUFFIXES:
        if name.endswith(suf) and len(name) > len(suf):
            return name[: -len(suf)]
    return ""


def spray(fielders: list[int]) -> str | None:
    if not fielders:
        return None
    score = sum(ANGLE[f] for f in fielders) / len(fielders)
    if score <= -1.5:
        return "L"
    if score <= -0.5:
        return "LC"
    if score < 0.5:
        return "C"
    if score < 1.5:
        return "RC"
    return "R"


def parse_ini(path: Path) -> list[tuple[str, int]]:
    pairs, in_batter = [], False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("["):
            in_batter = line == "[BATTER]"
            continue
        if in_batter and ":" in line:
            k, v = (s.strip() for s in line.split(":", 1))
            pairs.append((k, int(v)))
    return pairs


def build(pairs: list[tuple[str, int]]) -> list[dict]:
    by_code: dict[int, list[str]] = {}
    for name, code in pairs:
        if code == 0:  # '0', 'NONE' → 타석 아님
            continue
        by_code.setdefault(code, []).append(name)
    rows = []
    for code in sorted(by_code):
        names = by_code[code]
        name = names[0]
        type_code = classify(code)[0]
        if code == 7226:  # '3삼중' = 삼중살
            type_code = "TRIPLE_PLAY"
        direction = split_direction(name)
        fielders = [FIELDER[c] for c in direction if c in FIELDER]
        if type_code in ("STRIKEOUT", "STRIKEOUT_NOT_OUT", "WALK", "HIT_BY_PITCH",
                         "INTENTIONAL_WALK", "INTERFERENCE"):
            fielders = []
        rows.append({
            "result_code": code,
            "result_name": name,
            "result_type": type_code,
            "fielder_pos": fielders[0] if fielders else "",
            "spray_dir": spray(fielders) or "",
            "aliases": "|".join(names[1:]),  # 참고용(DB에는 적재하지 않음)
        })
    return rows


def build_types() -> list[dict]:
    rows = []
    for lo, hi, type_code, type_name, ab, hit, tb, bb, hbp, sf, sh, so, gdp, bb_type in RANGES:
        rows.append(_type_row(type_code, type_name, ab, hit, tb, bb, hbp, sf, sh, so, gdp, bb_type))
    rows.append(_type_row("TRIPLE_PLAY", "삼중살", 1, 0, 0, 0, 0, 0, 0, 0, 1, "GB"))
    return rows


def _type_row(type_code, type_name, ab, hit, tb, bb, hbp, sf, sh, so, gdp, bb_type) -> dict:
    return {
        "result_type": type_code,
        "result_type_name": type_name,
        "batted_ball": bb_type or "",
        "is_at_bat": ab,
        "is_hit": hit,
        "total_bases": tb,
        "is_walk": bb,
        "is_hbp": hbp,
        "is_sac_fly": sf,
        "is_sac_bunt": sh,
        "is_strikeout": so,
        "is_double_play": gdp,
    }


def main(argv: list[str]) -> None:
    src = Path(argv[1]) if len(argv) > 1 else DEFAULT_IN
    dst = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    rows = build(parse_ini(src))
    types = build_types()
    for path, data in ((dst, rows), (dst.with_name("pa_result_type.csv") if len(argv) > 2 else DEFAULT_TYPE_OUT, types)):
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
        print(f"{len(data)}행 → {path}")


if __name__ == "__main__":
    main(sys.argv)
