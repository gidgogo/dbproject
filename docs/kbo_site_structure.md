# KBO 공식 홈페이지 — 크롤링 대상 페이지 구조 (2-2, 2-3)

> 작성: 2026-11-05 · 상태: **공개 크롤러 코드로 확인 ✅ / 맥 실측 전 ❓**
> 클라우드 환경에서는 koreabaseball.com 접속이 막혀 있어, 실제 사이트를 크롤링하는 공개 오픈소스 코드에서 구조를 확인했다.
> 맥에서 `python crawl/probe_kbo.py` (요청 약 12회) 를 먼저 실행하면 `docs/probe/kbo_probe_YYYYMMDD.md`에
> 각 가정의 ✅/❌ 가 기록된다. ❌ 가 있으면 그 결과 파일을 공유해 주면 크롤러를 고친다.

## 1. 페이지 목록

| 용도 | URL | 방식 | 쓰는 스크립트 |
|---|---|---|---|
| 타자 기록실 (기본1) | `/Record/Player/HitterBasic/Basic1.aspx` | ASP.NET 포스트백 | kbo_records.py |
| 타자 기록실 (기본2) | `/Record/Player/HitterBasic/Basic2.aspx` | 〃 | kbo_records.py |
| 투수 기록실 (기본1·2) | `/Record/Player/PitcherBasic/Basic1.aspx`, `Basic2.aspx` | 〃 | kbo_records.py |
| 현역 선수 상세 | `/Record/Player/HitterDetail/Basic.aspx?playerId=`, `PitcherDetail/Basic.aspx?playerId=` | GET | kbo_profiles.py |
| 은퇴 선수 상세 | `/Record/Retire/Hitter.aspx?playerId=`, `/Record/Retire/Pitcher.aspx?playerId=` | GET | kbo_profiles.py |
| 선수 일자별 기록 | `/Record/Player/HitterDetail/Daily.aspx?playerId=` (투수 PitcherDetail) | GET + 연도 포스트백 | kbo_gamelogs.py |
| 팀 순위 (현재) | `/Record/TeamRank/TeamRank.aspx` | GET | probe |
| 팀 순위 (기준일) | `/Record/TeamRank/TeamRankDaily.aspx` | hfSearchDate + 조회 버튼 | kbo_team_rank.py |
| (kbodata) 게임센터 | `/Schedule/GameCenter/Main.aspx?gameDate=...&gameId=...&section=REVIEW` | Selenium | kbodata |

## 2. 기록실 (Basic1/Basic2)

- 폼 컨트롤 이름은 `ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$` 접두어 + 아래 이름
  - `ddlSeason$ddlSeason` 시즌, `ddlTeam$ddlTeam` 팀(값 = 팀코드 ❓), `ddlSeries$ddlSeries` 정규시즌 0
  - `hfOrderByCol` 정렬 기준 (`HRA_RT` 타율, `GAME_CN` 경기수), `hfOrderBy` (DESC), `lbtnOrderBy` 정렬 포스트백
  - 페이지 이동: `ucPager$btnNo2` … (또는 `hfPage`)
- 포스트백할 때 `__VIEWSTATE`, `__EVENTVALIDATION` 등 hidden 필드를 **모두** 다시 보내야 한다
  (빠지면 에러 페이지). → `crawl/aspnet.py`가 폼 전체를 모아 보낸다.
