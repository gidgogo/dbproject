# 8. 용어 사전 (필수)

> 담당: 이성수 · 초안 v0 (2026-11-05)
> - 8.1 표준 단어: 컬럼 이름을 만들 때 쓰는 단어와 영문 약어 (사람이 정리)
> - 8.2 야구 기록 용어: 보고서·화면에 나오는 기록 용어의 뜻과 계산 규칙
> - 8.3 표준 용어(논리명 ↔ 물리명): `08_glossary_terms.md` (DDL 주석에서 자동 생성)

## 8.1 표준 단어

| 단어 (논리) | 영문 | 물리명에 쓰는 형태 | 비고 |
|---|---|---|---|
| 팀 | Team | team | KBO 구단 |
| 시즌 | Season | season | 연도 |
| 구장 | Stadium | stadium | |
| 선수 | Player | player | |
| 경기 | Game | match | |
| 심판 | Umpire | umpire | |
| 타자 | Batter | batter | |
| 투수 | Pitcher | pitcher | |
| 타석 | Plate Appearance | pa / plate_appearance | 약어 PA |
| 이닝 | Inning | inning | |
| 기록 | Record | (생략) / official | 기록실 공식 값은 `_official` |
| 식별자 | Identifier | _id | 예: player_id |
| 코드 | Code | _code | 예: result_code |
| 번호 | Number | _no | 예: uniform_no, doubleheader_no |
| 순서 / 순번 | Sequence | _seq | 예: lineup_seq, appearance_seq |
| 여부 | Flag | is_ 접두어 | 예: is_retired |
| 명 / 이름 | Name | _name | |
| 일자 | Date | _date | |
| 시각 | Time | _time | |
| 일시 | Timestamp | _at | 예: crawled_at |
| 수(횟수) | Count | 복수형 | 예: hits, walks |
| 비율 | Rate | 지표 약어 | avg, obp, slg, era |
| 금액 | Amount | 단위 접미어 | salary_10k_krw(만원), salary_usd |
| 홈 / 원정 | Home / Away | home_ / away_ | |
| 공식 | Official | _official | KBO 기록실 저장 값 (직접 조회·검증용) |

## 8.2 야구 기록 용어

| 용어 | 약어 | 물리명 | 뜻 · 계산 |
|---|---|---|---|
| 타석 | PA | plate_appearances | 타자가 타격을 마친 횟수 전체 (볼넷·사구·희생타 포함) |
| 타수 | AB | at_bats | 타석 − (볼넷·사구·희생번트·희생플라이·타격방해) |
| 안타 | H | hits | 1루타 + 2루타 + 3루타 + 홈런 |
| 루타 | TB | total_bases | 1루타×1 + 2루타×2 + 3루타×3 + 홈런×4 |
| 타점 | RBI | rbi | 타격으로 들어온 점수 |
| 득점 | R | runs | 홈을 밟은 횟수 |
| 볼넷 / 고의4구 | BB / IBB | walks / intentional_walks | 고의4구는 볼넷에 포함해 센다 |
| 몸에 맞는 공(사구) | HBP | hbp | |
| 4사구 | — | walks_hbp | 볼넷 + 사구 (kbodata·스코어보드 B 항목은 둘을 합친 값) |
| 희생번트 / 희생플라이 | SAC / SF | sac_bunts / sac_flies | 타수에 포함되지 않음 |
| 병살타 | GDP | gidp | 한 타구로 두 명 아웃 |
| 타율 | AVG | avg | H / AB |
| 출루율 | OBP | obp | (H + BB + HBP) / (AB + BB + HBP + SF) |
| 장타율 | SLG | slg | TB / AB |
| OPS | OPS | ops | OBP + SLG |
| 규정타석 | — | (뷰 계산) | 팀 경기 수 × 3.1. 타율 순위·백분위 대상 기준 |
| 이닝(투구) | IP | outs_recorded | **아웃카운트로 저장**. 6⅓이닝 = 19아웃, 표시는 `fn_ip_display` |
| 상대타자수 | TBF | batters_faced | 투수가 상대한 타자 수 |
| 피안타 / 피홈런 | H / HR | hits_allowed / home_runs_allowed | |
| 실점 / 자책점 | R / ER | runs_allowed / earned_runs | 자책점: 실책 등을 빼고 투수 책임인 실점 |
| 평균자책점 | ERA | era | 자책점 × 9 / 이닝 = 자책점 × 27 / 아웃카운트 |
| WHIP | WHIP | whip | (피안타 + 볼넷) / 이닝. 우리 계산값(`whip_incl_hbp`)은 사구 포함 근사 |
| 승 / 패 / 세이브 / 홀드 | W / L / SV / HLD | decision | 경기마다 투수 1명씩 결정 (홀드는 여러 명 가능) |
| 퀄리티스타트 | QS | quality_starts | 선발 6이닝 이상 + 자책 3 이하 |
| 승률 | WPCT | win_pct | 승 / (승 + 패) |
| 게임차 | GB | games_behind | ((1위 승 − 승) + (패 − 1위 패)) / 2 |
| 더블헤더 | DH | doubleheader_no | 같은 날 같은 두 팀의 2경기 (1차전 1, 2차전 2) |
| 스프레이 차트 | — | spray_dir | 타구 방향 5구역 L·LC·C·RC·R (kbodata 결과 표기의 수비 위치로 추정) |
| 박스스코어 | — | — | 경기 후 타자·투수별 기록표 (KBO 게임센터 '리뷰') |
| playerId | — | player_id | KBO 공식 홈페이지가 선수에게 부여한 번호 |

## 8.3 표준 용어 (논리명 ↔ 물리명)

`08_glossary_terms.md` 참고. DDL 컬럼 주석(`논리명: 설명`)에서 자동으로 뽑으므로 DDL과 항상 일치한다.
같은 논리명에 다른 물리명·자료형이 쓰이면 ⚠️로 표시되게 해 두었고, 초안 작성 중 발견한 두 건
(투구의 '아웃카운트' ↔ 투수의 '아웃카운트' 의미 충돌, 경기.시즌 도메인 누락)을 고쳤다.
