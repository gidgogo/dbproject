"""etl/ 순수 함수 단위 테스트 (네트워크·DB 불필요)"""
import csv
import pytest
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


def test_overlapping_pitch_files_are_deduplicated_and_conflicts_rejected(tmp_path):
    from etl.pitches_to_tables import COLS, convert
    from crawl.common import write_csv, read_csv
    row = {"game_id": "20250601_OBWO0", "pitch_seq": "1", "pitcher_id": "10", "batter_id": "20",
           "pitch_type_ko": "직구", "speed_kmh": "145"}
    a, b, out = tmp_path / "OB.csv", tmp_path / "WO.csv", tmp_path / "pitch.csv"
    write_csv(a, [row], COLS)
    write_csv(b, [row], COLS)
    stats = convert([a, b], out, {"직구"})
    assert stats["kept"] == 1 and stats["duplicates_removed"] == 1
    assert len(read_csv(out)) == 1
    before = out.read_bytes()
    write_csv(b, [{**row, "speed_kmh": "146"}], COLS)
    with pytest.raises(ValueError, match="서로 다릅니다"):
        convert([a, b], out, {"직구"})
    assert out.read_bytes() == before
