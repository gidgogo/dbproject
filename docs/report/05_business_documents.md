# 5. 업무 문서 리스트 / 별첨 3. 수집한 업무 문서

> 공동 작성 항목 중 데이터 수집 부분 (이성수). 🟡 캡처는 맥에서 수집할 때 함께 저장 (`crawl/probe_kbo.py`가 원본 HTML을 `data/raw/probe/`에 남김)

"업무 문서" = 이 시스템이 다루는 실제 야구 기록 업무에서 쓰이는 문서·화면. 엔터티와 속성을 도출한 근거다.

## 5.1 업무 문서 목록

| 번호 | 업무 문서 | 출처 (URL) | 담긴 정보 | 도출한 엔터티 | 수집 방법 |
|---|---|---|---|---|---|
| D-01 | 경기 일정표 | koreabaseball.com/Schedule/Calendar.aspx | 날짜, 원정·홈 팀, 취소 여부 | 경기 | kbodata |
| D-02 | 박스스코어 — 스코어보드 | 게임센터 /Schedule/GameCenter/Main.aspx (리뷰) | 이닝별 점수, R·H·E·B, 승패 | 팀경기기록, 이닝득점 | kbodata |
| D-03 | 박스스코어 — 타자 기록 | 〃 | 타순·포지션·이닝별 타격 결과·타수·안타·타점·득점 | 타자경기기록, 타석, 타석결과코드 | kbodata |
| D-04 | 박스스코어 — 투수 기록 | 〃 | 등판·결과·이닝·투구수·피안타·4사구·삼진·실점·자책 | 투수경기기록 | kbodata |
| D-05 | 박스스코어 — 기타 기록 | 〃 | 결승타·홈런·2루타·도루·실책·병살·심판·구장·관중·시간 | 경기기타기록, 심판, 경기심판, 구장 | kbodata |
| D-06 | 기록실 — 타자 기본기록 1·2 | /Record/Player/HitterBasic/Basic1.aspx, Basic2.aspx | 시즌 누적 타격 기록, playerId | 선수시즌소속, 시즌타자기록_공식 | crawl/kbo_records.py |
| D-07 | 기록실 — 투수 기본기록 1·2 | /Record/Player/PitcherBasic/Basic1.aspx, Basic2.aspx | 시즌 누적 투구 기록, playerId | 선수시즌소속, 시즌투수기록_공식 | crawl/kbo_records.py |
| D-08 | 선수 상세 (현역) | /Record/Player/HitterDetail/Basic.aspx?playerId= (투수 PitcherDetail) | 생년월일·투타·신장체중·경력·계약금·연봉·지명·입단 | 선수, 선수연봉 | crawl/kbo_profiles.py |
| D-09 | 선수 상세 (은퇴) | /Record/Retire/Hitter.aspx?playerId= (Pitcher.aspx) | 〃 | 선수 | crawl/kbo_profiles.py |
| D-10 | 선수 일자별 기록 | /Record/Player/HitterDetail/Daily.aspx?playerId= | 출전 날짜 | (동명이인 구분용) | crawl/kbo_gamelogs.py |
| D-11 | 팀 순위 | /Record/TeamRank/TeamRankDaily.aspx | 순위·승·패·무·승률·게임차·최근10경기·연속 | 팀순위_공식 | crawl/kbo_team_rank.py |
| D-12 | 문자중계 | 네이버 스포츠 (api-gw.sports.naver.com 일정·relay) | 투구별 구종·구속·결과·카운트·위치 | 투구, 구종, 투구결과 | crawl/naver_relay.py |
| D-13 | 구단 정보 | KBO 구단 소개 / 구단 홈페이지 | 팀명 변경 이력, 연고지, 홈구장 | 팀, 팀시즌, 구장 | 직접 입력 (data/reference) |

## 5.2 별첨 3 — 수집 기록 (맥에서 수집할 때 채우기)

| 번호 | 수집일 | 범위 | 요청 수 | 결과 파일 | 캡처 |
|---|---|---|---|---|---|
| D-02~05 | | 2025-06-01 (5경기) 테스트 | | ~/Desktop/data/test/ | |
| D-06~07 | | 2025 시즌 | | data/player_season_team.csv, season_*.csv | |
| D-08~09 | | 2025 시즌 선수 | | data/players.csv | |
| D-11 | | 2025 시즌 최종 | | data/team_rank.csv | |
| D-12 | | 2025 시즌 한 팀 | | data/pitches_2025_<팀>.csv | |

## 5.3 출처 표기 (보고서·발표 공통)

- 경기·선수 기록: KBO 공식 홈페이지 (www.koreabaseball.com)
- 박스스코어 수집 도구: kbo-data (GitHub dev-bearabbit/kbo-data, MIT License)
- 투구 데이터: 네이버 스포츠 문자중계
- 데이터는 수업 프로젝트 용도로만 사용함
