# 네이버 스포츠 문자중계 — URL 패턴과 필드 정리 (2-4 가능성 확인)

> 작성: 2026-11-05 (이성수 작업, Claude 정리) · 상태: **공개 자료로 확인 ✅ / 맥 실측 전 ❓**
> 이 클라우드 환경에서는 네이버 접속이 막혀 있어 직접 호출하지 못했다. 아래 내용은 네이버 API를 실제로 쓰는
> 공개 오픈소스 코드와 문서에서 확인한 것이고, 맥에서 `python crawl/naver_probe.py --years 2018,2020,2022,2023,2025`
> 를 실행하면 `docs/probe/naver_probe_YYYYMMDD.md` 에 실측 결과가 남는다. 실측 후 이 문서의 ❓를 지운다.

## 1. 결론 (11/12 가능성 확인용 요약)

| 질문 | 답 | 근거 |
|---|---|---|
| 투구마다 구종·구속·결과가 있나 | **있다** — `stuff`(구종), `speed`(km/h), `pitchResult`(B/T/S/F/V/W/H) | 근거 A, B, C |
| 볼카운트·아웃·주자·점수가 있나 | **있다** — 이벤트마다 `currentGameState`(이벤트 *후* 상태) | 근거 A, B |
| 투구 위치 좌표(x·y)가 있나 | **있다** — `ptsOptions[]`에 PITCHf/x 형식 `crossPlateX`, `topSz`, `bottomSz`, 초기 위치·속도·가속도. 높이(z)는 궤적으로 계산 | 근거 A, D, E |
| 몇 년도 경기까지 | 트래킹(좌표): **2023년~** 확인, 2022년은 없음. 구종·구속 텍스트는 ❓ 연도별 실측 필요 | 근거 A ("2022 carries no tracking data") |
| 규모 | 한 경기 약 300구, 한 팀 144경기 약 4.4만 구, 리그 전체 약 22만 구/시즌 | 근거 A (2023~2025: 2,160경기 661k구) |
| 요청 수 | 경기당 이닝 수만큼(약 9.5회) → 한 팀 시즌 ≈ 1,400요청 ≈ 35~45분(1~2초 간격) | |

→ **Savant식 시각화 범위를 줄일 필요 없음.** 구종 비율·구속 분포·스트라이크존 히트맵 모두 가능(2023년 이후).
2022년 이전 시즌은 존 히트맵 대신 구종·구속 차트와 kbodata 타구 방향 스프레이 차트로 대체한다(작업지시서 2-4 ⑤).

## 2. URL 패턴

공통: `https://api-gw.sports.naver.com` — 응답 `{"code":200, "success":true, "result":{...}}`
요청 헤더: 브라우저형 `User-Agent`와 `Origin: https://m.sports.naver.com`(없으면 403이라는 보고, 근거 A).
User-Agent에 개인정보는 넣지 않는다.

| 용도 | 요청 | 비고 |
|---|---|---|
| 일정 | `GET /schedule/games?fields=basic,schedule,baseball&upperCategoryId=kbaseball&categoryId=kbo&fromDate=2025-01-01&toDate=2025-12-31&roundCodes=&size=500&page=1` | `size`가 1024 이상이면 10건만 오는 문제 보고 → 500씩 페이지로 (근거 A) |
| 이닝 중계 | `GET /schedule/games/{gameId}/relay?inning={n}` | 1회~마지막 이닝까지 이닝마다 1번 |
| (참고) 선수 시즌 기록 | `GET /statistics/categories/kbo/seasons/{year}/players/{pcode}` | 이번 범위에서는 안 씀 |

### 경기 ID 대응

| 출처 | 형식 | 예 |
|---|---|---|
| kbodata raw JSON (DB `game.game_id`) | `YYYYMMDD_` + 원정 + 홈 + 더블헤더 | `20250601_OBWO0` |
| KBO 게임센터 `G_ID` (DB `game.kbo_game_id`, 생성 컬럼) | 밑줄 없음 | `20250601OBWO0` |
| 네이버 `gameId` | G_ID + 시즌 4자리 | `20250601OBWO02025` |

네이버 일정에 `reversedHomeAway` 필드가 있고 홈/원정 순서가 뒤집힌 경기가 있다는 보고(근거 B)가 있어,
`crawl/naver_parsers.our_game_id()`는 gameId 문자열을 그대로 자르지 않고 일정의 `homeTeamCode`/`awayTeamCode`로 다시 조합한다. ❓

## 3. 일정 항목 필드 (`result.games[]`)

