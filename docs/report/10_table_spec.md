# 10. 테이블 기술서

> `tools/gen_erd_docs.py` 가 PostgreSQL 카탈로그(컬럼 COMMENT·제약조건)에서 자동 생성했다.
> 내용을 고칠 때는 새 Flyway 마이그레이션(V{n}__*.sql)에서 COMMENT ON 을 고친 뒤 다시 생성한다.
> Data Type 괄호 안은 논리 도메인(보고서 9장). DB에는 기본 자료형 + CHECK 로 들어가 있다.

## 10.1 팀 (team)

KBO 구단. 팀명이 바뀌어도 같은 구단이면 하나의 행 (팀명 이력은 team_season)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| team_id | 팀ID | varchar(2) (d_team_id) | Y | PK |  | KBO 팀코드. 구단명이 바뀌어도 유지된다 (SK→SSG도 SK) |
| team_name | 대표팀명 | varchar(30) | Y |  |  | 현재 정식 팀명 |
| city | 연고지 | varchar(20) | Y |  |  | 연고 도시 |
| first_season | 첫시즌 | integer (d_season) | Y |  |  | 전신 구단을 포함한 KBO 리그 첫 참가 시즌 |

**CHECK 제약**

- `team_first_season_check`: `CHECK (((first_season >= 1982) AND (first_season <= 2100)))`
- `team_team_id_check`: `CHECK (((team_id)::text ~ '^[A-Z]{2}$'::text))`

## 10.2 구장 (stadium)

경기가 열리는 야구장

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| stadium_id | 구장ID | integer | Y | PK |  | 인조 식별자(자동 증가) |
| stadium_name | 구장명 | varchar(40) | Y | UQ |  | 정식 명칭 |
| city | 지역 | varchar(20) | Y |  |  | 구장 소재 도시 |
| is_dome | 돔구장여부 | boolean | Y |  | false | 지붕이 있는 구장이면 true |
| capacity | 수용인원 | integer |  |  |  | 좌석 수 (모르면 NULL) |

**CHECK 제약**

- `ck_stadium_capacity`: `CHECK ((capacity > 0))`

## 10.3 팀시즌 (team_season)

시즌별 팀명과 홈구장 이력 (초안의 팀명이력 TEAM_NAME_HIST를 확장)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_team_season_key |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→team.team_id, UQ(업무키) |  | 팀(FK) |
| season | 시즌 | integer (d_season) | Y | UQ(업무키) |  | 연도 |
| team_name | 시즌팀명 | varchar(30) | Y |  |  | 그 시즌의 정식 팀명 (예: 2020 SK 와이번스, 2021 SSG 랜더스) |
| short_name | 약칭 | varchar(10) | Y | UQ |  | 박스스코어·kbodata 팀명 표기 (두산, SSG, 키움 등). 이름→팀ID 매핑 키 |
| home_stadium_id | 홈구장ID | integer |  | FK→stadium.stadium_id |  | 그 시즌 주 홈구장(FK) |

**참조 무결성 (FK)**

