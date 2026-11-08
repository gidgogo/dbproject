"""이름 + 팀 + 시즌 → KBO playerId 매핑.

kbodata 박스스코어에는 선수 이름만 있다. 크롤링한 선수 목록
(data/player_season_team.csv: season, team_id, player_id, name, ...)을 기준으로
다음 순서대로 찾는다. 앞 단계에서 하나로 정해지면 멈춘다.

  0. override   : data/reference/player_name_overrides.csv 에 사람이 직접 적은 매핑
                 (match_id를 적으면 그 경기에만, 비우면 그 시즌·팀 전체에 적용)
  1. exact      : 같은 시즌·같은 팀·같은 이름이 1명
  2. exact_kind : 같은 이름이 여러 명이면 타자/투수 구분으로 1명
  3. gamelog    : 그래도 여러 명이면 선수별 경기 일자(Daily 페이지)로 그 날 출전한 1명
  4. position   : 그래도 여러 명이면 그날 수비 위치와 선수 프로필 포지션(data/players.csv)으로 1명
                 (예: 중견수로 나온 '이주형' → 외야수 50167, 대타 '김태훈' → 투수가 아닌 65040)
  5. prefix     : 박스스코어 이름이 잘린 경우 (외국인: '페르난데' → '페르난데스')
  6. nospace    : 공백·가운뎃점 차이 ('로하스 주니어' ↔ '로하스주니어')
  7. other_team : 같은 시즌 다른 팀에 1명 (시즌 중 이적으로 소속 표기가 다른 경우).
                 여러 명이면 2~4단계로 다시 좁힌다
실패하면 None과 실패 사유(unmatched / ambiguous)를 돌려준다.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm(name: str) -> str:
    return "".join(ch for ch in name if ch not in " ·.-").strip()


@dataclass(frozen=True)
class Candidate:
    player_id: int
    name: str
    is_batter: bool
    is_pitcher: bool


@dataclass
class MatchResult:
    player_id: int | None
    method: str
    candidates: tuple[int, ...] = ()


# kbodata 포지션 코드(숫자) → 선수 프로필 포지션
_FIELD_GROUP = {"1": "투수", "2": "포수", "3": "내야수", "4": "내야수", "5": "내야수", "6": "내야수",
                "7": "외야수", "8": "외야수", "9": "외야수"}


class PlayerMapper:
    def __init__(self) -> None:
        self.by_team: dict[tuple[int, str], list[Candidate]] = defaultdict(list)
        self.by_season: dict[int, list[tuple[str, Candidate]]] = defaultdict(list)
        self.overrides: dict[tuple[int, str, str], int] = {}
        self.match_overrides: dict[tuple[str, str, str], int] = {}
        self.game_dates: dict[int, set[str]] = defaultdict(set)
        self.profile_position: dict[int, str] = {}

    # ---- 적재 ------------------------------------------------------------
    @classmethod
    def from_files(cls, player_season_csv: Path,
                   overrides_csv: Path | None = None,
                   game_dates_csv: Path | None = None,
                   profiles_csv: Path | None = None) -> "PlayerMapper":
        m = cls()
        with open(player_season_csv, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                m.add(int(r["season"]), r["team_id"], int(r["player_id"]), r["name"],
                      _truthy(r.get("is_batter", "1")), _truthy(r.get("is_pitcher", "0")))
        if overrides_csv and Path(overrides_csv).exists():
            with open(overrides_csv, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    match_id = (r.get("match_id") or "").strip()
                    if match_id:
                        m.match_overrides[(match_id, r["team_id"], r["name"])] = int(r["player_id"])
                    else:
                        m.overrides[(int(r["season"]), r["team_id"], r["name"])] = int(r["player_id"])
        if game_dates_csv and Path(game_dates_csv).exists():
            with open(game_dates_csv, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    m.game_dates[int(r["player_id"])].add(r["game_date"])
        if profiles_csv and Path(profiles_csv).exists():
            with open(profiles_csv, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    if (r.get("position") or "").strip():
                        m.profile_position[int(r["player_id"])] = r["position"].strip()
        return m

    def add(self, season: int, team_id: str, player_id: int, name: str,
            is_batter: bool = True, is_pitcher: bool = False) -> None:
        bucket = self.by_team[(season, team_id)]
        for i, c in enumerate(bucket):
            if c.player_id == player_id:  # 타자·투수 목록 양쪽에 있으면 합친다
                bucket[i] = Candidate(player_id, c.name, c.is_batter or is_batter,
                                      c.is_pitcher or is_pitcher)
                break
        else:
            cand = Candidate(player_id, name, is_batter, is_pitcher)
            bucket.append(cand)
            self.by_season[season].append((team_id, cand))

    # ---- 매칭 ------------------------------------------------------------
    def match(self, season: int, team_id: str, name: str, kind: str,
              game_date: str | None = None, positions: str | None = None,
              match_id: str | None = None) -> MatchResult:
        """kind: 'batter' 또는 'pitcher'. game_date: 'YYYY-MM-DD' (gamelog 단계용).
        positions: 그날 타자 포지션 코드 ('H8', '9' …, position 단계용). match_id: 경기별 예외표용"""
        name = (name or "").strip()
        if match_id and (match_id, team_id, name) in self.match_overrides:
            return MatchResult(self.match_overrides[(match_id, team_id, name)], "override")
        if (season, team_id, name) in self.overrides:
            return MatchResult(self.overrides[(season, team_id, name)], "override")

        pool = self.by_team.get((season, team_id), [])
        exact = [c for c in pool if c.name == name]
        if len(exact) == 1:
            return MatchResult(exact[0].player_id, "exact")
        if len(exact) > 1:
            return self._disambiguate(exact, kind, game_date, positions)

        if len(name) >= 2:
            pref = [c for c in pool if c.name.startswith(name)]
            if len(pref) == 1:
                return MatchResult(pref[0].player_id, "prefix")
            if len(pref) > 1:
                return MatchResult(None, "ambiguous", tuple(c.player_id for c in pref))

        ns = [c for c in pool if _norm(c.name) == _norm(name)]
        if len(ns) == 1:
            return MatchResult(ns[0].player_id, "nospace")

        other = [c for t, c in self.by_season.get(season, []) if t != team_id and c.name == name]
        if len(other) == 1:
            return MatchResult(other[0].player_id, "other_team")
        if len(other) > 1:
            return self._disambiguate(other, kind, game_date, positions)
        return MatchResult(None, "unmatched")

    def _disambiguate(self, cands: list[Candidate], kind: str, game_date: str | None,
                      positions: str | None = None) -> MatchResult:
        by_kind = [c for c in cands if (c.is_pitcher if kind == "pitcher" else c.is_batter)]
        if len(by_kind) == 1:
            return MatchResult(by_kind[0].player_id, "exact_kind")
        pool = by_kind or cands
        if game_date:
            played = [c for c in pool if game_date in self.game_dates.get(c.player_id, set())]
            if len(played) == 1:
                return MatchResult(played[0].player_id, "gamelog")
        by_pos = self._by_position(pool, kind, positions)
        if len(by_pos) == 1:
            return MatchResult(by_pos[0].player_id, "position")
        return MatchResult(None, "ambiguous", tuple(c.player_id for c in pool))

    def _by_position(self, pool: list[Candidate], kind: str, positions: str | None) -> list[Candidate]:
        """프로필 포지션이 있는 후보만 비교한다. 하나라도 프로필이 없으면 판단하지 않는다."""
        if not self.profile_position or any(c.player_id not in self.profile_position for c in pool):
            return []
        pos = {c.player_id: self.profile_position[c.player_id] for c in pool}
        if kind == "pitcher":
            return [c for c in pool if pos[c.player_id] == "투수"]
        groups = {_FIELD_GROUP[ch] for ch in (positions or "") if ch in _FIELD_GROUP}
        if groups:  # 수비에 나간 타자: 그 수비 위치와 프로필 포지션이 같은 후보
            return [c for c in pool if pos[c.player_id] in groups]
        return [c for c in pool if pos[c.player_id] != "투수"]  # 대타·대주자·지명타자


def _truthy(v: str | None) -> bool:
    return str(v).strip().lower() in ("1", "true", "t", "y", "yes")