| 필드 | 뜻 | 사용 |
|---|---|---|
| gameId | 네이버 경기 ID | 중계 요청 |
| gameDate | 경기 날짜 `YYYY-MM-DD` | 선수 매핑(출전일) |
| homeTeamCode / awayTeamCode | KBO 팀코드 (OB, LG, HT …) | 경기 ID 조합, 팀 필터 |
| statusCode | READY / STARTED / RESULT / CANCEL … | |
| statusInfo | `9회말`, `12회초`, `경기취소` | 마지막 이닝 → 중계 요청 횟수 |
| roundCode | `kbo_r` 정규시즌, `kbo_e` 시범, `kbo_as` 올스타, `kbo_ps_wd/sp/po/ks` 포스트시즌 | 정규시즌만 수집 |
| cancel | 취소 여부 | |
| gameTotalCount (result) | 전체 경기 수 | 페이지 계산 |

## 4. 중계 응답 (`result.textRelayData`)

| 필드 | 뜻 |
|---|---|
| inn | 현재(마지막) 이닝 |
| textRelays[] | 블록 목록. **한 이닝 안에서 최신 블록이 앞** → 시간순으로 쓰려면 뒤집는다 |
| homeLineup / awayLineup | `batter[]`, `pitcher[]` — `pcode`, `name`, `batOrder`, `seqno`(1 선발, 2~ 교체). 누적 |
| inningScore | `{home: {"1": "0", ...}, away: {...}}` |
| currentGameState | 현재 상태 (마지막 이벤트 기준) |

### 블록 (`textRelays[]`)

| 필드 | 뜻 |
|---|---|
| title | `3번타자 홍길동`, `1회초 LG 공격` |
| titleStyle | `0` 이닝 헤더, `8` 타자 타석, `2` 대타 등 |
| homeOrAway | `0` 원정 공격(초), `1` 홈 공격(말) |
| textOptions[] | 이벤트 목록 (블록 안에서는 오래된 것이 앞) |
| ptsOptions[] | 이 블록 투구의 트래킹 값 |
| no | 블록 번호 |

### 이벤트 (`textOptions[]`)

| 필드 | 뜻 |
|---|---|
| seqno | 경기 전체 이벤트 순번 (가끔 같은 값이 두 이벤트에 붙음: 교체 + 다음 타자) |
| type | 아래 표 |
| text | 중계 문장: `3구 헛스윙`, `홍길동 : 좌익수 앞 1루타` |
| pitchNum | 타석 내 투구 번호 (type 1) |
| pitchResult | B 볼, T 스트라이크(루킹), S 헛스윙, F 파울, V 번트헛스윙, W 번트파울, H 타격(인플레이) |
| stuff | 구종 한글: 직구, 슬라이더, 체인지업, 커브, 포크, 투심, 커터, 스위퍼, 너클볼, 슬러브, 싱커 (11종, 근거 A) |
| speed | 구속 km/h (문자열) |
| ptsPitchId | `ptsOptions[].pitchId` 와 연결 |
| currentGameState | 이벤트 **후** 상태: ball, strike, out, base1~3(주자 타순 번호), homeScore, awayScore, batter, pitcher(pcode). **값이 모두 문자열** |
| playerChange | 교체 이벤트의 inPlayer / outPlayer |

| type | 뜻 | 우리가 쓰는 방법 |
|---|---|---|
| 0 | 이닝 시작 | 무시 |
| 1 | **투구** | 투구 행 1개 |
| 2 | 선수 교체 | 무시 (대타는 type 8로 처리) |
| 7 | 투수판 이탈·마운드 방문 | 무시 |
| 8 | 타자 등장 | 새 타석 시작 (결과 전이면 대타 → 같은 타석) |
| 13 | 타석 결과 | 타석 종료, 마지막 투구에 결과 문장 기록 |
| 14 | 주루 | 무시 |
| 23 | 득점이 난 타석 결과 | 13과 같음 |
| 24 | 득점 | 무시 |
| 44 | 실책 주석 (직전 투구에 대한 설명) | 무시 |
| 99 | 경기 종료 문구 | 무시 |

### 트래킹 (`ptsOptions[]`, 단위 피트)

| 필드 | 뜻 | DB |
|---|---|---|
| pitchId | ptsPitchId 와 같은 값 | pitch.naver_pitch_id |
| crossPlateX | 홈플레이트 통과 좌우 위치 (포수 시점, 0 = 중앙) | pitch.plate_x |
| crossPlateY | 측정 기준면 (높이가 **아님**, 대부분 0.7083) | — |
| topSz / bottomSz | 타자별 스트라이크존 위·아래 | pitch.sz_top / sz_bot |
| x0, y0, z0 | y=50ft 지점 위치 | (원본에만) |
| vx0, vy0, vz0 / ax, ay, az | 속도 / 가속도 | (원본에만, plate_z 계산에 사용) |
| stance | 타석 방향 L/R | pitch.batter_stance |

