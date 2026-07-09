# INTEGRATION.md — 터읽기 ↔ 형제 앱 연결 설계 메모

> 작성 2026-06-26. 같은 사용자(건원)가 만든 3개 앱을 하나의 **대지분석 보드**로 연결하는 설계.
> 지금은 메모만 — 실제 코드는 터읽기 P12 이후. 키 신청 중에는 이 문서로 경계만 고정한다.

---

## 1. 세 앱은 한 보드의 세 파트

주소 한 줄로 채우는 '대지 분석 보드'를 영역별로 나눠 가진다. **서로 중복 구현 금지.**

| 앱 | 레포 | 담당 영역 | 핵심 출력 |
| --- | --- | --- | --- |
| **터읽기** | `arch-site-context` | 인문·생활맥락 (인구·시설·수급) | facts·counts·수급진단·문단 |
| **arch-law-diagnose** | `arch-law-diagnose` | 규제·법규 (건폐율·용적률·높이·일조·주차·조경·소방) | 8카테고리 GREEN/YELLOW/RED + 종합점수 |
| **arch-law-graph** | `arch-law-graph` | 법령 지식 (조문 관계 + 자연어 질의) | graph.json + RAG 답변 |

```text
주소 1줄
  → 터읽기           : 인구·시설·수급진단        (사람·생활)
  → arch-law-diagnose: 용도지역·용적률·높이·일조  (규제)
  → arch-law-graph   : 근거 법령 조문            (지식)
  = 완성된 대지분석 보드 (project_seed.json 한 덩어리)
```

---

## 2. 경계 — 터읽기가 "만들지 않는" 것 (중복·원칙위반 방지)

아래는 **arch-law-diagnose가 이미 완성**했다. 터읽기에서 재구현하면 ① 중복 ② 터읽기 절대원칙 위반("규제 해석은 사람", 차별점 체크리스트).

- **용적률·건폐율·높이·일조 한도** → diagnose `far.py`·`coverage.py`·`height.py` (LURIS+EUM 교차검증, 법제처 `LAW_API_KEY`로 조례까지).
- **"제2종일반주거 → 몇 층"** 류 계산·해석 → diagnose 영역 + 물리 매싱은 아예 보드 밖(Forma 트랙).
- 따라서 **터읽기는 법제처 API 발급 불필요** (diagnose가 이미 보유).

> P14("토지이용규제를 수급진단에 연결")은 터읽기가 직접 LURIS/조례를 파싱하는 게 아니라,
> **diagnose 결과(용도지역 사실)를 받아와** 인문 맥락과 엮는 방향으로 좁힌다.

---

## 3. 터읽기가 형제 앱에서 **가져다 쓸 것** (검증된 코드 재사용)

arch-law-diagnose에 터읽기 원칙과 정확히 일치하는, 이미 검증된 코드가 있다.

| 우선 | 가져올 것 | 출처 | 터읽기에서의 쓸모 |
| --- | --- | --- | --- |
| 1 | `request_with_retry` (재시도/백오프, 5xx만 2회·4xx 즉시) | diagnose `services/http_retry.py` | 터읽기 KOSIS·카카오·VWorld 호출 견고화 (현재 미보유) |
| 2 | `data_quality` 필드 + `DataQualityBanner` (API사용·fallback·stale 명시) | diagnose | 터읽기 `source`/`notes` 정직성(절대원칙 3·4) 강화 참고 |
| 3 | `zone_use_normalizer.py` (용도지역 19종+별칭 61) / `vworld_client.py` WFS | diagnose | 터읽기가 용도지역을 *사실로* 표시할 때 — 단 diagnose가 이미 하므로 **복붙보다 결과 수신 권장** |

---

## 4. 연결 방식 — project_seed.json (터읽기 CLAUDE.md "나중에 project_seed JSON" 자리)

세 앱이 각자 키·캐시를 따로 굴리지 말고, **공유 좌표·법정동코드를 기준으로 결과를 합친다.**

```jsonc
// project_seed.json — 주소 1회 해석 → 세 앱이 각자 채움 (schema_version 'project_seed/1.0')
{
  "schema_version": "project_seed/1.0",
  "site": { "address":"...", "lat":0, "lon":0, "pnu":"...", "sgg_code":"11560" },
  "context":  { /* 터읽기: /board 결과(BoardResult, 'board/1.0') 또는 board_brief */ },
  "law":      { /* arch-law-diagnose: 8카테고리 GREEN/YELLOW/RED + 용도지역 사실 */ },
  "knowledge":{ /* arch-law-graph: 근거 조문 노드 id 목록 */ },
  "base_date": "..."
}
```

- **좌표·주소 해석은 1곳에서** (카카오/JUSO) → 세 앱이 같은 `site`를 공유 → 키·호출 중복 제거.
- diagnose가 이미 가진 **VWorld WFS·LURIS·EUM·법제처 결과를 터읽기가 호출해 받는** 구조 →
  터읽기는 규제 데이터를 *재취득하지 않는다.*

### 계약 확정 (2026-07-09, T 시리즈 2단계) — 터읽기는 **provider**, 조립은 소비자·허브·Claude가

