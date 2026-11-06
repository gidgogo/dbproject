"""data/reference 의 기준 CSV를 읽어 이름 → 코드 변환에 쓰는 도우미.

- 팀명(kbodata·기록실 표기) + 시즌 → KBO 팀코드
- 박스스코어 구장 표기 + 시즌 → stadium_id
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT / "data" / "reference"

# kbodata config.ini [TEAM] 과 util.change_name_to_id 에서 확인한 별칭.
# 시즌별 표기(team_season.csv)로 못 찾을 때만 쓴다.
TEAM_ALIASES = {
    "두산": "OB", "OB": "OB",
    "롯데": "LT",
    "삼성": "SS",
    "한화": "HH",
    "LG": "LG",
    "KIA": "HT", "기아": "HT",
    "SK": "SK", "SSG": "SK",
    "우리": "WO", "서울": "WO", "히어로즈": "WO", "넥센": "WO", "키움": "WO",
    "NC": "NC",
    "KT": "KT", "kt": "KT",
}


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Reference:
    team_by_season_name: dict[tuple[int, str], str] = field(default_factory=dict)
    team_ids: set[str] = field(default_factory=set)
    place_rules: list[tuple[str, int, int | None, int]] = field(default_factory=list)
    event_types: set[str] = field(default_factory=set)
    pa_codes: set[int] = field(default_factory=set)

    @classmethod
    def load(cls, ref_dir: Path = REF_DIR) -> "Reference":
        ref = cls()
        for r in read_csv(ref_dir / "team.csv"):
            ref.team_ids.add(r["team_id"])
        for r in read_csv(ref_dir / "team_season.csv"):
            ref.team_by_season_name[(int(r["season"]), r["short_name"])] = r["team_id"]
            ref.team_by_season_name[(int(r["season"]), r["team_name"])] = r["team_id"]
        for r in read_csv(ref_dir / "stadium_place_map.csv"):
            to = int(r["to_season"]) if r["to_season"] else None
            ref.place_rules.append((r["place"], int(r["from_season"]), to, int(r["stadium_id"])))
        ref.event_types = {r["event_type"] for r in read_csv(ref_dir / "game_event_type.csv")}
        ref.pa_codes = {int(r["result_code"]) for r in read_csv(ref_dir / "pa_result_code.csv")}
        return ref

    def team_id(self, name: str | None, season: int) -> str | None:
        """'두산', 'SSG', 'OB' 같은 표기를 팀코드로. 모르면 None."""
        key = (name or "").strip()
        if key in self.team_ids:
            return key
        if (season, key) in self.team_by_season_name:
            return self.team_by_season_name[(season, key)]
        return TEAM_ALIASES.get(key)

    def stadium_id(self, place: str | None, season: int) -> int | None:
        key = (place or "").strip()
        for p, frm, to, sid in self.place_rules:
            if p == key and frm <= season and (to is None or season <= to):
                return sid
        return None