- 결과 표: `table.tData`, 선수명 셀 링크 `…/HitterDetail/Basic.aspx?playerId=76232`
- **규정타석**: 기본 정렬(타율)에서는 규정타석 이상 선수만 나온다. 경기수(GAME_CN)로 정렬하면 전체 선수가 나온다 ❓
- 열 이름 (영문 약어. 선수명·팀명·AVG·G·PA·AB·H·HR 는 공개 코드에서 확인, 나머지 전체 목록·순서는 ❓ probe로 확인)
  - 타자 기본1: 순위, 선수명, 팀명, AVG, G, PA, AB, R, H, 2B, 3B, HR, TB, RBI, SAC, SF
  - 타자 기본2: 순위, 선수명, 팀명, AVG, BB, IBB, HBP, SO, GDP, SLG, OBP, OPS, MH, RISP, PH-BA
  - 투수 기본1: 순위, 선수명, 팀명, ERA, G, W, L, SV, HLD, WPCT, IP, H, HR, BB, HBP, SO, R, ER, WHIP
  - 투수 기본2: 순위, 선수명, 팀명, ERA, CG, SHO, QS, BSV, TBF, NP, AVG, 2B, 3B, SAC, SF, IBB, WP, BK
  - 열 이름으로 매핑하므로 순서가 바뀌어도 된다. 모르는 열은 probe 리포트에 ⚠️로 표시된다.

## 3. 선수 상세

`<span id="…_playerProfile_lbl***">` (은퇴 선수 페이지는 `ucPlayerProfile_` 일 수 있음)

| id 끝부분 | 예 | 저장 |
|---|---|---|
| lblName | 홍길동 | player_name |
| lblBackNo | 48 | uniform_no (현재 시즌) |
| lblBirthday | 1998년 04월 07일 | birth_date |
| lblPosition | 투수(우투우타) | position, throws, bats |
| lblHeightWeight | 190cm/86kg | height_cm, weight_kg |
| lblCareer | ○○초-○○중-○○고 | career |
| lblPayment | 7000만원 | signing_bonus_10k |
| lblSalary | 52000만원 / 100000달러 | salary_10k_krw / salary_usd (현재 시즌) |
| lblDraft | 17 KIA 2차 4라운드 34순위 | draft_info, draft_year |
| lblJoinInfo | 19KIA | join_info, join_year |
| `h4.team` | KIA 타이거즈 | 현재 소속팀 |

## 4. 팀 순위

열: 순위, 팀명, 경기, 승, 패, 무, 승률, 게임차, 최근10경기, 연속, 홈, 방문.
기준일 변경: `hfSearchDate`(YYYYMMDD) + `btnCalendarSelect` 제출, `ddlSeries`를 덮어쓰면 에러가 난다는 보고가 있다.

## 5. JSON 웹서비스 (참고, 이번 범위에서는 안 씀)

- `POST /ws/Main.asmx/GetKboGameList` `{"leId":"1","srId":"0,1,3,4,5,7,9","date":"YYYYMMDD"}` → 경기 목록
  (G_ID, 승리·패전·세이브 투수 이름 포함) — kbodata 투수 결과 버그를 검증할 때 쓸 수 있다.
- `POST /ws/Schedule.asmx/GetScoreBoardScroll`, `/ws/Controls.asmx/GetSearchPlayer`

## 근거 (공개 자료)

| 출처 | 확인한 내용 |
|---|---|
| GitHub `kbo-data-portal/collector` scrapers/player.py, utils/request.py | 기록실 URL, `sort=GAME_CN`, hfOrderByCol/hfOrderBy/lbtnOrderBy/hfPage 포스트백, VIEWSTATE·EVENTVALIDATION, 표 파싱, 상세·Daily URL |
| GitHub `icedo724/kbo-bayes` collect/fetch.py | 폼 전체 재전송 필요, ddlSeason/ddlSeries/ucPager$btnNoN, 규정타석 설명, Daily.aspx ddlYear, TeamRankDaily hfSearchDate + btnCalendarSelect |
| GitHub `hwinside/kbo-everyday` specs/kbo-api-map.md | TeamRank 열, GetKboGameList 필드, 팀코드 |
| GitHub 코드 검색 (playerProfile_lbl…): tmdgy6232/html, co2plant/KBO_DiscordApp, harlanljones/rosetta 테스트 HTML 등 | 상세 페이지 span id와 값 형식 |
| GitHub 코드 검색 (Record/Retire): 여러 레포 | 은퇴 선수 URL |
| dev-bearabbit/kbo-data (kbodata) 소스 | 게임센터 파싱 방식, 팀코드, 결과 코드표 |
