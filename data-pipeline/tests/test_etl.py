"""etl/ 순수 함수 단위 테스트 (네트워크·DB 불필요)"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from etl.kbodata_parse import (  # noqa: E402
    duration_minutes, etc_items, load_result_name_map, outs_from_kbodata_inning,
    outs_from_text_inning, parse_etc_item, parse_game_id, position_code, split_pa_codes, text_to_codes,
)
from etl.player_mapper import PlayerMapper  # noqa: E402
from etl.reference import Reference  # noqa: E402


def test_game_id():
    d, away, home, dh = parse_game_id("20250601_OBWO0")
    assert (d.isoformat(), away, home, dh) == ("2025-06-01", "OB", "WO", 0)


def test_innings_to_outs():
    assert outs_from_kbodata_inning("61") == 19   # 6⅓
    assert outs_from_kbodata_inning("02") == 2    # ⅔
    assert outs_from_kbodata_inning("100") == 30  # 10이닝
    assert outs_from_text_inning("6 1/3") == 19
    assert outs_from_text_inning("1/3") == 1
    assert outs_from_text_inning("9") == 27


def test_pa_code_split():
    assert split_pa_codes("10137000") == [1013, 7000]
    assert split_pa_codes("-") == []
    assert split_pa_codes(2000) == [2000]
    assert split_pa_codes("0") == []


def test_text_codes_match_kbodata_config():
    m = load_result_name_map()
    assert text_to_codes("좌중안", m) == [1020]
    assert text_to_codes("좌안/삼진", m) == [1019, 2000]
    assert text_to_codes("三비", m) == [7002]  # 2010년 이전 한자 표기


def test_position_and_duration():
    assert position_code("타중") == "H8"
    assert position_code("H8") == "H8"
    assert position_code("") is None
    assert duration_minutes("3:05") == 185


def test_etc_parsing():
    assert etc_items("김재호(2회) 페르난데스(5회)") == ["김재호(2회)", "페르난데스(5회)"]
    assert etc_items(["김준상(1회", "정수빈(3회)"]) == ["김준상(1회)", "정수빈(3회)"]
    r = parse_etc_item("임종성2(4 6회)")
    assert (r["name"], r["innings"], r["count"]) == ("임종성", [4, 6], 2)
    r = parse_etc_item("양의지12호(4회2점 김광현)")
    assert (r["name"], r["innings"], r["count"]) == ("양의지", [4], 1)
    r = parse_etc_item("최정2(3회1점 5회2점)")
    assert r["innings"] == [3, 5]


def test_reference_team_and_stadium():
    ref = Reference.load()
    assert ref.team_id("SSG", 2021) == "SK"
    assert ref.team_id("SK", 2015) == "SK"
    assert ref.team_id("넥센", 2015) == "WO"
    assert ref.team_id("두산", 2025) == "OB"
    assert ref.stadium_id("대구", 2015) == 3
    assert ref.stadium_id("대구", 2016) == 4
    assert ref.stadium_id("없는구장", 2025) is None
    assert ref.team_id("두산 베어스", 2026) == "OB"
    assert ref.team_id("SK 와이번스", 2020) == "SK"
    assert ref.team_id("SSG 랜더스", 2025) == "SK"
    assert ref.team_id("", 2025) is None


def test_player_mapper_rules():
    m = PlayerMapper()
    m.add(2025, "SS", 1, "이승현", is_batter=False, is_pitcher=True)
    m.add(2025, "SS", 2, "이승현", is_batter=False, is_pitcher=True)
    m.add(2025, "SS", 3, "김지찬", is_batter=True)
    m.add(2025, "SS", 4, "김지찬", is_batter=False, is_pitcher=True)
    m.add(2025, "OB", 5, "페르난데스", is_batter=True)
    m.add(2025, "LG", 6, "오스틴", is_batter=True)
    assert m.match(2025, "OB", "페르난데", "batter").method == "prefix"
    assert m.match(2025, "SS", "김지찬", "batter").player_id == 3          # 타자/투수로 구분
    assert m.match(2025, "SS", "이승현", "pitcher").method == "ambiguous"   # 같은 팀 투수 동명이인
    m.game_dates[2].add("2025-06-01")
    r = m.match(2025, "SS", "이승현", "pitcher", "2025-06-01")
    assert (r.player_id, r.method) == (2, "gamelog")                        # 출전 일자로 구분
    assert m.match(2025, "KT", "오스틴", "batter").method == "other_team"
    assert m.match(2025, "KT", "없는선수", "batter").method == "unmatched"
    m.overrides[(2025, "SS", "이승현")] = 1
    assert m.match(2025, "SS", "이승현", "pitcher").player_id == 1


def test_pa_result_reference_is_consistent():
    """타석결과코드 기준표: 모든 코드가 유형을 가지고, 유형의 집계 플래그가 서로 모순되지 않는다"""
    types = {r["result_type"]: r for r in csv.DictReader(open(ROOT / "data/reference/pa_result_type.csv", encoding="utf-8"))}
    codes = list(csv.DictReader(open(ROOT / "data/reference/pa_result_code.csv", encoding="utf-8")))
    assert len(codes) == 179
    for c in codes:
        t = types[c["result_type"]]
        assert (int(t["total_bases"]) > 0) == (t["is_hit"] == "1")
        assert not (t["is_hit"] == "1" and t["is_at_bat"] == "0")
    by_code = {int(c["result_code"]): c for c in codes}
    assert by_code[1020]["result_name"] == "좌중안" and by_code[1020]["spray_dir"] == "LC"
    assert by_code[1300]["result_type"] == "HOME_RUN"
    assert by_code[5005]["result_type"] == "SAC_FLY"
    assert types["SAC_FLY"]["is_at_bat"] == "0" and types["REACHED_ON_ERROR"]["is_at_bat"] == "1"



def test_current_profile_is_not_historical_membership(tmp_path):
    from crawl.common import write_csv, read_csv
    from etl.crawl_to_tables import build
    data, out = tmp_path / "source", tmp_path / "load"
    write_csv(data / "player_season_team.csv", [
        {"player_id": 54205, "season": 2025, "team_id": "OB", "name": "여동건", "is_batter": 1},
        {"player_id": 54205, "season": 2026, "team_id": "OB", "name": "여동건", "is_batter": 1},
    ], ["player_id", "season", "team_id", "name", "is_batter"])
    profile = {"player_id": 54205, "player_name": "여동건", "team_name": "상무", "team_id": "",
               "uniform_no": "01", "salary_season": 2026, "salary_10k_krw": 3000,
               "height_cm": 0, "weight_kg": 0,
               "crawled_at": "2026-11-06T12:00:00+09:00", "source_url": "https://www.koreabaseball.com/Record/Player/HitterDetail/Basic.aspx?playerId=54205"}
    write_csv(data / "players.csv", [profile], list(profile))
    build(data, out)
    player = read_csv(out / "player.csv")[0]
    assert player["height_cm"] == player["weight_kg"] == ""
    assert player["current_team_name"] == "상무"
    assert player["current_uniform_no"] == "01"
    assert "playerId=54205" in player["profile_source_url"]
    assert all(r["team_id"] == "OB" and not r["uniform_no"] for r in read_csv(out / "player_season.csv"))
    assert read_csv(out / "player_salary.csv")[0]["season"] == "2026"
    # Even a matching team and year cannot prove the season's historical uniform.
    profile["team_id"], profile["team_name"] = "OB", "두산 베어스"
    write_csv(data / "players.csv", [profile], list(profile))
    build(data, out)
    assert all(not r["uniform_no"] for r in read_csv(out / "player_season.csv"))


def test_player_mapper_position_and_match_override():
    m = PlayerMapper()
    m.add(2025, "WO", 50167, "이주형", is_batter=True)
    m.add(2025, "WO", 51302, "이주형", is_batter=True)
    m.add(2025, "SS", 62360, "김태훈", is_batter=True, is_pitcher=True)
    m.add(2025, "SS", 65040, "김태훈", is_batter=True)
    # 프로필이 없으면 포지션으로 판단하지 않는다
    assert m.match(2025, "WO", "이주형", "batter", positions="8").method == "ambiguous"
    m.profile_position.update({50167: "외야수", 51302: "내야수", 62360: "투수", 65040: "외야수"})
    r = m.match(2025, "WO", "이주형", "batter", positions="8")            # 중견수 → 외야수
    assert (r.player_id, r.method) == (50167, "position")
    assert m.match(2025, "WO", "이주형", "batter", positions="H6").player_id == 51302  # 대타 후 유격수
    assert m.match(2025, "WO", "이주형", "batter", positions="H").method == "ambiguous"  # 둘 다 야수
    assert m.match(2025, "SS", "김태훈", "batter", positions="H").player_id == 65040     # 대타 → 투수 제외
    assert m.match(2025, "SS", "김태훈", "pitcher").player_id == 62360
    # 경기별 예외가 시즌 예외보다 먼저
    m.overrides[(2025, "WO", "이주형")] = 50167
    m.match_overrides[("20250601_OBWO0", "WO", "이주형")] = 51302
    assert m.match(2025, "WO", "이주형", "batter", match_id="20250601_OBWO0").player_id == 51302
    assert m.match(2025, "WO", "이주형", "batter", match_id="20250602_OBWO0").player_id == 50167


def _run_converter(players: Path, out: Path, *extra: str) -> int:
    from etl import kbodata_to_tables
    raw = ROOT / "tests/fixtures/synthetic/raw_games.json"
    return kbodata_to_tables.main([str(raw), "--players", str(players), "--out", str(out),
                                   "--overrides", str(out / "_none.csv"), "--game-dates", str(out / "_none.csv"),
                                   "--profiles", str(out / "_none.csv"), *extra])


def _status(out: Path) -> str:
    with open(out / "_load_status.csv", encoding="utf-8", newline="") as f:
        return next(csv.DictReader(f))["status"]


def test_converter_blocks_load_when_player_is_unmatched(tmp_path):
    full = ROOT / "tests/fixtures/synthetic/data/player_season_team.csv"
    out = tmp_path / "load"
    assert _run_converter(full, out) == 0
    assert _status(out) == "ok" and (out / "batter_match.csv").exists()

    # 타자 한 명을 매핑표에서 빼면: 종료 코드 1, 적재용 CSV 없음(이전 실행 것도 삭제), 상태 blocked
    lines = full.read_text(encoding="utf-8").splitlines()
    missing = tmp_path / "players_missing.csv"
    missing.write_text("\n".join(l for l in lines if ",900102," not in l) + "\n", encoding="utf-8")
    assert _run_converter(missing, out) == 1
    assert _status(out) == "blocked"
    assert not any((out / f"{t}.csv").exists() for t in ("match", "batter_match", "pitcher_match"))
    with open(out / "_unmatched_players.csv", encoding="utf-8", newline="") as f:
        assert [r["name"] for r in csv.DictReader(f)] and "적재 중단" in (out / "_kbodata_report.md").read_text()

    # 매핑표 자체가 없어도 성공으로 끝나면 안 된다
    assert _run_converter(tmp_path / "없는파일.csv", tmp_path / "load2") == 1
    assert _status(tmp_path / "load2") == "blocked"


def test_converter_blocks_load_on_unknown_pa_code(tmp_path):
    import json
    games = json.loads((ROOT / "tests/fixtures/synthetic/raw_games.json").read_text(encoding="utf-8"))
    games[0]["contents"]["away_batter"][0]["i_1"] = "9999"   # 코드표에 없는 타석 결과
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(games, ensure_ascii=False), encoding="utf-8")
    from etl import kbodata_to_tables
    out = tmp_path / "load"
    rc = kbodata_to_tables.main([str(raw), "--players", str(ROOT / "tests/fixtures/synthetic/data/player_season_team.csv"),
                                 "--out", str(out), "--profiles", str(tmp_path / "_none.csv")])
    assert rc == 1 and _status(out) == "blocked"
    assert "9999" in (out / "_kbodata_report.md").read_text(encoding="utf-8")
