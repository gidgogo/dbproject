# 8-부록. 표준 용어 목록 (자동 생성)

> 컬럼 COMMENT의 '논리명'을 모은 것. 같은 논리명에 물리명이나 자료형이 둘 이상이면 ⚠️ 표시 → 통일 검토

| 논리명(용어) | 물리명 | 도메인/자료형 | 설명(대표) | 사용 테이블 |
|---|---|---|---|---|
| 2루타 | doubles | d_total | 2B | season_batting_official |
| 3루타 | triples | d_total | 3B | season_batting_official |
| 4사구 | walks_hbp | d_count | B (볼넷+몸에 맞는 공) | match_team, pitcher_match |
| KBO경기ID | kbo_match_id | varchar(13) | KBO 게임센터 G_ID (밑줄 제거, 생성 컬럼) | match |
| OPS | ops | d_slg | 출루율+장타율 | season_batting_official |
| WHIP | whip | d_era | (피안타+볼넷)/이닝 | season_pitching_official |
| 개시시각 | start_time | time | 경기 시작 시각 | match |
| 게임차 | games_behind | numeric(4,1) | 1위와의 게임차 | team_rank_official |
| 결과명 | result_name | varchar(10) | 박스스코어 표기 (예: 좌중안, 유땅, 삼진) | pa_result_code |
| 결과유형명 | result_type_name | varchar(20) | 한글 이름 | pa_result_type |
| 결과유형코드 | result_type | varchar(20) | SINGLE, DOUBLE, STRIKEOUT, GROUND_OUT 등 | pa_result_type, pa_result_code |
| 결과코드 | result_code | integer | kbodata 4자리 코드 | pa_result_code, plate_appearance |
| 경기ID | match_id | d_match_id | YYYYMMDD_원정팀코드홈팀코드더블헤더 (예: 20250601_OBWO0) | match, match_team, inning_score, batter_match, plate_appearance, pitcher_match, match_event, match_umpire |
| 경기구분 | series_id | integer | KBO srId (0 정규시즌, 1 시범경기, 3~7 포스트시즌) | match |
| 경기수 | games | d_total | G | season_batting_official, season_pitching_official, team_rank_official |
| 경기시간 | duration_min | integer | 분 단위 (3:05 → 185) | match |
| 경기일자 | match_date | date | 경기 날짜 | match |
| 경력 | career | varchar(200) | 출신교·경력 원문 (예: 발산초-덕수중-구리인창고). 화면 표시용 문자열 | player |
| 고의4구 | intentional_walks | d_total | IBB | season_batting_official |
| 관중수 | attendance | integer | 명 (무관중 경기는 0) | match |
| 구장ID | stadium_id | integer | 인조 식별자(자동 증가) | stadium, match |
| 구장명 | stadium_name | varchar(40) | 정식 명칭 | stadium |
| 기록ID | event_id | bigint | 인조 식별자(자동 증가) | match_event |
| 기록유형 | event_type | varchar(10) | 박스스코어 항목명 그대로 | match_event_type, match_event |
| 기준일 | as_of_date | date | 순위 기준 날짜 | team_rank_official |
| 대표팀명 | team_name | varchar(30) | 현재 정식 팀명 | team |
| 더블헤더번호 | doubleheader_no | integer | 0 일반, 1 1차전, 2 2차전 | match |
| 돔구장여부 | is_dome | boolean | 지붕이 있는 구장이면 true | stadium |
| 득점 | runs | d_count, d_total | R | match_team, batter_match, season_batting_official |
| 등판순서 | appearance_seq | integer | 1이 선발 | pitcher_match |
| 라인업순서 | lineup_seq | integer | 박스스코어 행 순서 (선발 다음에 교체 선수) | batter_match |
| 루타 | total_bases | d_total | TB | season_batting_official |
| 루타수 | total_bases | integer | 1루타 1 ~ 홈런 4 | pa_result_type |
| 무 | draws | d_total | D | team_rank_official |
| 병살여부 | is_double_play | boolean | 병살타·삼중살 | pa_result_type |
| 병살타 | gidp | d_total | GDP | season_batting_official |
| 볼넷 | walks | d_total | BB | season_batting_official, season_pitching_official |
| 볼넷여부 | is_walk | boolean | 볼넷·고의4구 | pa_result_type |
| 블론세이브 | blown_saves | d_total | BSV | season_pitching_official |
| 사구 | hbp | d_total | HBP | season_batting_official, season_pitching_official |
| 사구여부 | is_hbp | boolean | 몸에 맞는 공 | pa_result_type |
| 삼진 | strikeouts | d_total | SO | season_batting_official |
| 삼진여부 | is_strikeout | boolean | 삼진·스트라이크 낫아웃 | pa_result_type |
| 상대타자수 | batters_faced | d_count, d_total | TBF | pitcher_match, season_pitching_official |
| 상세 | detail | varchar(100) | 괄호 안 내용 (예: 4회2점 김광현) | match_event |
| 생년월일 | birth_date | date | 생년월일 | player |
| 선수ID | player_id | d_player_id | KBO playerId | player, player_season, player_salary, batter_match, plate_appearance, pitcher_match, match_event, season_batting_official, season_pitching_official |
| 선수명 | player_name | d_person_name | 현재 등록 이름 | player |
| 세이브 | saves | d_total | SV | season_pitching_official |
| 수용인원 | capacity | integer | 좌석 수 (모르면 NULL) | stadium |
| 수집일시 | crawled_at | timestamptz | 기록실에서 받은 시각 | season_batting_official, season_pitching_official, team_rank_official |
| 순번 | seq | integer | 같은 경기·같은 유형 안에서의 순서 | match_event |
| 순위 | rank | integer | 1~10 | team_rank_official |
| 승 | wins | d_total | W | season_pitching_official, team_rank_official |
| 승률 | win_pct | d_rate | 승/(승+패) | team_rank_official |
| 승패 | result | varchar(1) | W 승, L 패, D 무 | match_team |
| 승패세홀 | decision | varchar(1) | W 승, L 패, S 세이브, H 홀드, 없으면 NULL | pitcher_match |
| 시즌 | season | d_season | 연도 | team_season, player_season, player_salary, match, season_batting_official, season_pitching_official, team_rank_official |
| 시즌등번호 | uniform_no | varchar(3) | 별도 시즌 근거가 있을 때만 입력. 현재 프로필의 등번호는 player.current_uniform_no에 저장 | player_season |
| 시즌팀명 | team_name | varchar(30) | 그 시즌의 정식 팀명 (예: 2020 SK 와이번스, 2021 SSG 랜더스) | team_season |
| 시즌표기명 | name_in_season | d_person_name | 그 시즌 기록실 표기 이름 (개명·외국인 이름 축약 대응) | player_season |
| 신장 | height_cm | integer | cm | player |
| 실점 | runs_allowed | d_count, d_total | R | pitcher_match, season_pitching_official |
| 실책 | errors | d_count | E | match_team |
| 심판ID | umpire_id | integer | 인조 식별자(자동 증가) | umpire, match_umpire |
| 심판명 | umpire_name | d_person_name | 이름 (동명이인이 나오면 구분 규칙 필요) | umpire |
| 아웃카운트 | outs_recorded | d_outs | 이닝×3 (6⅓이닝 = 19). kbodata 이닝 61 → 19 | pitcher_match, season_pitching_official |
| 안타 | hits | d_count, d_total | H | match_team, batter_match, season_batting_official |
| 안타여부 | is_hit | boolean | 안타면 true | pa_result_type |
| 약칭 | short_name | varchar(10) | 박스스코어·kbodata 팀명 표기 (두산, SSG, 키움 등). 이름→팀ID 매핑 키 | team_season |
| 연고지 | city | varchar(20) | 연고 도시 | team |
| 연봉(달러) | salary_usd | integer | 외국인 선수 달러 표기 | player_salary |
| 연봉(원화) | salary_10k_krw | integer | 만원 단위 | player_salary |
| 연봉원문 | source_text | varchar(30) | 상세 페이지 표기 그대로 (예: 52000만원) | player_salary |
| 연속 | streak | varchar(10) | 원문 (예: 3승) | team_rank_official |
| 영문명 | name_en | varchar(30) | 영문 이름 | match_event_type |
| 완봉 | shutouts | d_total | SHO | season_pitching_official |
| 완투 | complete_games | d_total | CG | season_pitching_official |
| 원문 | raw_text | varchar(200) | kbodata ETC_info 원문 조각 | match_event |
| 원문선수명 | player_name_raw | d_person_name | 박스스코어 표기 이름 | match_event |
| 원정팀ID | away_team_id | d_team_id | (원정팀ID, 시즌)이 팀시즌(FK) | match |
| 은퇴여부 | is_retired | boolean | 은퇴 선수 페이지에서 수집했으면 true | player |
| 이닝 | inning | d_inning | 1~18 | inning_score, plate_appearance, match_event |
| 이닝내순번 | seq_in_inning | integer | 한 이닝에 두 번 이상 타석에 서면 1, 2 ... | plate_appearance |
| 이닝득점 | runs | d_count | 그 이닝 득점 (공격하지 않은 이닝은 행이 없음) | inning_score |
| 일련번호 | id | bigint | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_team_season_key | team_season, player_season, player_salary, match_team, inning_score, batter_match, plate_appearance, pitcher_match, match_umpire, season_batting_official, season_pitching_official, team_rank_official |
| 입단계약금 | signing_bonus_10k | integer | 만원 단위 (원화가 아니면 NULL) | player |
| 입단연도 | join_year | d_season | 입단정보에서 추출한 연도 | player |
| 입단정보 | join_info | varchar(30) | 입단년도 원문 (예: 19KIA) | player |
| 자책점 | earned_runs | d_count, d_total | ER | pitcher_match, season_pitching_official |
| 장타율 | slg | d_slg | SLG | season_batting_official |
| 종료시각 | end_time | time | 경기 종료 시각 | match |
| 지명연도 | draft_year | d_season | 지명정보에서 추출한 연도 | player |
| 지명정보 | draft_info | varchar(60) | 지명 순위 원문 (예: 17 KIA 2차 4라운드 34순위) | player |
| 지역 | city | varchar(20) | 구장 소재 도시 | stadium |
| 처리수비위치 | fielder_pos | integer | 타구를 처리한 첫 수비수 (1 투수 ~ 9 우익수) | pa_result_code |
| 첫시즌 | first_season | d_season | 전신 구단을 포함한 KBO 리그 첫 참가 시즌 | team |
| 체중 | weight_kg | integer | kg | player |
| 최근10경기 | last10 | varchar(20) | 원문 (예: 6승1무3패) | team_rank_official |
| 출루율 | obp | d_rate | OBP | season_batting_official |
| 퀄리티스타트 | quality_starts | d_total | QS | season_pitching_official |
| 타격방향 | bats | d_hand | L 좌타, R 우타, S 양타 | player |
| 타구방향 | spray_dir | varchar(2) | 스프레이 차트 구역 L 좌, LC 좌중, C 중, RC 우중, R 우 | pa_result_code |
| 타구종류 | batted_ball | varchar(2) | GB 땅볼, FB 뜬공, LD 직선타, BU 번트 (안타는 kbodata에 정보 없음) | pa_result_type |
| 타석 | plate_appearances | d_total | PA | season_batting_official |
| 타수 | at_bats | d_count, d_total | AB | batter_match, season_batting_official |
| 타수포함여부 | is_at_bat | boolean | 타수(AB)에 들어가면 true | pa_result_type |
| 타순 | batting_order | integer | 1~9. kbodata가 타순 열을 버리므로 현재 NULL (❓ 원본 보강 필요) | batter_match |
| 타율 | avg | d_rate | AVG | season_batting_official |
| 타자기록여부 | is_batter | boolean | 기록실 타자 목록에 있으면 true | player_season |
| 타점 | rbi | d_count, d_total | RBI | batter_match, season_batting_official |
| 탈삼진 | strikeouts | d_count, d_total | SO | pitcher_match, season_pitching_official |
| 투구손 | throws | d_hand | L 좌투, R 우투 | player |
| 투구수 | pitches | d_count, d_total | NP (과거 경기는 없을 수 있음) | pitcher_match, season_pitching_official |
| 투수기록여부 | is_pitcher | boolean | 기록실 투수 목록에 있으면 true | player_season |
| 팀ID | team_id | d_team_id | KBO 팀코드. 구단명이 바뀌어도 유지된다 (SK→SSG도 SK) | team, team_season, player_season, match_team, inning_score, batter_match, pitcher_match, match_event, season_batting_official, season_pitching_official, team_rank_official |
| 패 | losses | d_total | L | season_pitching_official, team_rank_official |
| 평균자책점 | era | d_era | ERA | season_pitching_official |
| 포지션 | position | varchar(10) | 투수/포수/내야수/외야수 (상세 페이지 기준) | player |
| 포지션이력 | positions | varchar(12) | kbodata 포지션 코드 문자열 (예: H8 = 대타 후 중견수). 표시용 | batter_match |
| 표기순서 | listed_order | integer | 박스스코어 나열 순서 (❓ 주심/누심 구분 규칙 확인 필요) | match_umpire |
| 프로필수집일시 | profile_crawled_at | timestamptz | 상세 페이지를 받은 시각 | player |
| 프로필출처 | profile_source_url | text | KBO playerId가 포함된 상세 페이지 URL | player |
| 피안타 | hits_allowed | d_count, d_total | H | pitcher_match, season_pitching_official |
| 피타수 | at_bats | d_count | 상대 타수 | pitcher_match |
| 피홈런 | home_runs_allowed | d_count, d_total | HR | pitcher_match, season_pitching_official |
| 현재등번호 | current_uniform_no | varchar(3) | 프로필 수집 시점의 등번호. 과거 시즌에 소급하지 않음 | player |
| 현재소속명 | current_team_name | varchar(60) | 프로필 수집 시점의 소속 원문. 상무 등 KBO 10개 구단 외 소속도 보존하며 과거 시즌 소속과 구분 | player |
| 홀드 | holds | d_total | HLD | season_pitching_official |
| 홈구장ID | home_stadium_id | integer | 그 시즌 주 홈구장(FK) | team_season |
| 홈런 | home_runs | d_total | HR | season_batting_official |
| 홈원정구분 | home_away | varchar(1) | H 홈, A 원정. 경기의 팀ID에서 유도되지만 조회 편의를 위해 저장하고 트리거로 일관성을 보장 | match_team |
| 홈팀ID | home_team_id | d_team_id | (홈팀ID, 시즌)이 팀시즌(FK) | match |
| 희생번트 | sac_bunts | d_total | SAC | season_batting_official |
| 희생번트여부 | is_sac_bunt | boolean | 희생번트(실책·야수선택 포함) | pa_result_type |
| 희생플라이 | sac_flies | d_total | SF | season_batting_official |
| 희생플라이여부 | is_sac_fly | boolean | 희생플라이 | pa_result_type |
