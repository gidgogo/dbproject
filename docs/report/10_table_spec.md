# 10. 테이블 기술서

> `tools/gen_erd_docs.py` 가 PostgreSQL 카탈로그(컬럼 COMMENT·제약조건)에서 자동 생성했다.
> 내용을 고칠 때는 `erd/ddl/02_tables.sql` 의 COMMENT를 고친 뒤 다시 생성한다.

## 10.1 팀 (team)

KBO 구단. 팀명이 바뀌어도 같은 구단이면 하나의 행 (팀명 이력은 team_season)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| team_id | 팀ID | d_team_id (character(2)) | Y | PK |  | KBO 팀코드. 구단명이 바뀌어도 유지된다 (SK→SSG도 SK) |
| team_name | 대표팀명 | character varying(30) | Y |  |  | 현재 정식 팀명 |
| city | 연고지 | character varying(20) | Y |  |  | 연고 도시 |
| first_season | 첫시즌 | d_season (smallint) | Y |  |  | 전신 구단을 포함한 KBO 리그 첫 참가 시즌 |

## 10.2 구장 (stadium)

경기가 열리는 야구장

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| stadium_id | 구장ID | smallint | Y | PK |  | 인조 식별자(자동 증가) |
| stadium_name | 구장명 | character varying(40) | Y | UQ |  | 정식 명칭 |
| city | 지역 | character varying(20) | Y |  |  | 구장 소재 도시 |
| is_dome | 돔구장여부 | boolean | Y |  | false | 지붕이 있는 구장이면 true |
| capacity | 수용인원 | integer |  |  |  | 좌석 수 (모르면 NULL) |

**CHECK 제약**

- `ck_stadium_capacity`: `CHECK ((capacity > 0))`

## 10.3 팀시즌 (team_season)

시즌별 팀명과 홈구장 이력 (초안의 팀명이력 TEAM_NAME_HIST를 확장)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| team_id | 팀ID | d_team_id (character(2)) | Y | PK, FK→team.team_id |  | 팀(FK) |
| season | 시즌 | d_season (smallint) | Y | PK, UQ |  | 연도 |
| team_name | 시즌팀명 | character varying(30) | Y |  |  | 그 시즌의 정식 팀명 (예: 2020 SK 와이번스, 2021 SSG 랜더스) |
| short_name | 약칭 | character varying(10) | Y | UQ |  | 박스스코어·kbodata 팀명 표기 (두산, SSG, 키움 등). 이름→팀ID 매핑 키 |
| home_stadium_id | 홈구장ID | smallint |  | FK→stadium.stadium_id |  | 그 시즌 주 홈구장(FK) |

**참조 무결성 (FK)**