- **표준 페이로드 = `POST /board`** (`BoardResult`, `schema_version:"board/1.0"`). facts(전국=100 지수·근접도)·수급진단·재해·교차시사점(S2)·**설계 드라이버(T2)**·종합해석(S4 ①사실 ②AI의견)·coverage. 이게 터읽기의 `context` 블록.
- **압축 투영 `POST /board {brief:true}`** (`board_brief`, `board_brief/1.0`) — 원시 seed context(상권 수천건 목록 등) 제거, 해석 층만 (~66KB→~7KB). **제안서·프롬프트·MCP 반환·형제앱 주입용.**
- **봉투 `board_to_project_seed(board, law, knowledge)`** (`services/board_contract.py`) — /board 결과를 `ProjectSeed`로 감싸 law·knowledge 슬롯을 형제앱에 남김. kw-ai-hub 파이프라인·site-model 결합용.
- **경계 (§2 준수)**: brief 는 ①사실종합·②AI판단을 모두 담되, **competition 등은 제안서에 ②AI판단을 직접 전재하지 않는다**(이중 AI 의견·출처 흐림 방지) — 사실+드라이버+①까지가 권장. 터읽기는 드라이버(재료)까지, 제안서 컨셉안은 competition 영역.
- **소비 경로 3종**: ① 앱→앱 = `POST /board`(HTTP, competition 등) · ② Claude/에이전트 = 터읽기 MCP 서버(3단계) · ③ 데스크톱(kbs_topomap 등) = project_seed 파일 export.
- **✅ competition 연동 완료 (2026-07-09)**: competition_comparison 이 `/board {brief:true,synthesize:false}` pull → 수주 제안서 대지분석을 실측화. 형제 레포 변경 `services/teoilgi_client.py`·`routers/brief.py`·`services/brief_proposal.py`, env `TEOILGI_BOARD_URL`(기본 Cloud Run). synthesize=false 라 ②AI판단 미전달(경계). 실HTTP E2E·테스트 무회귀 검증.
- 연결 트리거 지점(향후): 터읽기 `/compare`·`/ask` 번들에 `law` 블록을 옵션으로 첨부.

---

## 5. 키·신청 함의 (지금 진행 중인 작업과 직접 연관)

- **VWorld** (2026-06-26 실측 검증): 터읽기 개발키(`A9E1…`, 만료 2026-12-26)는 **모든 활용 API 보유**
  (WMTS + 2D데이터 포함). 즉 **키 하나로 위성타일 + 2D데이터 둘 다 됨.**
  - **역할 분담**: *규제* 레이어(용도지역·지적도·도로폭)는 diagnose 영역. 하지만 *시설* 레이어
    (아동복지시설 `LT_P_MGPRTFC` 등)는 **터읽기 모드 B 보강 영역**(카카오 누락 공식시설, CLAUDE.md §8.5 경로당 정신).
  - **작동 레시피** (서울 아동복지시설 6건 실조회 성공):
    ```
    GET https://api.vworld.kr/req/data
      service=data&request=GetFeature&data=<레이어ID>&key=<VWORLD_KEY>
      domain=arch-site-context-30350777436.asia-northeast3.run.app   ← ★등록 서비스URL과 일치 필수
      geomFilter=BOX(lon,lat,lon,lat)   ← 필수(없으면 INVALID_RANGE)
      geometry=true&crs=EPSG:4326&format=json
    ```
    - ★함정: `INCORRECT_KEY` 에러 = 권한 아님, **domain 파라미터가 등록 URL과 불일치**일 때 남. WMTS는 domain 없이도 되지만 `/req/data`(2D)는 엄격.
    - 속성: `fac_nam`(시설명)·`cat_nam`(분류)·`fac_n_add`(도로명)·`fac_o_add`(지번)·`fac_tel`. `geometry=true`면 Point 좌표[lon,lat].
  - ⚠️ 개발키→운영키 전환 시 "실사용 API만" 심사 → 2D데이터는 "모드 B 공식시설 조회"로 사유.
- **법제처(`LAW_API_KEY`)**: 터읽기 발급 불필요 (diagnose 보유).
- **공유 후보 키**: ANTHROPIC·KAKAO는 세 앱 공통 → Cloud Run Secret Manager에서 공유 가능.

---

## 6. 다음 (P12 들어갈 때)

1. ✅ **완료 (2026-06-29)** `site` 해석 1곳 공통화 → `project_seed.json` 스키마 확정.
   - `app/schemas/project_seed.py` `Site`/`ProjectSeed` (이 문서 §4 계약 그대로).
   - `app/services/site_seed.py` `build_site`(resolve 1곳 + VWorld pnu)/`build_project_seed`.
2. ✅ **완료 (2026-06-29)** `request_with_retry` 이식 → `app/services/http_retry.py` (5xx·네트워크만 재시도, 4xx 즉시). 단위테스트 5건.
   - ⬜ 후속: 기존 외부호출(kosis·kakao·vworld·molit 등)에 점진 적용.
3. ⬜ diagnose에 "용도지역 사실만 반환하는 가벼운 엔드포인트" 요청 → 터읽기 P14가 소비.
4. ⬜ 보드 합본 뷰(터읽기 프론트)에서 `law` 블록을 링크/임베드.
   - ⬜ 터읽기 `/seed` 엔드포인트(build_project_seed로 site+context 반환) — 합본 진입점.