**높이(plate_z) 계산**: 등가속도 운동 y(t) = y0 + vy0·t + ½·ay·t² 가 기준면(0.7083ft)에 닿는 시각 t를 구해
z(t) = z0 + vz0·t + ½·az·t² (`crawl/naver_parsers.plate_z`). 같은 계산으로 x를 구하면 네이버 crossPlateX와
5×10⁻⁵ ft 이내로 일치한다는 검증이 있다(근거 A) → 기준면이 플레이트 중간임을 뒷받침.

## 5. 알려진 데이터 문제와 처리

| 문제 | 처리 (crawl/naver_parsers.py) |
|---|---|
| 같은 투구가 다시 전송됨 (pitchNum 중복) | 타석 안에서 pitchNum이 이미 있으면 버림 |
| 반이닝 전체가 다시 전송됨 (seqno가 뒤로 돌아감) | 그 반이닝은 처음 것만 쓰고 나머지 버림 |
| 일부 경기 crossPlateY 값 이상 | 높이 계산에 상수 0.7083 사용 |
| 고의4구는 투구 이벤트 없이 결과만 | 투구 테이블에는 넣지 않음 (타석은 kbodata 쪽에 있음) |
| 3아웃이 주루사로 끝난 타석은 결과 이벤트가 없음 | 반이닝이 바뀌면 타석을 닫음 |

## 6. 선수 매핑 (네이버 pcode ↔ KBO playerId)

- 공개 코드 주석에 "playerCode(KBO 숫자 pcode)"라는 표현이 있고(근거 B), 숫자 pcode가 KBO playerId와 같은 체계로
  쓰인다. → `crawl/naver_relay.py`는 pcode가 숫자이고 매핑표에 있는 playerId면 그대로 쓴다. ❓ 실측으로 비율 확인
- 아니면 라인업의 이름 + 팀 + 시즌으로 `etl/player_mapper.py`(kbodata와 같은 매퍼)를 쓴다.
- 실패한 것은 `data/raw/naver/<시즌>/_report_<팀>.md` 에 (pcode, 이름, 팀) 목록으로 남는다.

## 7. 이용 시 주의

- 공식 공개 API가 아니다(문서 없음). 수업 프로젝트 용도로만, 1~2초 간격·순차 요청으로 수집한다.
  교수님은 데이터 수집 방법은 신경 쓰지 않는다고 말씀하셨으며, 별도 문의는 불필요하다([확인 기록](email_professor.md)).
- 원본 JSON(`data/raw/naver/`)은 레포에 올리지 않는다(.gitignore).

## 근거 (공개 자료)

| 기호 | 출처 | 확인한 내용 |
|---|---|---|
| A | GitHub `slothman3878/kbo_pbp_naver_sports` (README, kbo_pbp/naver.py, relay.py, statcast.py, schema.yaml) | 엔드포인트, 헤더, type 코드, pitchResult, 구종 11종, ptsOptions 필드·단위, 기준면 0.7083, 2022 트래킹 없음, 데이터 결함, 2023~2025 규모 |
| B | GitHub `hwinside/kbo-everyday` (specs/pitch-by-pitch.md, specs/live-stats-tab.md, specs/kbo-naver-full-dual-source.md, src/lib/naver-relay-counts.ts) | 2026-07 실경기 실측: type 1 투구 필드(stuff, speed, pitchResult, currentGameState), gameId = KBO G_ID + 연도, textRelays 최신순, reversedHomeAway |
| C | GitHub `jeonbyeongmin/kbo-cli` (src/types.ts, src/api.ts) | ptsOptions ↔ textOptions 연결(ballcount/pitchNum), crossPlateX 단위(ft, 포수 시점) |
| D | GitHub 코드 검색: `Jeon-byeong-yoon/kbo-ai-brief` (docs/DATA-SOURCES.md) | crossPlateY는 높이가 아님, 높이는 궤적으로 계산 |
| E | GitHub 코드 검색: `yagongso/KBO_crawler`, `kparkk2/KBO_pbp_text_crawler` (download.py) | ptsOptions 필드 목록(crossPlateX, topSz, pitchId, vx0 …) |

## ❓ 맥에서 실측할 것 (crawl/naver_probe.py)

- [ ] 2025 경기 1회 중계에 stuff/speed/pitchResult/ptsOptions가 모두 있는지
- [ ] 연도별 제공 범위: 2018, 2020, 2022, 2023, 2025 (구속·구종 / 좌표)
- [ ] 헤더 없이 요청하면 403인지 (예의상 브라우저형 UA + Origin 유지)
- [ ] pcode가 KBO playerId와 같은지 (naver_relay.py 리포트의 `pcode` 매핑 비율)
- [ ] gameId 팀 순서가 뒤집힌 경기가 실제로 있는지