- `fk_team_season_stadium`: (home_stadium_id) → stadium(stadium_id) ON UPDATE CASCADE ON DELETE SET NULL — 비식별 관계
- `fk_team_season_team`: (team_id) → team(team_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계

## 10.4 선수 (player)

KBO playerId로 식별하는 선수 마스터. 이름은 동명이인·개명이 있어 식별자로 쓰지 않는다

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| player_id | 선수ID | d_player_id (integer) | Y | PK |  | KBO playerId |
| player_name | 선수명 | d_person_name (character varying(30)) | Y |  |  | 현재 등록 이름 |
| birth_date | 생년월일 | date |  |  |  | 생년월일 |
| height_cm | 신장 | smallint |  |  |  | cm |
| weight_kg | 체중 | smallint |  |  |  | kg |
| throws | 투구손 | d_hand (character(1)) |  |  |  | L 좌투, R 우투 |
| bats | 타격방향 | d_hand (character(1)) |  |  |  | L 좌타, R 우타, S 양타 |
| position | 포지션 | character varying(10) |  |  |  | 투수/포수/내야수/외야수 (상세 페이지 기준) |
| career | 경력 | character varying(200) |  |  |  | 출신교·경력 원문 (예: 발산초-덕수중-구리인창고). 화면 표시용 문자열 |
| draft_info | 지명정보 | character varying(60) |  |  |  | 지명 순위 원문 (예: 17 KIA 2차 4라운드 34순위) |
| draft_year | 지명연도 | d_season (smallint) |  |  |  | 지명정보에서 추출한 연도 |
| join_info | 입단정보 | character varying(30) |  |  |  | 입단년도 원문 (예: 19KIA) |
| join_year | 입단연도 | d_season (smallint) |  |  |  | 입단정보에서 추출한 연도 |
| signing_bonus_10k | 입단계약금 | integer |  |  |  | 만원 단위 (원화가 아니면 NULL) |
| is_retired | 은퇴여부 | boolean | Y |  | false | 은퇴 선수 페이지에서 수집했으면 true |
| profile_crawled_at | 프로필수집일시 | timestamp with time zone |  |  |  | 상세 페이지를 받은 시각 |
| current_team_name | 현재소속명 | character varying(60) |  |  |  | 프로필 수집 시점의 소속 원문. 상무 등 KBO 10개 구단 외 소속도 보존하며 과거 시즌 소속과 구분 |
| current_uniform_no | 현재등번호 | character varying(3) |  |  |  | 프로필 수집 시점의 등번호. 과거 시즌에 소급하지 않음 |
| profile_source_url | 프로필출처 | text |  |  |  | KBO playerId가 포함된 상세 페이지 URL |

**CHECK 제약**

- `ck_player_bonus`: `CHECK ((signing_bonus_10k >= 0))`
- `ck_player_current_uniform`: `CHECK (((current_uniform_no)::text ~ '^[0-9]{1,3}$'::text))`
- `ck_player_height`: `CHECK (((height_cm >= 140) AND (height_cm <= 230)))`
- `ck_player_position`: `CHECK ((("position")::text = ANY ((ARRAY['투수'::character varying, '포수'::character varying, '내야수'::character varying, '외야수'::character varying])::text[])))`
- `ck_player_throws`: `CHECK (((throws)::bpchar = ANY (ARRAY['L'::bpchar, 'R'::bpchar])))`
- `ck_player_weight`: `CHECK (((weight_kg >= 40) AND (weight_kg <= 200)))`

## 10.5 선수시즌소속 (player_season)

선수가 어느 시즌에 어느 팀 소속으로 기록을 남겼는지. 시즌 중 이적하면 팀마다 한 행. 이름+팀+시즌 → 선수ID 매핑의 근거

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| player_id | 선수ID | d_player_id (integer) | Y | PK, FK→player.player_id |  | 선수(FK) |
| season | 시즌 | d_season (smallint) | Y | PK, FK→team_season.season |  | 연도 |
| team_id | 팀ID | d_team_id (character(2)) | Y | PK, FK→team_season.team_id |  | 소속팀. (팀ID, 시즌)이 팀시즌(FK) |
| name_in_season | 시즌표기명 | d_person_name (character varying(30)) | Y |  |  | 그 시즌 기록실 표기 이름 (개명·외국인 이름 축약 대응) |
| is_batter | 타자기록여부 | boolean | Y |  | false | 기록실 타자 목록에 있으면 true |
| is_pitcher | 투수기록여부 | boolean | Y |  | false | 기록실 투수 목록에 있으면 true |
| uniform_no | 시즌등번호 | character varying(3) |  |  |  | 별도 시즌 근거가 있을 때만 입력. 현재 프로필의 등번호는 player.current_uniform_no에 저장 |

**참조 무결성 (FK)**

- `fk_player_season_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_player_season_team_season`: (team_id, season) → team_season(team_id, season) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_player_season_role`: `CHECK ((is_batter OR is_pitcher))`
- `ck_player_season_uniform`: `CHECK (((uniform_no)::text ~ '^[0-9]{1,3}$'::text))`

## 10.6 선수연봉 (player_salary)

연봉은 팀이 아니라 (선수, 시즌)에 종속되므로 선수시즌소속과 분리 (2NF)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| player_id | 선수ID | d_player_id (integer) | Y | PK, FK→player.player_id |  | 선수(FK) |
| season | 시즌 | d_season (smallint) | Y | PK |  | 연도 |
| salary_10k_krw | 연봉(원화) | integer |  |  |  | 만원 단위 |
| salary_usd | 연봉(달러) | integer |  |  |  | 외국인 선수 달러 표기 |
| source_text | 연봉원문 | character varying(30) |  |  |  | 상세 페이지 표기 그대로 (예: 52000만원) |

**참조 무결성 (FK)**

- `fk_player_salary_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계

**CHECK 제약**

- `ck_player_salary_amount`: `CHECK (((salary_10k_krw >= 0) AND (salary_usd >= 0)))`
- `ck_player_salary_any`: `CHECK (((salary_10k_krw IS NOT NULL) OR (salary_usd IS NOT NULL)))`

## 10.7 경기 (game)

한 경기. 경기ID는 kbodata raw JSON의 id를 그대로 쓴다

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| game_id | 경기ID | d_game_id (character varying(14)) | Y | PK |  | YYYYMMDD_원정팀코드홈팀코드더블헤더 (예: 20250601_OBWO0) |
| game_date | 경기일자 | date | Y |  |  | 경기 날짜 |
| season | 시즌 | d_season (smallint) | Y | FK→team_season.season | GENERATED: (EXTRACT(year FROM game_date))::smallint | 경기일자의 연도 (생성 컬럼, 직접 입력 불가) |
| away_team_id | 원정팀ID | d_team_id (character(2)) | Y | FK→team_season.team_id |  | (원정팀ID, 시즌)이 팀시즌(FK) |
| home_team_id | 홈팀ID | d_team_id (character(2)) | Y | FK→team_season.team_id |  | (홈팀ID, 시즌)이 팀시즌(FK) |
| doubleheader_no | 더블헤더번호 | smallint | Y |  | 0 | 0 일반, 1 1차전, 2 2차전 |
| series_id | 경기구분 | smallint | Y |  | 0 | KBO srId (0 정규시즌, 1 시범경기, 3~7 포스트시즌) |
| stadium_id | 구장ID | smallint |  | FK→stadium.stadium_id |  | 구장(FK). 매핑 실패 시 NULL |
| attendance | 관중수 | integer |  |  |  | 명 (무관중 경기는 0) |
| start_time | 개시시각 | time without time zone |  |  |  | 경기 시작 시각 |
| end_time | 종료시각 | time without time zone |  |  |  | 경기 종료 시각 |
| duration_min | 경기시간 | smallint |  |  |  | 분 단위 (3:05 → 185) |
| kbo_game_id | KBO경기ID | character varying(13) |  | UQ | GENERATED: replace((game_id)::text, '_'::text, ''::text) | KBO 게임센터 G_ID (밑줄 제거, 생성 컬럼) |

**참조 무결성 (FK)**

- `fk_game_away_team_season`: (away_team_id, season) → team_season(team_id, season) ON UPDATE NO ACTION ON DELETE NO ACTION — 비식별 관계
- `fk_game_home_team_season`: (home_team_id, season) → team_season(team_id, season) ON UPDATE NO ACTION ON DELETE NO ACTION — 비식별 관계
- `fk_game_stadium`: (stadium_id) → stadium(stadium_id) ON UPDATE CASCADE ON DELETE SET NULL — 비식별 관계

**CHECK 제약**

- `ck_game_attendance`: `CHECK ((attendance >= 0))`
- `ck_game_doubleheader`: `CHECK (((doubleheader_no >= 0) AND (doubleheader_no <= 2)))`
- `ck_game_duration`: `CHECK ((duration_min > 0))`
- `ck_game_id_parts`: `CHECK (((game_id)::text = ((((to_char((game_date)::timestamp with time zone, 'YYYYMMDD'::text) || '_'::text) || (away_team_id)::text) || (home_team_id)::text) || doubleheader_no)))`
- `ck_game_series`: `CHECK (((series_id >= 0) AND (series_id <= 9)))`
- `ck_game_teams`: `CHECK (((away_team_id)::bpchar <> (home_team_id)::bpchar))`

## 10.8 팀경기기록 (team_game)

경기 스코어보드의 팀별 한 줄 (R H E B)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| game_id | 경기ID | d_game_id (character varying(14)) | Y | PK, FK→game.game_id, UQ |  | 경기(FK) |
| team_id | 팀ID | d_team_id (character(2)) | Y | PK, FK→team.team_id |  | 팀(FK). 그 경기의 홈팀 또는 원정팀이어야 함(트리거로 검사) |
| home_away | 홈원정구분 | character(1) | Y | UQ |  | H 홈, A 원정. 경기의 팀ID에서 유도되지만 조회 편의를 위해 저장하고 트리거로 일관성을 보장 |
| result | 승패 | character(1) | Y |  |  | W 승, L 패, D 무 |
| runs | 득점 | d_count (smallint) | Y |  |  | R |
| hits | 안타 | d_count (smallint) | Y |  |  | H |
| errors | 실책 | d_count (smallint) | Y |  |  | E |
| walks_hbp | 4사구 | d_count (smallint) | Y |  |  | B (볼넷+몸에 맞는 공) |

**참조 무결성 (FK)**

- `fk_team_game_game`: (game_id) → game(game_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_team_game_team`: (team_id) → team(team_id) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_team_game_result`: `CHECK ((result = ANY (ARRAY['W'::bpchar, 'L'::bpchar, 'D'::bpchar])))`
- `ck_team_game_side`: `CHECK ((home_away = ANY (ARRAY['H'::bpchar, 'A'::bpchar])))`

## 10.9 이닝득점 (inning_score)

스코어보드 이닝별 점수. kbodata의 i_1~i_18 반복 컬럼을 행으로 바꾼 것 (1NF)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| game_id | 경기ID | d_game_id (character varying(14)) | Y | PK, FK→team_game.game_id |  | (경기ID, 팀ID)가 팀경기기록(FK) |
| team_id | 팀ID | d_team_id (character(2)) | Y | PK, FK→team_game.team_id |  | 공격한 팀 |
| inning | 이닝 | d_inning (smallint) | Y | PK |  | 1~18 |
| runs | 이닝득점 | d_count (smallint) | Y |  |  | 그 이닝 득점 (공격하지 않은 이닝은 행이 없음) |

**참조 무결성 (FK)**

- `fk_inning_score_team_game`: (game_id, team_id) → team_game(game_id, team_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계

## 10.10 타석결과유형 (pa_result_type)

안타·삼진·땅볼 등 결과 유형과 기록 집계 규칙(타수 포함 여부, 루타 수)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| result_type | 결과유형코드 | character varying(20) | Y | PK |  | SINGLE, DOUBLE, STRIKEOUT, GROUND_OUT 등 |
| result_type_name | 결과유형명 | character varying(20) | Y |  |  | 한글 이름 |
| batted_ball | 타구종류 | character(2) |  |  |  | GB 땅볼, FB 뜬공, LD 직선타, BU 번트 (안타는 kbodata에 정보 없음) |
| is_at_bat | 타수포함여부 | boolean | Y |  |  | 타수(AB)에 들어가면 true |
| is_hit | 안타여부 | boolean | Y |  |  | 안타면 true |
| total_bases | 루타수 | smallint | Y |  |  | 1루타 1 ~ 홈런 4 |
| is_walk | 볼넷여부 | boolean | Y |  |  | 볼넷·고의4구 |
| is_hbp | 사구여부 | boolean | Y |  |  | 몸에 맞는 공 |
| is_sac_fly | 희생플라이여부 | boolean | Y |  |  | 희생플라이 |
| is_sac_bunt | 희생번트여부 | boolean | Y |  |  | 희생번트(실책·야수선택 포함) |
| is_strikeout | 삼진여부 | boolean | Y |  |  | 삼진·스트라이크 낫아웃 |
| is_double_play | 병살여부 | boolean | Y |  |  | 병살타·삼중살 |

**CHECK 제약**

- `ck_pa_result_type_ab`: `CHECK (((NOT is_hit) OR is_at_bat))`
- `ck_pa_result_type_bb`: `CHECK ((batted_ball = ANY (ARRAY['GB'::bpchar, 'FB'::bpchar, 'LD'::bpchar, 'BU'::bpchar])))`
- `ck_pa_result_type_hit`: `CHECK (((total_bases > 0) = is_hit))`
- `ck_pa_result_type_tb`: `CHECK (((total_bases >= 0) AND (total_bases <= 4)))`

## 10.11 타석결과코드 (pa_result_code)

kbodata config.ini [BATTER] 코드표 (좌중안=1020 등)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| result_code | 결과코드 | smallint | Y | PK |  | kbodata 4자리 코드 |
| result_name | 결과명 | character varying(10) | Y | UQ |  | 박스스코어 표기 (예: 좌중안, 유땅, 삼진) |
| result_type | 결과유형코드 | character varying(20) | Y | FK→pa_result_type.result_type |  | 타석결과유형(FK) |
| fielder_pos | 처리수비위치 | smallint |  |  |  | 타구를 처리한 첫 수비수 (1 투수 ~ 9 우익수) |
| spray_dir | 타구방향 | character varying(2) |  |  |  | 스프레이 차트 구역 L 좌, LC 좌중, C 중, RC 우중, R 우 |

**참조 무결성 (FK)**

- `fk_pa_result_code_type`: (result_type) → pa_result_type(result_type) ON UPDATE CASCADE ON DELETE RESTRICT — 비식별 관계

**CHECK 제약**

- `ck_pa_result_code_fielder`: `CHECK (((fielder_pos >= 1) AND (fielder_pos <= 9)))`
- `ck_pa_result_code_range`: `CHECK (((result_code >= 1000) AND (result_code <= 7999)))`
- `ck_pa_result_code_spray`: `CHECK (((spray_dir)::text = ANY ((ARRAY['L'::character varying, 'LC'::character varying, 'C'::character varying, 'RC'::character varying, 'R'::character varying])::text[])))`

## 10.12 타자경기기록 (batter_game)

박스스코어 타자 한 줄. 이닝별 결과는 타석 테이블로 분리

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| game_id | 경기ID | d_game_id (character varying(14)) | Y | PK, FK→team_game.game_id, UQ |  | (경기ID, 팀ID)가 팀경기기록(FK) |
| player_id | 선수ID | d_player_id (integer) | Y | PK, FK→player.player_id |  | 선수(FK) |
| team_id | 팀ID | d_team_id (character(2)) | Y | FK→team_game.team_id, UQ |  | 출전 팀 (그 경기 두 팀 중 하나여야 함을 FK로 보장) |
| lineup_seq | 라인업순서 | smallint | Y | UQ |  | 박스스코어 행 순서 (선발 다음에 교체 선수) |
| batting_order | 타순 | smallint |  |  |  | 1~9. kbodata가 타순 열을 버리므로 현재 NULL (❓ 원본 보강 필요) |
| positions | 포지션이력 | character varying(12) |  |  |  | kbodata 포지션 코드 문자열 (예: H8 = 대타 후 중견수). 표시용 |
| at_bats | 타수 | d_count (smallint) | Y |  |  | AB |
| hits | 안타 | d_count (smallint) | Y |  |  | H |
| rbi | 타점 | d_count (smallint) | Y |  |  | RBI |
| runs | 득점 | d_count (smallint) | Y |  |  | R |

**참조 무결성 (FK)**

- `fk_batter_game_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계
- `fk_batter_game_team_game`: (game_id, team_id) → team_game(game_id, team_id) ON UPDATE CASCADE ON DELETE CASCADE — 비식별 관계

**CHECK 제약**

- `ck_batter_game_hits`: `CHECK (((hits)::smallint <= (at_bats)::smallint))`
- `ck_batter_game_lineup`: `CHECK ((lineup_seq >= 1))`
- `ck_batter_game_order`: `CHECK (((batting_order >= 1) AND (batting_order <= 9)))`
- `ck_batter_game_positions`: `CHECK (((positions)::text ~ '^[1-9DHR]+$'::text))`

## 10.13 타석 (plate_appearance)

타자의 타석 하나. kbodata 타자 기록의 i_1~i_18 반복 그룹을 행으로 바꾼 것 (1NF)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| game_id | 경기ID | d_game_id (character varying(14)) | Y | PK, FK→batter_game.game_id |  | (경기ID, 선수ID)가 타자경기기록(FK) |
| player_id | 선수ID | d_player_id (integer) | Y | PK, FK→batter_game.player_id |  | 타자 |
| inning | 이닝 | d_inning (smallint) | Y | PK |  | 타석이 들어선 이닝 |
| seq_in_inning | 이닝내순번 | smallint | Y | PK |  | 한 이닝에 두 번 이상 타석에 서면 1, 2 ... |
| result_code | 결과코드 | smallint | Y | FK→pa_result_code.result_code |  | 타석결과코드(FK) |

**참조 무결성 (FK)**

- `fk_plate_appearance_batter_game`: (game_id, player_id) → batter_game(game_id, player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_plate_appearance_code`: (result_code) → pa_result_code(result_code) ON UPDATE CASCADE ON DELETE RESTRICT — 비식별 관계

**CHECK 제약**

- `ck_plate_appearance_seq`: `CHECK (((seq_in_inning >= 1) AND (seq_in_inning <= 4)))`

## 10.14 투수경기기록 (pitcher_game)

박스스코어 투수 한 줄. 선발 여부는 등판순서=1로 유도(저장하지 않음)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| game_id | 경기ID | d_game_id (character varying(14)) | Y | PK, FK→team_game.game_id, UQ |  | (경기ID, 팀ID)가 팀경기기록(FK) |
| player_id | 선수ID | d_player_id (integer) | Y | PK, FK→player.player_id |  | 선수(FK) |
| team_id | 팀ID | d_team_id (character(2)) | Y | FK→team_game.team_id, UQ |  | 소속 팀 |
| appearance_seq | 등판순서 | smallint | Y | UQ |  | 1이 선발 |
| decision | 승패세홀 | character(1) |  |  |  | W 승, L 패, S 세이브, H 홀드, 없으면 NULL |
| outs_recorded | 아웃카운트 | d_outs (integer) | Y |  |  | 이닝×3 (6⅓이닝 = 19). kbodata 이닝 61 → 19 |
| batters_faced | 상대타자수 | d_count (smallint) | Y |  |  | TBF |
| at_bats | 피타수 | d_count (smallint) | Y |  |  | 상대 타수 |
| pitches | 투구수 | d_count (smallint) |  |  |  | NP (과거 경기는 없을 수 있음) |
| hits_allowed | 피안타 | d_count (smallint) | Y |  |  | H |
| home_runs_allowed | 피홈런 | d_count (smallint) | Y |  |  | HR |
| walks_hbp | 4사구 | d_count (smallint) | Y |  |  | 볼넷+몸에 맞는 공 (kbodata는 둘을 합쳐서 제공) |
| strikeouts | 탈삼진 | d_count (smallint) | Y |  |  | SO |
| runs_allowed | 실점 | d_count (smallint) | Y |  |  | R |
| earned_runs | 자책점 | d_count (smallint) | Y |  |  | ER |

**참조 무결성 (FK)**

- `fk_pitcher_game_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계
- `fk_pitcher_game_team_game`: (game_id, team_id) → team_game(game_id, team_id) ON UPDATE CASCADE ON DELETE CASCADE — 비식별 관계

**CHECK 제약**

- `ck_pitcher_game_ab`: `CHECK (((at_bats)::smallint <= (batters_faced)::smallint))`
- `ck_pitcher_game_decision`: `CHECK ((decision = ANY (ARRAY['W'::bpchar, 'L'::bpchar, 'S'::bpchar, 'H'::bpchar])))`
- `ck_pitcher_game_er`: `CHECK (((earned_runs)::smallint <= (runs_allowed)::smallint))`
- `ck_pitcher_game_hits`: `CHECK (((hits_allowed)::smallint <= (at_bats)::smallint))`
- `ck_pitcher_game_hr`: `CHECK (((home_runs_allowed)::smallint <= (hits_allowed)::smallint))`
- `ck_pitcher_game_outs`: `CHECK (((outs_recorded)::integer <= 81))`
- `ck_pitcher_game_seq`: `CHECK ((appearance_seq >= 1))`

## 10.15 기타기록유형 (game_event_type)

박스스코어 기타 기록의 항목 (결승타, 홈런, 도루, 실책 ...)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| event_type | 기록유형 | character varying(10) | Y | PK |  | 박스스코어 항목명 그대로 |
| name_en | 영문명 | character varying(30) | Y |  |  | 영문 이름 |

## 10.16 경기기타기록 (game_event)

결승타·홈런·도루·실책 등. 원문 한 항목에 이닝이 여러 개면 이닝마다 한 행

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| event_id | 기록ID | bigint | Y | PK |  | 인조 식별자(자동 증가) |
| game_id | 경기ID | d_game_id (character varying(14)) | Y | FK→team_game.game_id, UQ |  | 경기(FK) |
| event_type | 기록유형 | character varying(10) | Y | FK→game_event_type.event_type, UQ |  | 기타기록유형(FK) |
| seq | 순번 | smallint | Y | UQ |  | 같은 경기·같은 유형 안에서의 순서 |
| player_id | 선수ID | d_player_id (integer) |  | FK→player.player_id |  | 선수(FK). 이름 매핑 실패 시 NULL |
| team_id | 팀ID | d_team_id (character(2)) |  | FK→team_game.team_id |  | 선수 소속 팀 (모르면 NULL) |
| player_name_raw | 원문선수명 | d_person_name (character varying(30)) | Y |  |  | 박스스코어 표기 이름 |
| inning | 이닝 | d_inning (smallint) |  |  |  | 발생 이닝 (없으면 NULL) |
| detail | 상세 | character varying(100) |  |  |  | 괄호 안 내용 (예: 4회2점 김광현) |
| raw_text | 원문 | character varying(200) | Y |  |  | kbodata ETC_info 원문 조각 |

**참조 무결성 (FK)**

- `fk_game_event_game`: (game_id) → game(game_id) ON UPDATE CASCADE ON DELETE CASCADE — 비식별 관계
- `fk_game_event_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE SET NULL — 비식별 관계
- `fk_game_event_team_game`: (game_id, team_id) → team_game(game_id, team_id) ON UPDATE CASCADE ON DELETE CASCADE — 비식별 관계
- `fk_game_event_type`: (event_type) → game_event_type(event_type) ON UPDATE CASCADE ON DELETE RESTRICT — 비식별 관계

**CHECK 제약**

- `ck_game_event_seq`: `CHECK ((seq >= 1))`

## 10.17 심판 (umpire)

심판 (원본에 ID가 없어 이름을 대체키로 사용)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| umpire_id | 심판ID | smallint | Y | PK |  | 인조 식별자(자동 증가) |
| umpire_name | 심판명 | d_person_name (character varying(30)) | Y | UQ |  | 이름 (동명이인이 나오면 구분 규칙 필요) |

## 10.18 경기심판 (game_umpire)

경기와 심판의 M:N 관계를 푸는 연관 엔터티

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| game_id | 경기ID | d_game_id (character varying(14)) | Y | PK, FK→game.game_id, UQ |  | 경기(FK) |
| umpire_id | 심판ID | smallint | Y | PK, FK→umpire.umpire_id |  | 심판(FK) |
| listed_order | 표기순서 | smallint | Y | UQ |  | 박스스코어 나열 순서 (❓ 주심/누심 구분 규칙 확인 필요) |

**참조 무결성 (FK)**

- `fk_game_umpire_game`: (game_id) → game(game_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_game_umpire_umpire`: (umpire_id) → umpire(umpire_id) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_game_umpire_order`: `CHECK (((listed_order >= 1) AND (listed_order <= 6)))`

## 10.19 시즌타자기록(공식) (season_batting_official)

KBO 기록실 시즌 누적 값. 화면에 직접 조회하고 경기 집계와 비교·검증한다

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| player_id | 선수ID | d_player_id (integer) | Y | PK, FK→player.player_id |  | 선수(FK) |
| season | 시즌 | d_season (smallint) | Y | PK, FK→team_season.season |  | 연도 |
| team_id | 팀ID | d_team_id (character(2)) | Y | PK, FK→team_season.team_id |  | 기록실 표기 팀 (❓ 이적 선수 행 분리 여부 확인 필요) |
| games | 경기수 | d_total (integer) |  |  |  | G |
| plate_appearances | 타석 | d_total (integer) |  |  |  | PA |
| at_bats | 타수 | d_total (integer) |  |  |  | AB |
| runs | 득점 | d_total (integer) |  |  |  | R |
| hits | 안타 | d_total (integer) |  |  |  | H |
| doubles | 2루타 | d_total (integer) |  |  |  | 2B |
| triples | 3루타 | d_total (integer) |  |  |  | 3B |
| home_runs | 홈런 | d_total (integer) |  |  |  | HR |
| total_bases | 루타 | d_total (integer) |  |  |  | TB |
| rbi | 타점 | d_total (integer) |  |  |  | RBI |
| sac_bunts | 희생번트 | d_total (integer) |  |  |  | SAC |
| sac_flies | 희생플라이 | d_total (integer) |  |  |  | SF |
| walks | 볼넷 | d_total (integer) |  |  |  | BB |
| intentional_walks | 고의4구 | d_total (integer) |  |  |  | IBB |
| hbp | 사구 | d_total (integer) |  |  |  | HBP |
| strikeouts | 삼진 | d_total (integer) |  |  |  | SO |
| gidp | 병살타 | d_total (integer) |  |  |  | GDP |
| avg | 타율 | d_rate (numeric(4,3)) |  |  |  | AVG |
| obp | 출루율 | d_rate (numeric(4,3)) |  |  |  | OBP |
| slg | 장타율 | d_slg (numeric(5,3)) |  |  |  | SLG |
| ops | OPS | d_slg (numeric(5,3)) |  |  |  | 출루율+장타율 |
| crawled_at | 수집일시 | timestamp with time zone | Y |  | now() | 기록실에서 받은 시각 |

**참조 무결성 (FK)**

- `fk_sbo_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_sbo_team_season`: (team_id, season) → team_season(team_id, season) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_sbo_hits`: `CHECK (((hits)::integer <= (at_bats)::integer))`

## 10.20 시즌투수기록(공식) (season_pitching_official)

KBO 기록실 시즌 누적 값 (화면 조회 및 경기 집계 검증용)

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| player_id | 선수ID | d_player_id (integer) | Y | PK, FK→player.player_id |  | 선수(FK) |
| season | 시즌 | d_season (smallint) | Y | PK, FK→team_season.season |  | 연도 |
| team_id | 팀ID | d_team_id (character(2)) | Y | PK, FK→team_season.team_id |  | 기록실 표기 팀 |
| games | 경기수 | d_total (integer) |  |  |  | G |
| wins | 승 | d_total (integer) |  |  |  | W |
| losses | 패 | d_total (integer) |  |  |  | L |
| saves | 세이브 | d_total (integer) |  |  |  | SV |
| holds | 홀드 | d_total (integer) |  |  |  | HLD |
| outs_recorded | 아웃카운트 | d_outs (integer) |  |  |  | 이닝(IP)을 아웃 수로 변환 (144 1/3 → 433) |
| hits_allowed | 피안타 | d_total (integer) |  |  |  | H |
| home_runs_allowed | 피홈런 | d_total (integer) |  |  |  | HR |
| walks | 볼넷 | d_total (integer) |  |  |  | BB |
| hbp | 사구 | d_total (integer) |  |  |  | HBP |
| strikeouts | 탈삼진 | d_total (integer) |  |  |  | SO |
| runs_allowed | 실점 | d_total (integer) |  |  |  | R |
| earned_runs | 자책점 | d_total (integer) |  |  |  | ER |
| batters_faced | 상대타자수 | d_total (integer) |  |  |  | TBF |
| pitches | 투구수 | d_total (integer) |  |  |  | NP |
| complete_games | 완투 | d_total (integer) |  |  |  | CG |
| shutouts | 완봉 | d_total (integer) |  |  |  | SHO |
| quality_starts | 퀄리티스타트 | d_total (integer) |  |  |  | QS |
| blown_saves | 블론세이브 | d_total (integer) |  |  |  | BSV |
| era | 평균자책점 | d_era (numeric(6,2)) |  |  |  | ERA |
| whip | WHIP | d_era (numeric(6,2)) |  |  |  | (피안타+볼넷)/이닝 |
| crawled_at | 수집일시 | timestamp with time zone | Y |  | now() | 기록실에서 받은 시각 |

**참조 무결성 (FK)**

- `fk_spo_player`: (player_id) → player(player_id) ON UPDATE CASCADE ON DELETE CASCADE — 식별 관계
- `fk_spo_team_season`: (team_id, season) → team_season(team_id, season) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_spo_er`: `CHECK (((earned_runs)::integer <= (runs_allowed)::integer))`

## 10.21 팀순위(공식) (team_rank_official)

KBO 기록실 팀 순위 (기준일별). 경기 테이블로 계산한 순위 뷰와 비교·검증

| Attribute | 논리명 | Data Type | NN | Key | Default | Description |
|---|---|---|:---:|---|---|---|
| season | 시즌 | d_season (smallint) | Y | PK, FK→team_season.season |  | 연도 |
| team_id | 팀ID | d_team_id (character(2)) | Y | PK, FK→team_season.team_id |  | (팀ID, 시즌)이 팀시즌(FK) |
| as_of_date | 기준일 | date | Y | PK |  | 순위 기준 날짜 |
| rank | 순위 | smallint | Y |  |  | 1~10 |
| games | 경기수 | d_total (integer) | Y |  |  | G |
| wins | 승 | d_total (integer) | Y |  |  | W |
| losses | 패 | d_total (integer) | Y |  |  | L |
| draws | 무 | d_total (integer) | Y |  |  | D |
| win_pct | 승률 | d_rate (numeric(4,3)) |  |  |  | 승/(승+패) |
| games_behind | 게임차 | numeric(4,1) |  |  |  | 1위와의 게임차 |
| last10 | 최근10경기 | character varying(20) |  |  |  | 원문 (예: 6승1무3패) |
| streak | 연속 | character varying(10) |  |  |  | 원문 (예: 3승) |
| crawled_at | 수집일시 | timestamp with time zone | Y |  | now() | 기록실에서 받은 시각 |

**참조 무결성 (FK)**

- `fk_tro_team_season`: (team_id, season) → team_season(team_id, season) ON UPDATE CASCADE ON DELETE RESTRICT — 식별 관계

**CHECK 제약**

- `ck_tro_games`: `CHECK (((((wins)::integer + (losses)::integer) + (draws)::integer) = (games)::integer))`
- `ck_tro_gb`: `CHECK ((games_behind >= (0)::numeric))`
- `ck_tro_rank`: `CHECK (((rank >= 1) AND (rank <= 10)))`
