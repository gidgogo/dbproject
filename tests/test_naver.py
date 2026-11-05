"""네이버 문자중계 파서 테스트 (가상 JSON)"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))

from crawl.naver_parsers import final_inning, our_game_id, pitch_rows, plate_z, playable  # noqa: E402
from naver_relay_synthetic import INNINGS, SCHEDULE_GAME  # noqa: E402


def test_game_id_and_schedule_filters():
    assert our_game_id(SCHEDULE_GAME) == "20250101_OBWO0"
    assert final_inning("12회말") == 12 and final_inning("경기취소") is None
    assert playable(SCHEDULE_GAME, "OB") and not playable(SCHEDULE_GAME, "LG")
    assert not playable({**SCHEDULE_GAME, "roundCode": "kbo_e"})  # 시범경기 제외
    assert playable({**SCHEDULE_GAME, "statusInfo": "경기종료", "statusCode": "RESULT"})
    assert not playable({**SCHEDULE_GAME, "statusInfo": "경기취소", "statusCode": "CANCEL", "cancel": True})


def test_pitch_rows():
    rows = pitch_rows(INNINGS)
    # 재전송된 투구 1개, 재전송된 반이닝 블록은 빠져야 한다
    assert [(r["half"], r["at_bat_no"], r["pitch_no"]) for r in rows] == [
        ("T", 1, 1), ("T", 1, 2), ("T", 1, 3), ("T", 2, 1), ("T", 2, 2), ("B", 3, 1), ("B", 3, 2)]
    assert [r["pitch_seq"] for r in rows] == list(range(1, 8))
    # 직전 카운트: 0-0, 1-0, 1-1 / 대타가 들어와도 0-1 유지
    assert [(r["balls"], r["strikes"]) for r in rows] == [(0, 0), (1, 0), (1, 1), (0, 0), (0, 1), (0, 0), (0, 1)]
    assert rows[4]["batter_pcode"] == "900103"           # 대타
    assert rows[2]["pa_result_text"].endswith("1루타")    # 타석 마지막 투구에 결과
    assert rows[4]["pa_result_text"].endswith("2루타")
    assert rows[0]["plate_x"] == -0.9 and rows[0]["batter_stance"] == "L"
    assert rows[6]["plate_x"] is None                    # 트래킹 없음
    assert rows[5]["outs"] == 0 and rows[0]["pitcher_pcode"] == "900211"


def test_plate_z_physics():
    # 등가속도 궤적: y0=50ft, vy0=-130ft/s, ay=26ft/s² → 플레이트 도달 약 0.40초
    z = plate_z({"y0": 50, "vy0": -130, "ay": 26, "z0": 5.6, "vz0": -6, "az": -15})
    assert 2.0 < z < 3.5
    assert plate_z({"y0": 50}) is None


def test_fetch_game_uses_inn_when_status_has_no_inning(tmp_path, monkeypatch):
    """statusInfo 에 이닝이 없으면 1회 응답의 inn(마지막 이닝)만큼 받는다. 받은 경기는 다시 받지 않는다."""
    import crawl.naver_relay as nr
    calls = []

    def fake_api_get(session, path, **params):
        calls.append(params.get("inning"))
        return {"textRelayData": {"inn": 11, "textRelays": []}}

    monkeypatch.setattr(nr, "api_get", fake_api_get)
    monkeypatch.setattr(nr, "RAW", tmp_path)
    game = {**SCHEDULE_GAME, "statusInfo": "경기종료", "statusCode": "RESULT"}
    innings = nr.fetch_game(None, 2025, game)
    assert calls == list(range(1, 12)) and sorted(innings) == list(range(1, 12))
    nr.fetch_game(None, 2025, game)          # 이어받기: 파일이 있으면 요청하지 않음
    assert len(calls) == 11