- `fk_team_season_stadium`: (home_stadium_id) → stadium(stadium_id) ON UPDATE CASCADE ON DELETE SET NULL — 비식별 관계
- `fk_team_season_team`: (team_id) → team(team_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계

**CHECK 제약**

- `team_season_season_check`: `CHECK (((season >= 1982) AND (season <= 2100)))`

## 10.4 선수 (player)

KBO playerId로 식별하는 선수 마스터. 이름은 동명이인·개명이 있어 식별자로 쓰지 않는다

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| player_id | 선수ID | integer (d_player_id) | Y | PK |  | KBO playerId |
| player_name | 선수명 | varchar(30) (d_person_name) | Y |  |  | 현재 등록 이름 |
| birth_date | 생년월일 | date |  |  |  | 생년월일 |
| height_cm | 신장 | integer |  |  |  | cm |
| weight_kg | 체중 | integer |  |  |  | kg |
| throws | 투구손 | varchar(1) (d_hand) |  |  |  | L 좌투, R 우투 |
| bats | 타격방향 | varchar(1) (d_hand) |  |  |  | L 좌타, R 우타, S 양타 |
| position | 포지션 | varchar(10) |  |  |  | 투수/포수/내야수/외야수 (상세 페이지 기준) |
| career | 경력 | varchar(200) |  |  |  | 출신교·경력 원문 (예: 발산초-덕수중-구리인창고). 화면 표시용 문자열 |
| draft_info | 지명정보 | varchar(60) |  |  |  | 지명 순위 원문 (예: 17 KIA 2차 4라운드 34순위) |
| draft_year | 지명연도 | integer (d_season) |  |  |  | 지명정보에서 추출한 연도 |
| join_info | 입단정보 | varchar(30) |  |  |  | 입단년도 원문 (예: 19KIA) |
| join_year | 입단연도 | integer (d_season) |  |  |  | 입단정보에서 추출한 연도 |
| signing_bonus_10k | 입단계약금 | integer |  |  |  | 만원 단위 (원화가 아니면 NULL) |
| is_retired | 은퇴여부 | boolean | Y |  | false | 은퇴 선수 페이지에서 수집했으면 true |
| profile_crawled_at | 프로필수집일시 | timestamptz |  |  |  | 상세 페이지를 받은 시각 |
| current_team_name | 현재소속명 | varchar(60) |  |  |  | 프로필 수집 시점의 소속 원문. 상무 등 KBO 10개 구단 외 소속도 보존하며 과거 시즌 소속과 구분 |
| current_uniform_no | 현재등번호 | varchar(3) |  |  |  | 프로필 수집 시점의 등번호. 과거 시즌에 소급하지 않음 |
| profile_source_url | 프로필출처 | text |  |  |  | KBO playerId가 포함된 상세 페이지 URL |

**CHECK 제약**

- `ck_player_bonus`: `CHECK ((signing_bonus_10k >= 0))`
- `ck_player_current_uniform`: `CHECK (((current_uniform_no)::text ~ '^[0-9]{1,3}$'::text))`
- `ck_player_height`: `CHECK (((height_cm >= 140) AND (height_cm <= 230)))`
- `ck_player_position`: `CHECK ((("position")::text = ANY ((ARRAY['투수'::character varying, '포수'::character varying, '내야수'::character varying, '외야수'::character varying])::text[])))`
- `ck_player_throws`: `CHECK (((throws)::text = ANY ((ARRAY['L'::character varying, 'R'::character varying])::text[])))`
- `ck_player_weight`: `CHECK (((weight_kg >= 40) AND (weight_kg <= 200)))`
- `player_bats_check`: `CHECK (((bats)::text = ANY ((ARRAY['L'::character varying, 'R'::character varying, 'S'::character varying])::text[])))`
- `player_draft_year_check`: `CHECK (((draft_year >= 1982) AND (draft_year <= 2100)))`
- `player_join_year_check`: `CHECK (((join_year >= 1982) AND (join_year <= 2100)))`
- `player_player_id_check`: `CHECK ((player_id > 0))`
- `player_player_name_check`: `CHECK ((length(btrim((player_name)::text)) > 0))`
- `player_throws_check`: `CHECK (((throws)::text = ANY ((ARRAY['L'::character varying, 'R'::character varying, 'S'::character varying])::text[])))`

## 10.5 선수시즌소속 (player_season)

선수가 어느 시즌에 어느 팀 소속으로 기록을 남겼는지. 시즌 중 이적하면 팀마다 한 행. 이름+팀+시즌 → 선수ID 매핑의 근거

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_player_season_key |
| player_id | 선수ID | integer (d_player_id) | Y | FK→player.player_id, UQ(업무키) |  | 선수(FK) |
| season | 시즌 | integer (d_season) | Y | FK→team_season.season, UQ(업무키) |  | 연도 |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→team_season.team_id, UQ(업무키) |  | 소속팀. (팀ID, 시즌)이 팀시즌(FK) |
| name_in_season | 시즌표기명 | varchar(30) (d_person_name) | Y |  |  | 그 시즌 기록실 표기 이름 (개명·외국인 이름 축약 대응) |
| is_batter | 타자기록여부 | boolean | Y |  | false | 기록실 타자 목록에 있으면 true |
| is_pitcher | 투수기록여부 | boolean | Y |  | false | 기록실 투수 목록에 있으면 true |
| uniform_no | 시즌등번호 | varchar(3) |  |  |  | 별도 시즌 근거가 있을 때만 입력. 현재 프로필의 등번호는 player.current_uniform_no에 저장 |

**참조 무결성 (FK)**

- `fk_player_season_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_player_season_team_season`: (team_id, season) → team_season(team_id, season) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_player_season_role`: `CHECK ((is_batter OR is_pitcher))`
- `ck_player_season_uniform`: `CHECK (((uniform_no)::text ~ '^[0-9]{1,3}$'::text))`
- `player_season_name_in_season_check`: `CHECK ((length(btrim((name_in_season)::text)) > 0))`
- `player_season_season_check`: `CHECK (((season >= 1982) AND (season <= 2100)))`

## 10.6 선수연봉 (player_salary)

연봉은 팀이 아니라 (선수, 시즌)에 종속되므로 선수시즌소속과 분리 (2NF)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_player_salary_key |
| player_id | 선수ID | integer (d_player_id) | Y | FK→player.player_id, UQ(업무키) |  | 선수(FK) |
| season | 시즌 | integer (d_season) | Y | UQ(업무키) |  | 연도 |
| salary_10k_krw | 연봉(원화) | integer |  |  |  | 만원 단위 |
| salary_usd | 연봉(달러) | integer |  |  |  | 외국인 선수 달러 표기 |
| source_text | 연봉원문 | varchar(30) |  |  |  | 상세 페이지 표기 그대로 (예: 52000만원) |

**참조 무결성 (FK)**

- `fk_player_salary_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계

**CHECK 제약**

- `ck_player_salary_amount`: `CHECK (((salary_10k_krw >= 0) AND (salary_usd >= 0)))`
- `ck_player_salary_any`: `CHECK (((salary_10k_krw IS NOT NULL) OR (salary_usd IS NOT NULL)))`
- `player_salary_season_check`: `CHECK (((season >= 1982) AND (season <= 2100)))`

## 10.7 경기 (match)

한 경기. 경기ID는 kbodata raw JSON의 id를 그대로 쓴다

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| match_id | 경기ID | varchar(14) (d_match_id) | Y | PK |  | YYYYMMDD_원정팀코드홈팀코드더블헤더 (예: 20250601_OBWO0) |
| match_date | 경기일자 | date | Y |  |  | 경기 날짜 |
| season | 시즌 | integer (d_season) | Y | FK→team_season.season | GENERATED: (EXTRACT(year FROM match_date))::integer | 경기일자의 연도 (생성 컬럼, 직접 입력 불가) |
| away_team_id | 원정팀ID | varchar(2) (d_team_id) | Y | FK→team_season.team_id |  | (원정팀ID, 시즌)이 팀시즌(FK) |
| home_team_id | 홈팀ID | varchar(2) (d_team_id) | Y | FK→team_season.team_id |  | (홈팀ID, 시즌)이 팀시즌(FK) |
| doubleheader_no | 더블헤더번호 | integer | Y |  | 0 | 0 일반, 1 1차전, 2 2차전 |
| series_id | 경기구분 | integer | Y |  | 0 | KBO srId (0 정규시즌, 1 시범경기, 3~7 포스트시즌) |
| stadium_id | 구장ID | integer |  | FK→stadium.stadium_id |  | 구장(FK). 매핑 실패 시 NULL |
| attendance | 관중수 | integer |  |  |  | 명 (무관중 경기는 0) |
| start_time | 개시시각 | time |  |  |  | 경기 시작 시각 |
| end_time | 종료시각 | time |  |  |  | 경기 종료 시각 |
| duration_min | 경기시간 | integer |  |  |  | 분 단위 (3:05 → 185) |
| kbo_match_id | KBO경기ID | varchar(13) |  | UQ | GENERATED: replace((match_id)::text, '_'::text, ''::text) | KBO 게임센터 G_ID (밑줄 제거, 생성 컬럼) |

**참조 무결성 (FK)**

- `fk_match_away_team_season`: (away_team_id, season) → team_season(team_id, season) ON UPDATE NO ACTION ON DELETE NO ACTION — 비식별 관계
- `fk_match_home_team_season`: (home_team_id, season) → team_season(team_id, season) ON UPDATE NO ACTION ON DELETE NO ACTION — 비식별 관계
- `fk_match_stadium`: (stadium_id) → stadium(stadium_id) ON UPDATE CASCADE ON DELETE SET NULL — 비식별 관계

**CHECK 제약**

- `ck_match_attendance`: `CHECK ((attendance >= 0))`
- `ck_match_doubleheader`: `CHECK (((doubleheader_no >= 0) AND (doubleheader_no <= 2)))`
- `ck_match_duration`: `CHECK ((duration_min > 0))`
- `ck_match_id_parts`: `CHECK (((match_id)::text = ((((to_char((match_date)::timestamp with time zone, 'YYYYMMDD'::text) || '_'::text) || (away_team_id)::text) || (home_team_id)::text) || doubleheader_no)))`
- `ck_match_series`: `CHECK (((series_id >= 0) AND (series_id <= 9)))`
- `ck_match_teams`: `CHECK (((away_team_id)::text <> (home_team_id)::text))`
- `match_match_id_check`: `CHECK (((match_id)::text ~ '^[0-9]{8}_[A-Z]{4}[0-9]$'::text))`
- `match_season_check`: `CHECK (((season >= 1982) AND (season <= 2100)))`

## 10.8 팀경기기록 (match_team)

경기 스코어보드의 팀별 한 줄 (R H E B)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_match_team_key |
| match_id | 경기ID | varchar(14) (d_match_id) | Y | FK→match.match_id, UQ(업무키) |  | 경기(FK) |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→team.team_id, UQ(업무키) |  | 팀(FK). 그 경기의 홈팀 또는 원정팀이어야 함(트리거로 검사) |
| home_away | 홈원정구분 | varchar(1) | Y | UQ |  | H 홈, A 원정. 경기의 팀ID에서 유도되지만 조회 편의를 위해 저장하고 트리거로 일관성을 보장 |
| result | 승패 | varchar(1) | Y |  |  | W 승, L 패, D 무 |
| runs | 득점 | integer (d_count) | Y |  |  | R |
| hits | 안타 | integer (d_count) | Y |  |  | H |
| errors | 실책 | integer (d_count) | Y |  |  | E |
| walks_hbp | 4사구 | integer (d_count) | Y |  |  | B (볼넷+몸에 맞는 공) |

**참조 무결성 (FK)**

- `fk_match_team_match`: (match_id) → match(match_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_match_team_team`: (team_id) → team(team_id) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_match_team_result`: `CHECK (((result)::text = ANY ((ARRAY['W'::character varying, 'L'::character varying, 'D'::character varying])::text[])))`
- `ck_match_team_side`: `CHECK (((home_away)::text = ANY ((ARRAY['H'::character varying, 'A'::character varying])::text[])))`
- `match_team_errors_check`: `CHECK ((errors >= 0))`
- `match_team_hits_check`: `CHECK ((hits >= 0))`
- `match_team_runs_check`: `CHECK ((runs >= 0))`
- `match_team_walks_hbp_check`: `CHECK ((walks_hbp >= 0))`

## 10.9 이닝득점 (inning_score)

스코어보드 이닝별 점수. kbodata의 i_1~i_18 반복 컬럼을 행으로 바꾼 것 (1NF)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_inning_score_key |
| match_id | 경기ID | varchar(14) (d_match_id) | Y | FK→match_team.match_id, UQ(업무키) |  | (경기ID, 팀ID)가 팀경기기록(FK) |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→match_team.team_id, UQ(업무키) |  | 공격한 팀 |
| inning | 이닝 | integer (d_inning) | Y | UQ(업무키) |  | 1~18 |
| runs | 이닝득점 | integer (d_count) | Y |  |  | 그 이닝 득점 (공격하지 않은 이닝은 행이 없음) |

**참조 무결성 (FK)**

- `fk_inning_score_match_team`: (match_id, team_id) → match_team(match_id, team_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계

**CHECK 제약**

- `inning_score_inning_check`: `CHECK (((inning >= 1) AND (inning <= 18)))`
- `inning_score_runs_check`: `CHECK ((runs >= 0))`

## 10.10 타석결과유형 (pa_result_type)

안타·삼진·땅볼 등 결과 유형과 기록 집계 규칙(타수 포함 여부, 루타 수)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| result_type | 결과유형코드 | varchar(20) | Y | PK |  | SINGLE, DOUBLE, STRIKEOUT, GROUND_OUT 등 |
| result_type_name | 결과유형명 | varchar(20) | Y |  |  | 한글 이름 |
| batted_ball | 타구종류 | varchar(2) |  |  |  | GB 땅볼, FB 뜬공, LD 직선타, BU 번트 (안타는 kbodata에 정보 없음) |
| is_at_bat | 타수포함여부 | boolean | Y |  |  | 타수(AB)에 들어가면 true |
| is_hit | 안타여부 | boolean | Y |  |  | 안타면 true |
| total_bases | 루타수 | integer | Y |  |  | 1루타 1 ~ 홈런 4 |
| is_walk | 볼넷여부 | boolean | Y |  |  | 볼넷·고의4구 |
| is_hbp | 사구여부 | boolean | Y |  |  | 몸에 맞는 공 |
| is_sac_fly | 희생플라이여부 | boolean | Y |  |  | 희생플라이 |
| is_sac_bunt | 희생번트여부 | boolean | Y |  |  | 희생번트(실책·야수선택 포함) |
| is_strikeout | 삼진여부 | boolean | Y |  |  | 삼진·스트라이크 낫아웃 |
| is_double_play | 병살여부 | boolean | Y |  |  | 병살타·삼중살 |

**CHECK 제약**

- `ck_pa_result_type_ab`: `CHECK (((NOT is_hit) OR is_at_bat))`
- `ck_pa_result_type_bb`: `CHECK (((batted_ball)::text = ANY ((ARRAY['GB'::character varying, 'FB'::character varying, 'LD'::character varying, 'BU'::character varying])::text[])))`
- `ck_pa_result_type_hit`: `CHECK (((total_bases > 0) = is_hit))`
- `ck_pa_result_type_tb`: `CHECK (((total_bases >= 0) AND (total_bases <= 4)))`

## 10.11 타석결과코드 (pa_result_code)

kbodata config.ini [BATTER] 코드표 (좌중안=1020 등)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| result_code | 결과코드 | integer | Y | PK |  | kbodata 4자리 코드 |
| result_name | 결과명 | varchar(10) | Y | UQ |  | 박스스코어 표기 (예: 좌중안, 유땅, 삼진) |
| result_type | 결과유형코드 | varchar(20) | Y | FK→pa_result_type.result_type |  | 타석결과유형(FK) |
| fielder_pos | 처리수비위치 | integer |  |  |  | 타구를 처리한 첫 수비수 (1 투수 ~ 9 우익수) |
| spray_dir | 타구방향 | varchar(2) |  |  |  | 스프레이 차트 구역 L 좌, LC 좌중, C 중, RC 우중, R 우 |

**참조 무결성 (FK)**

- `fk_pa_result_code_type`: (result_type) → pa_result_type(result_type) ON UPDATE CASCADE ON DELETE RESTRICT — 비식별 관계

**CHECK 제약**

- `ck_pa_result_code_fielder`: `CHECK (((fielder_pos >= 1) AND (fielder_pos <= 9)))`
- `ck_pa_result_code_range`: `CHECK (((result_code >= 1000) AND (result_code <= 7999)))`
- `ck_pa_result_code_spray`: `CHECK (((spray_dir)::text = ANY ((ARRAY['L'::character varying, 'LC'::character varying, 'C'::character varying, 'RC'::character varying, 'R'::character varying])::text[])))`

## 10.12 타자경기기록 (batter_match)

박스스코어 타자 한 줄. 이닝별 결과는 타석 테이블로 분리

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_batter_match_key |
| match_id | 경기ID | varchar(14) (d_match_id) | Y | FK→match_team.match_id, UQ(업무키) |  | (경기ID, 팀ID)가 팀경기기록(FK) |
| player_id | 선수ID | integer (d_player_id) | Y | FK→player.player_id, UQ(업무키) |  | 선수(FK) |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→match_team.team_id, UQ |  | 출전 팀 (그 경기 두 팀 중 하나여야 함을 FK로 보장) |
| lineup_seq | 라인업순서 | integer | Y | UQ |  | 박스스코어 행 순서 (선발 다음에 교체 선수) |
| batting_order | 타순 | integer |  |  |  | 1~9. kbodata가 타순 열을 버리므로 현재 NULL (❓ 원본 보강 필요) |
| positions | 포지션이력 | varchar(12) |  |  |  | kbodata 포지션 코드 문자열 (예: H8 = 대타 후 중견수). 표시용 |
| at_bats | 타수 | integer (d_count) | Y |  |  | AB |
| hits | 안타 | integer (d_count) | Y |  |  | H |
| rbi | 타점 | integer (d_count) | Y |  |  | RBI |
| runs | 득점 | integer (d_count) | Y |  |  | R |

**참조 무결성 (FK)**

- `fk_batter_match_match_team`: (match_id, team_id) → match_team(match_id, team_id) ON UPDATE CASCADE ON DELETE CASCADE — 비식별 관계
- `fk_batter_match_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `batter_match_at_bats_check`: `CHECK ((at_bats >= 0))`
- `batter_match_hits_check`: `CHECK ((hits >= 0))`
- `batter_match_rbi_check`: `CHECK ((rbi >= 0))`
- `batter_match_runs_check`: `CHECK ((runs >= 0))`
- `ck_batter_match_hits`: `CHECK ((hits <= at_bats))`
- `ck_batter_match_lineup`: `CHECK ((lineup_seq >= 1))`
- `ck_batter_match_order`: `CHECK (((batting_order >= 1) AND (batting_order <= 9)))`
- `ck_batter_match_positions`: `CHECK (((positions)::text ~ '^[1-9DHR]+$'::text))`

## 10.13 타석 (plate_appearance)

타자의 타석 하나. kbodata 타자 기록의 i_1~i_18 반복 그룹을 행으로 바꾼 것 (1NF)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_plate_appearance_key |
| match_id | 경기ID | varchar(14) (d_match_id) | Y | FK→batter_match.match_id, UQ(업무키) |  | (경기ID, 선수ID)가 타자경기기록(FK) |
| player_id | 선수ID | integer (d_player_id) | Y | FK→batter_match.player_id, UQ(업무키) |  | 타자 |
| inning | 이닝 | integer (d_inning) | Y | UQ(업무키) |  | 타석이 들어선 이닝 |
| seq_in_inning | 이닝내순번 | integer | Y | UQ(업무키) |  | 한 이닝에 두 번 이상 타석에 서면 1, 2 ... |
| result_code | 결과코드 | integer | Y | FK→pa_result_code.result_code |  | 타석결과코드(FK) |

**참조 무결성 (FK)**

- `fk_plate_appearance_batter_match`: (match_id, player_id) → batter_match(match_id, player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_plate_appearance_code`: (result_code) → pa_result_code(result_code) ON UPDATE CASCADE ON DELETE RESTRICT — 비식별 관계

**CHECK 제약**

- `ck_plate_appearance_seq`: `CHECK (((seq_in_inning >= 1) AND (seq_in_inning <= 4)))`
- `plate_appearance_inning_check`: `CHECK (((inning >= 1) AND (inning <= 18)))`

## 10.14 투수경기기록 (pitcher_match)

박스스코어 투수 한 줄. 선발 여부는 등판순서=1로 유도(저장하지 않음)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_pitcher_match_key |
| match_id | 경기ID | varchar(14) (d_match_id) | Y | FK→match_team.match_id, UQ(업무키) |  | (경기ID, 팀ID)가 팀경기기록(FK) |
| player_id | 선수ID | integer (d_player_id) | Y | FK→player.player_id, UQ(업무키) |  | 선수(FK) |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→match_team.team_id, UQ |  | 소속 팀 |
| appearance_seq | 등판순서 | integer | Y | UQ |  | 1이 선발 |
| decision | 승패세홀 | varchar(1) |  |  |  | W 승, L 패, S 세이브, H 홀드, 없으면 NULL |
| outs_recorded | 아웃카운트 | integer (d_outs) | Y |  |  | 이닝×3 (6⅓이닝 = 19). kbodata 이닝 61 → 19 |
| batters_faced | 상대타자수 | integer (d_count) | Y |  |  | TBF |
| at_bats | 피타수 | integer (d_count) | Y |  |  | 상대 타수 |
| pitches | 투구수 | integer (d_count) |  |  |  | NP (과거 경기는 없을 수 있음) |
| hits_allowed | 피안타 | integer (d_count) | Y |  |  | H |
| home_runs_allowed | 피홈런 | integer (d_count) | Y |  |  | HR |
| walks_hbp | 4사구 | integer (d_count) | Y |  |  | 볼넷+몸에 맞는 공 (kbodata는 둘을 합쳐서 제공) |
| strikeouts | 탈삼진 | integer (d_count) | Y |  |  | SO |
| runs_allowed | 실점 | integer (d_count) | Y |  |  | R |
| earned_runs | 자책점 | integer (d_count) | Y |  |  | ER |

**참조 무결성 (FK)**

- `fk_pitcher_match_match_team`: (match_id, team_id) → match_team(match_id, team_id) ON UPDATE CASCADE ON DELETE CASCADE — 비식별 관계
- `fk_pitcher_match_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_pitcher_match_ab`: `CHECK ((at_bats <= batters_faced))`
- `ck_pitcher_match_decision`: `CHECK (((decision)::text = ANY ((ARRAY['W'::character varying, 'L'::character varying, 'S'::character varying, 'H'::character varying])::text[])))`
- `ck_pitcher_match_er`: `CHECK ((earned_runs <= runs_allowed))`
- `ck_pitcher_match_hits`: `CHECK ((hits_allowed <= at_bats))`
- `ck_pitcher_match_hr`: `CHECK ((home_runs_allowed <= hits_allowed))`
- `ck_pitcher_match_outs`: `CHECK ((outs_recorded <= 81))`
- `ck_pitcher_match_seq`: `CHECK ((appearance_seq >= 1))`
- `pitcher_match_at_bats_check`: `CHECK ((at_bats >= 0))`
- `pitcher_match_batters_faced_check`: `CHECK ((batters_faced >= 0))`
- `pitcher_match_earned_runs_check`: `CHECK ((earned_runs >= 0))`
- `pitcher_match_hits_allowed_check`: `CHECK ((hits_allowed >= 0))`
- `pitcher_match_home_runs_allowed_check`: `CHECK ((home_runs_allowed >= 0))`
- `pitcher_match_outs_recorded_check`: `CHECK ((outs_recorded >= 0))`
- `pitcher_match_pitches_check`: `CHECK ((pitches >= 0))`
- `pitcher_match_runs_allowed_check`: `CHECK ((runs_allowed >= 0))`
- `pitcher_match_strikeouts_check`: `CHECK ((strikeouts >= 0))`
- `pitcher_match_walks_hbp_check`: `CHECK ((walks_hbp >= 0))`

## 10.15 기타기록유형 (match_event_type)

박스스코어 기타 기록의 항목 (결승타, 홈런, 도루, 실책 ...)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| event_type | 기록유형 | varchar(10) | Y | PK |  | 박스스코어 항목명 그대로 |
| name_en | 영문명 | varchar(30) | Y |  |  | 영문 이름 |

## 10.16 경기기타기록 (match_event)

결승타·홈런·도루·실책 등. 원문 한 항목에 이닝이 여러 개면 이닝마다 한 행

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| event_id | 기록ID | bigint | Y | PK |  | 인조 식별자(자동 증가) |
| match_id | 경기ID | varchar(14) (d_match_id) | Y | FK→match_team.match_id, UQ |  | 경기(FK) |
| event_type | 기록유형 | varchar(10) | Y | FK→match_event_type.event_type, UQ |  | 기타기록유형(FK) |
| seq | 순번 | integer | Y | UQ |  | 같은 경기·같은 유형 안에서의 순서 |
| player_id | 선수ID | integer (d_player_id) |  | FK→player.player_id |  | 선수(FK). 이름 매핑 실패 시 NULL |
| team_id | 팀ID | varchar(2) (d_team_id) |  | FK→match_team.team_id |  | 선수 소속 팀 (모르면 NULL) |
| player_name_raw | 원문선수명 | varchar(30) (d_person_name) | Y |  |  | 박스스코어 표기 이름 |
| inning | 이닝 | integer (d_inning) |  |  |  | 발생 이닝 (없으면 NULL) |
| detail | 상세 | varchar(100) |  |  |  | 괄호 안 내용 (예: 4회2점 김광현) |
| raw_text | 원문 | varchar(200) | Y |  |  | kbodata ETC_info 원문 조각 |

**참조 무결성 (FK)**

- `fk_match_event_match`: (match_id) → match(match_id) ON UPDATE CASCADE ON DELETE CASCADE — 비식별 관계
- `fk_match_event_match_team`: (match_id, team_id) → match_team(match_id, team_id) ON UPDATE CASCADE ON DELETE CASCADE — 비식별 관계
- `fk_match_event_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE SET NULL — 비식별 관계
- `fk_match_event_type`: (event_type) → match_event_type(event_type) ON UPDATE CASCADE ON DELETE RESTRICT — 비식별 관계

**CHECK 제약**

- `ck_match_event_seq`: `CHECK ((seq >= 1))`
- `match_event_inning_check`: `CHECK (((inning >= 1) AND (inning <= 18)))`
- `match_event_player_name_raw_check`: `CHECK ((length(btrim((player_name_raw)::text)) > 0))`

## 10.17 심판 (umpire)

심판 (원본에 ID가 없어 이름을 대체키로 사용)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| umpire_id | 심판ID | integer | Y | PK |  | 인조 식별자(자동 증가) |
| umpire_name | 심판명 | varchar(30) (d_person_name) | Y | UQ |  | 이름 (동명이인이 나오면 구분 규칙 필요) |

**CHECK 제약**

- `umpire_umpire_name_check`: `CHECK ((length(btrim((umpire_name)::text)) > 0))`

## 10.18 경기심판 (match_umpire)

경기와 심판의 M:N 관계를 푸는 연관 엔터티

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_match_umpire_key |
| match_id | 경기ID | varchar(14) (d_match_id) | Y | FK→match.match_id, UQ(업무키) |  | 경기(FK) |
| umpire_id | 심판ID | integer | Y | FK→umpire.umpire_id, UQ(업무키) |  | 심판(FK) |
| listed_order | 표기순서 | integer | Y | UQ |  | 박스스코어 나열 순서 (❓ 주심/누심 구분 규칙 확인 필요) |

**참조 무결성 (FK)**

- `fk_match_umpire_match`: (match_id) → match(match_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_match_umpire_umpire`: (umpire_id) → umpire(umpire_id) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_match_umpire_order`: `CHECK (((listed_order >= 1) AND (listed_order <= 6)))`

## 10.19 시즌타자기록(공식) (season_batting_official)

KBO 기록실 시즌 누적 값. 화면에 직접 조회하고 경기 집계와 비교·검증한다

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_season_batting_official_key |
| player_id | 선수ID | integer (d_player_id) | Y | FK→player.player_id, UQ(업무키) |  | 선수(FK) |
| season | 시즌 | integer (d_season) | Y | FK→team_season.season, UQ(업무키) |  | 연도 |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→team_season.team_id, UQ(업무키) |  | 기록실 표기 팀 (❓ 이적 선수 행 분리 여부 확인 필요) |
| games | 경기수 | integer (d_total) |  |  |  | G |
| plate_appearances | 타석 | integer (d_total) |  |  |  | PA |
| at_bats | 타수 | integer (d_total) |  |  |  | AB |
| runs | 득점 | integer (d_total) |  |  |  | R |
| hits | 안타 | integer (d_total) |  |  |  | H |
| doubles | 2루타 | integer (d_total) |  |  |  | 2B |
| triples | 3루타 | integer (d_total) |  |  |  | 3B |
| home_runs | 홈런 | integer (d_total) |  |  |  | HR |
| total_bases | 루타 | integer (d_total) |  |  |  | TB |
| rbi | 타점 | integer (d_total) |  |  |  | RBI |
| sac_bunts | 희생번트 | integer (d_total) |  |  |  | SAC |
| sac_flies | 희생플라이 | integer (d_total) |  |  |  | SF |
| walks | 볼넷 | integer (d_total) |  |  |  | BB |
| intentional_walks | 고의4구 | integer (d_total) |  |  |  | IBB |
| hbp | 사구 | integer (d_total) |  |  |  | HBP |
| strikeouts | 삼진 | integer (d_total) |  |  |  | SO |
| gidp | 병살타 | integer (d_total) |  |  |  | GDP |
| avg | 타율 | numeric(4,3) (d_rate) |  |  |  | AVG |
| obp | 출루율 | numeric(4,3) (d_rate) |  |  |  | OBP |
| slg | 장타율 | numeric(5,3) (d_slg) |  |  |  | SLG |
| ops | OPS | numeric(5,3) (d_slg) |  |  |  | 출루율+장타율 |
| crawled_at | 수집일시 | timestamptz | Y |  | now() | 기록실에서 받은 시각 |

**참조 무결성 (FK)**

- `fk_sbo_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_sbo_team_season`: (team_id, season) → team_season(team_id, season) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_sbo_hits`: `CHECK ((hits <= at_bats))`
- `season_batting_official_at_bats_check`: `CHECK ((at_bats >= 0))`
- `season_batting_official_avg_check`: `CHECK (((avg >= (0)::numeric) AND (avg <= (1)::numeric)))`
- `season_batting_official_doubles_check`: `CHECK ((doubles >= 0))`
- `season_batting_official_games_check`: `CHECK ((games >= 0))`
- `season_batting_official_gidp_check`: `CHECK ((gidp >= 0))`
- `season_batting_official_hbp_check`: `CHECK ((hbp >= 0))`
- `season_batting_official_hits_check`: `CHECK ((hits >= 0))`
- `season_batting_official_home_runs_check`: `CHECK ((home_runs >= 0))`
- `season_batting_official_intentional_walks_check`: `CHECK ((intentional_walks >= 0))`
- `season_batting_official_obp_check`: `CHECK (((obp >= (0)::numeric) AND (obp <= (1)::numeric)))`
- `season_batting_official_ops_check`: `CHECK (((ops >= (0)::numeric) AND (ops <= (5)::numeric)))`
- `season_batting_official_plate_appearances_check`: `CHECK ((plate_appearances >= 0))`
- `season_batting_official_rbi_check`: `CHECK ((rbi >= 0))`
- `season_batting_official_runs_check`: `CHECK ((runs >= 0))`
- `season_batting_official_sac_bunts_check`: `CHECK ((sac_bunts >= 0))`
- `season_batting_official_sac_flies_check`: `CHECK ((sac_flies >= 0))`
- `season_batting_official_season_check`: `CHECK (((season >= 1982) AND (season <= 2100)))`
- `season_batting_official_slg_check`: `CHECK (((slg >= (0)::numeric) AND (slg <= (5)::numeric)))`
- `season_batting_official_strikeouts_check`: `CHECK ((strikeouts >= 0))`
- `season_batting_official_total_bases_check`: `CHECK ((total_bases >= 0))`
- `season_batting_official_triples_check`: `CHECK ((triples >= 0))`
- `season_batting_official_walks_check`: `CHECK ((walks >= 0))`

## 10.20 시즌투수기록(공식) (season_pitching_official)

KBO 기록실 시즌 누적 값 (화면 조회 및 경기 집계 검증용)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_season_pitching_official_key |
| player_id | 선수ID | integer (d_player_id) | Y | FK→player.player_id, UQ(업무키) |  | 선수(FK) |
| season | 시즌 | integer (d_season) | Y | FK→team_season.season, UQ(업무키) |  | 연도 |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→team_season.team_id, UQ(업무키) |  | 기록실 표기 팀 |
| games | 경기수 | integer (d_total) |  |  |  | G |
| wins | 승 | integer (d_total) |  |  |  | W |
| losses | 패 | integer (d_total) |  |  |  | L |
| saves | 세이브 | integer (d_total) |  |  |  | SV |
| holds | 홀드 | integer (d_total) |  |  |  | HLD |
| outs_recorded | 아웃카운트 | integer (d_outs) |  |  |  | 이닝(IP)을 아웃 수로 변환 (144 1/3 → 433) |
| hits_allowed | 피안타 | integer (d_total) |  |  |  | H |
| home_runs_allowed | 피홈런 | integer (d_total) |  |  |  | HR |
| walks | 볼넷 | integer (d_total) |  |  |  | BB |
| hbp | 사구 | integer (d_total) |  |  |  | HBP |
| strikeouts | 탈삼진 | integer (d_total) |  |  |  | SO |
| runs_allowed | 실점 | integer (d_total) |  |  |  | R |
| earned_runs | 자책점 | integer (d_total) |  |  |  | ER |
| batters_faced | 상대타자수 | integer (d_total) |  |  |  | TBF |
| pitches | 투구수 | integer (d_total) |  |  |  | NP |
| complete_games | 완투 | integer (d_total) |  |  |  | CG |
| shutouts | 완봉 | integer (d_total) |  |  |  | SHO |
| quality_starts | 퀄리티스타트 | integer (d_total) |  |  |  | QS |
| blown_saves | 블론세이브 | integer (d_total) |  |  |  | BSV |
| era | 평균자책점 | numeric(6,2) (d_era) |  |  |  | ERA |
| whip | WHIP | numeric(6,2) (d_era) |  |  |  | (피안타+볼넷)/이닝 |
| crawled_at | 수집일시 | timestamptz | Y |  | now() | 기록실에서 받은 시각 |

**참조 무결성 (FK)**

- `fk_spo_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_spo_team_season`: (team_id, season) → team_season(team_id, season) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_spo_er`: `CHECK ((earned_runs <= runs_allowed))`
- `season_pitching_official_batters_faced_check`: `CHECK ((batters_faced >= 0))`
- `season_pitching_official_blown_saves_check`: `CHECK ((blown_saves >= 0))`
- `season_pitching_official_complete_games_check`: `CHECK ((complete_games >= 0))`
- `season_pitching_official_earned_runs_check`: `CHECK ((earned_runs >= 0))`
- `season_pitching_official_era_check`: `CHECK ((era >= (0)::numeric))`
- `season_pitching_official_games_check`: `CHECK ((games >= 0))`
- `season_pitching_official_hbp_check`: `CHECK ((hbp >= 0))`
- `season_pitching_official_hits_allowed_check`: `CHECK ((hits_allowed >= 0))`
- `season_pitching_official_holds_check`: `CHECK ((holds >= 0))`
- `season_pitching_official_home_runs_allowed_check`: `CHECK ((home_runs_allowed >= 0))`
- `season_pitching_official_losses_check`: `CHECK ((losses >= 0))`
- `season_pitching_official_outs_recorded_check`: `CHECK ((outs_recorded >= 0))`
- `season_pitching_official_pitches_check`: `CHECK ((pitches >= 0))`
- `season_pitching_official_quality_starts_check`: `CHECK ((quality_starts >= 0))`
- `season_pitching_official_runs_allowed_check`: `CHECK ((runs_allowed >= 0))`
- `season_pitching_official_saves_check`: `CHECK ((saves >= 0))`
- `season_pitching_official_season_check`: `CHECK (((season >= 1982) AND (season <= 2100)))`
- `season_pitching_official_shutouts_check`: `CHECK ((shutouts >= 0))`
- `season_pitching_official_strikeouts_check`: `CHECK ((strikeouts >= 0))`
- `season_pitching_official_walks_check`: `CHECK ((walks >= 0))`
- `season_pitching_official_whip_check`: `CHECK ((whip >= (0)::numeric))`
- `season_pitching_official_wins_check`: `CHECK ((wins >= 0))`

## 10.21 팀순위(공식) (team_rank_official)

KBO 기록실 팀 순위 (기준일별). 경기 테이블로 계산한 순위 뷰와 비교·검증

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| id | 일련번호 | bigint | Y | PK |  | 인조 식별자(JPA 엔티티 @Id). 업무 키는 uq_team_rank_official_key |
| season | 시즌 | integer (d_season) | Y | FK→team_season.season, UQ(업무키) |  | 연도 |
| team_id | 팀ID | varchar(2) (d_team_id) | Y | FK→team_season.team_id, UQ(업무키) |  | (팀ID, 시즌)이 팀시즌(FK) |
| as_of_date | 기준일 | date | Y | UQ(업무키) |  | 순위 기준 날짜 |
| rank | 순위 | integer | Y |  |  | 1~10 |
| games | 경기수 | integer (d_total) | Y |  |  | G |
| wins | 승 | integer (d_total) | Y |  |  | W |
| losses | 패 | integer (d_total) | Y |  |  | L |
| draws | 무 | integer (d_total) | Y |  |  | D |
| win_pct | 승률 | numeric(4,3) (d_rate) |  |  |  | 승/(승+패) |
| games_behind | 게임차 | numeric(4,1) |  |  |  | 1위와의 게임차 |
| last10 | 최근10경기 | varchar(20) |  |  |  | 원문 (예: 6승1무3패) |
| streak | 연속 | varchar(10) |  |  |  | 원문 (예: 3승) |
| crawled_at | 수집일시 | timestamptz | Y |  | now() | 기록실에서 받은 시각 |

**참조 무결성 (FK)**

- `fk_tro_team_season`: (team_id, season) → team_season(team_id, season) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_tro_games`: `CHECK ((((wins + losses) + draws) = games))`
- `ck_tro_gb`: `CHECK ((games_behind >= (0)::numeric))`
- `ck_tro_rank`: `CHECK (((rank >= 1) AND (rank <= 10)))`
- `team_rank_official_draws_check`: `CHECK ((draws >= 0))`
- `team_rank_official_games_check`: `CHECK ((games >= 0))`
- `team_rank_official_losses_check`: `CHECK ((losses >= 0))`
- `team_rank_official_season_check`: `CHECK (((season >= 1982) AND (season <= 2100)))`
- `team_rank_official_win_pct_check`: `CHECK (((win_pct >= (0)::numeric) AND (win_pct <= (1)::numeric)))`
- `team_rank_official_wins_check`: `CHECK ((wins >= 0))`
