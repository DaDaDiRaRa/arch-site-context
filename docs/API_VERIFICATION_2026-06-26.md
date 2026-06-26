# API 연결 검증 결과 — 2026-06-26

> `.env` 의 17개 키를 **실제 엔드포인트로 호출**해 연결 상태를 분류한 결과.
> 재현: `.venv\Scripts\python.exe scripts\verify_apis.py` (+ 정밀 2차 `scripts\verify_apis2.py`).
> 상세 JSON: `out/verify_apis_result.json`. 키 값은 어디에도 출력하지 않음.

검증 방식: 키별 정상 응답 + 데이터 수신 / 표준 오류코드 / HTTP 게이트웨이 응답을 직접 받아 판정.
추정 없음 — 모두 실호출 근거 (절대 원칙 1·3).

---

## 0. 한눈에 (요약)

| 상태 | 개수 | 항목 |
| --- | --- | --- |
| ✅ 정상 작동 | **9개 키** | KAKAO · VWORLD · KOSIS · JUSO · ANTHROPIC · KMA · RONE · SEOUL · NEIS · KOPIS |
| 🟡 키는 유효하나 데이터셋 미승인 | **DATA_GO_KR 일부** | 에어코리아·아파트매매·공시지가·건축물대장·경로당·어린이집·문화기반시설 |
| 🔴 키/계정 활성화 안 됨 | **2개 키** | TMAP(게이트웨이 거부) · LIBRARY(API 미활성) |
| 🔴 키 인증 실패 | **1개 키** | CULTURE(kcisa 401 + data.go.kr 미승인) |
| ⚫ 애초에 REST API 없음 | **1개 키** | SBIZ365(대시보드/파일만) |
| ⬜ 범위 밖(보류) | **1쌍** | EUM(규제 → arch-law-diagnose 담당) |

**핵심 결론 3가지**
1. **앱 본체(모드 A·B·수급·비교·물어보기)는 정상.** pytest 65개 전부 통과, 5개 핵심 키 + 신규 5개 포털 키 라이브.
2. **이미 코드로 붙여둔 data.go.kr 확장(에어코리아·실거래가·공시지가·건축물대장)은 전부 "데이터셋 미승인"이라 실데이터가 안 나온다.** 코드는 graceful 처리되어 앱은 안 죽지만, 광고한 항목이 조용히 빈다.
3. **마스터리스트의 "키 발급 완료/✅" 일부가 실제와 불일치** (SBIZ365·TMAP·LIBRARY·CULTURE·아파트매매 등). 아래 §5에서 정정.

---

## 1. ✅ 정상 작동 (실데이터 확인)

| 키 | 용도 | 검증 신호 |
| --- | --- | --- |
| `KAKAO_KEY` | 주소→좌표, 반경검색 (모드 B) | documents>0, 영등포구 좌표 수신 |
| `VWORLD_KEY` | 위성타일 WMTS (모드 B) | `image/jpeg` 타일 바이트 수신 (z15) |
| `KOSIS_KEY` | 지역통계 (모드 A) | DT_1B04005N 66행, 2025년 수신 |
| `JUSO_API_KEY` | 도로명주소 폴백 (P1.6) | errorCode=0 (※ dev키 — 운영 전 교체, DEFERRED D2) |
| `ANTHROPIC_API_KEY` | Claude 서술·물어보기 | count_tokens OK, model=claude-opus-4-8 |
| `KMA_KEY` | 기상청 단기예보 (#97~101) | apihub `authKey`, resultCode=00 |
| `RONE_KEY` | 부동산원 R-ONE (#39~41) | SttsApiTblData `KEY=`, 데이터행 수신 |
| `SEOUL_API_KEY` | 서울 열린데이터 (#22 등) | INFO-000 |
| `NEIS_KEY` | 학교현황 (#117) | INFO-000, 학교행 수신 |
| `KOPIS_KEY` | 공연시설 (#134b) | `prfplc` db 행 수신 |

추가로 **OSM Overpass**(#161, 키 불필요)는 모드 B(`facilities.py`)에 이미 연결되어 작동.

---

## 2. 🟡 DATA_GO_KR_API_KEY — 키는 유효, 데이터셋별 승인이 갈린다

**키 자체는 정상.** 같은 키로 아래가 실데이터를 반환한다:

| 데이터셋 | 엔드포인트 | 결과 |
| --- | --- | --- |
| 상가(상권)정보 반경 (#29 실API) | `B553077/.../storeListInRadius` | ✅ WORKS (sangwon 데모) |
| 응급의료기관 (#125) | `B552657/ErmctInfoInqireService` | ✅ resultCode 00 |
| HIRA 병원정보 (#123) | `B551182/hospInfoServicev2` | ✅ resultCode 00 |
| 토지 매매 실거래 | `1613000/RTMSDataSvcLandTrade` | ✅ OK |
| 연립다세대 매매 | `1613000/RTMSDataSvcRHTrade` | ✅ OK |
| 아파트 전월세 | `1613000/RTMSDataSvcAptRent` | ✅ OK |
| 오피스텔 전월세 | `1613000/RTMSDataSvcOffiRent` | ✅ OK |

**그러나 코드로 이미 붙여둔 데이터셋은 전부 미승인(403/500)이라 실데이터가 안 나온다:**

| 데이터셋 | 호출 코드 | 받은 응답 | 의미 |
| --- | --- | --- | --- |
| **에어코리아 대기질 (#86)** | `services/airkorea.py` (matrix `_common` PM2.5/PM10/O3/NO2) | **403 Forbidden** | B552584 활용신청 미승인. ⇒ **모든 `/analyze` 가 광고한 대기질 4항목을 조용히 비움** |
| **아파트 *매매* 실거래 (#33)** | `services/molit.py fetch_apt_trade` → `RTMSDataSvcAptTradeDev` | **403 Forbidden** | 아파트'매매'는 미승인 (승인된 건 위 4종). ⇒ `/site` 실거래 빈값 |
| **표준지 공시지가 (#35)** | `molit.py fetch_land_price` | **500 Unexpected** | 미승인. ⇒ `/site` 공시지가 None |
| **건축물대장 (#48)** | `molit.py fetch_building` | **500 Unexpected** | 미승인. ⇒ `/site` 건물정보 None |
| 경로당·마을회관 (§8.5 P1.5b) | `scripts/check_dataportal.py` | code 30 | 활용신청 미승인 (기존 DEFERRED D1 그대로) |
| 어린이집 표준데이터 (#126) | (probe) | code 30 | 미승인 |
| 문화기반시설총람 (#134) | `B553457/rgnCltrFcltExmn` | 500 | 미승인 (§4 참조) |
| 공장창고 등 매매 | `RTMSDataSvcNrgTrade` | 403 | 마스터리스트엔 [승인]이나 실패 — 전파지연/엔드포인트 재확인 필요 |

> **판정 근거**: data.go.kr 는 *미승인 데이터셋*에 대해 게이트웨이가 **403 Forbidden / 500 Unexpected errors**(평문)로 막고, *키 자체가 틀리면* 표준 XML `resultCode=30` 을 준다. 우리는 30(키문제)이 아니라 403/500(데이터셋 권한)을 받았고, 동일 키로 7종이 정상 → **키 OK, 데이터셋 승인이 갈린 것**으로 확정.

### 2-1. 발견한 코드 이슈 (승인되면 바로 문제 될 것)
- `app/services/airkorea.py` : 측정소 목록을 `ArpltnInforInqireSvc/getMsrstnList` 로 호출 — `getMsrstnList` 의 정식 서비스는 **`MsrstnInfoInqireSvc`**. 측정값은 `ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty` 가 맞음. **승인 후 측정소 검색이 실패할 경로** → 서비스 경로 분리 필요.

---

## 3. 🔴 키/계정이 아직 활성화되지 않음 (사용자 액션 필요)

| 키 | 증상 | 원인 추정 | 할 일 |
| --- | --- | --- | --- |
| **`TMAP_KEY`** | 모든 호출 `403 / INVALID_API_KEY` (쿼리·헤더 둘 다, POI·reverse 둘 다) | SK OpenAPI 앱이 미승인/미활성 또는 해당 API 미구독 | SK Open API 콘솔에서 앱 상태·발급키 재확인, 사용할 API(대중교통/지오) 활성화 |
| **`LIBRARY_KEY`** | `"API 활성화 상태가 아닙니다"` (엔드포인트·키 자체는 인식됨) | data4library 계정의 API 활성화/승인 대기 | 도서관정보나루 마이페이지에서 OpenAPI 활성화 승인 확인 |

---

## 4. 🔴 CULTURE_KEY — 두 경로 모두 막힘 (#134 문화기반시설)

문화기반시설 데이터는 **포털이 둘로 갈린다**:
- **data.go.kr `B553457/rgnCltrFcltExmn`** (전국문화기반시설총람) → `DATA_GO_KR_API_KEY` 필요. 현재 **500(미승인)**.
- **kcisa `api.kcisa.kr/openapi/API_CCA_###`** → `CULTURE_KEY`(kcisa 키)로 호출. 그러나 **API_CCA_145/148/149 전부 401 Unauthorized**.

게다가 조사 결과 **`API_CCA_###` 계열은 공연·전시·문학 등 *콘텐츠* 데이터셋이지 "문화기반시설 총람"이 아니다.** 즉:
- 진짜 #134(문화기반시설 총람)는 **data.go.kr B553457** 경로 → 거기에 `DATA_GO_KR_API_KEY` 로 **활용신청**해야 함.
- `CULTURE_KEY` 로 쓰려면 → kcisa에서 **실제 구독한 데이터셋의 정확한 API_CCA 번호**를 마이페이지 Swagger에서 확인해야 함 (현재 401 = 미구독/미인증).

> **결정 필요**: #134 를 (A) data.go.kr B553457 활용신청으로 갈지, (B) kcisa CULTURE_KEY 의 정확한 데이터셋으로 갈지. 둘 중 하나 확정 전엔 #134 연결 불가.

---

## 5. ⚫ SBIZ365_KEY — REST API 자체가 없음 (구조 재검토)

- 소상공인365(`sbiz365.or.kr` / `bigdata.sbiz.or.kr`)는 **대시보드 + 파일(CSV/PDF) 다운로드**만 제공. **상권분석 매출·점포수·폐업률·창업률·빈상가(#29·#30)의 JSON/XML REST API 가 없다.**
- `SBIZ365_KEY` 는 **포털/iframe 접근용**이지 fetch serviceKey 가 아님.
- 상권의 *실제 REST API* 는 이미 쓰는 **data.go.kr `B553077` 상가(상권)정보**(점포 목록·업종·경계)뿐 — 단, 이건 매출/폐업 지표가 아니라 *점포 분포* 데이터.
- §2 차별점 체크리스트 1번("실제 API 호출하는가") 불충족 → **#29·#30 은 'file-data/대시보드' 로 재분류**. 매출·창업·폐업 지표가 꼭 필요하면 fileData(15143517·15151047) **주기적 CSV 적재**가 현실적 경로.
- `B553077` 추가 활용 가능 엔드포인트: `storeListInDong`(행정동)·`storeListInRectangle`(bbox)·`largeUpjongList/middleUpjongList/smallUpjongList`(업종코드) — 수급진단 업종분류에 유용.

---

## 6. ⬜ EUM(EUM_ID/EUM_KEY) — 터읽기 범위 밖 (보류)

- 토지이음 = 용도지역·행위제한 = **규제정보**. INTEGRATION.md §2: 규제는 **arch-law-diagnose** 담당, 터읽기 재구현 금지.
- DEFERRED D6: 제품 정체성 결정 보류 + EUM 엔드포인트 미검증. → 이번 검증에서도 의도적으로 SKIP. 진행 결정 시 별도 검증.

---

## 7. 앱 본체 상태 (does it work?)

- **pytest: 65 passed** (157s). 모드 A·B·diagnose·compare·ask·tiles·cache·geo·resolve·narrative 전부 통과.
- 라우터 8종 등록 확인 (`/health /facilities /facilities/map /analyze /matrix /diagnose /compare /ask /site`).
- **`/site` 는 CLAUDE.md 엔드포인트 표에 없는 신규** + 데이터 3종(실거래/공시지가/건축물대장) 전부 미승인 → 현재 **빈 응답(graceful)**. 테스트도 없음. ⇒ 데이터셋 승인 전까지는 사실상 비활성.
- 즉 **"이미 검증된 기존 기능"은 멀쩡**하고, **"새로 키 붙인 확장"이 데이터셋 승인/활성화 단계에서 막혀 있는** 상태.

---

## 8. 우선순위 액션 리스트

**A. 사용자만 풀 수 있는 것 (포털 액션)**
1. data.go.kr 활용신청 — 코드가 이미 기다리는 4종 우선: **에어코리아 대기오염정보(B552584)·표준지공시지가·건축물대장(BldRgstService_v2)·아파트매매(RTMSDataSvcAptTradeDev)**. (또는 `/site`/`airkorea`를 *이미 승인된* 토지매매·전월세·연립다세대로 재배선 — §8-B2)
2. **TMAP**: SK 콘솔에서 앱 활성화/키 재확인.
3. **LIBRARY**: data4library OpenAPI 활성화 승인 확인.
4. **CULTURE(#134)**: data.go.kr B553457 활용신청 **또는** kcisa 구독 데이터셋의 정확한 API_CCA 번호 확보 (택1).
5. **경로당·어린이집** 표준데이터: data.go.kr 활용신청 (code 30).

**B. 코드로 풀 수 있는 것 (내가 할 수 있음)**
1. `airkorea.py` 측정소 서비스 경로 분리 (`MsrstnInfoInqireSvc`) — 승인 후 동작하도록 선반영.
2. **승인된 data.go.kr 데이터로 재배선**: `molit.py`/`/site` 를 미승인 아파트매매·공시지가·건축물대장 대신 *작동하는* 토지·전월세·연립다세대 실거래 + (HIRA·응급의료) 로 우선 구성.
3. **신규 정상 키 5종 서비스 골격 추가**(P14): KMA(날씨)·RONE(부동산지수)·SEOUL(생활인구)·NEIS(학교)·KOPIS(공연시설) — 검증된 엔드포인트로 클라이언트 작성.
4. `verify_apis.py` 를 CI/주기 점검 자산으로 유지 (키 만료·승인전파 감지).

**C. 마스터리스트/문서 정정** (§5·§4 반영, 아래 §9)

---

## 9. API_MASTER_LIST.md 정정 필요 항목 (실측 불일치)

| # | 현재 표기 | 실측(2026-06-26) |
| --- | --- | --- |
| #29·#30 상권분석·빈상가 | "✅ 키 발급 완료 SBIZ365_KEY" | ⚫ **REST API 없음** — 대시보드/파일만. SBIZ365_KEY=포털용 |
| #33 아파트 실거래가 | ✅ | 🟡 아파트'매매' **미승인**(403). 전월세는 승인 |
| #35 공시지가 / #48 건축물대장 | ✅ / ✅⚠️ | 🟡 **미승인**(500) |
| #86 에어코리아 | ✅ | 🟡 **미승인**(403) |
| #103 TMAP | "✅ 키 발급 완료" | 🔴 **키 게이트웨이 거부**(앱 미활성 추정) |
| #122 도서관정보나루 | 🔑 | 🔴 키 있으나 **API 미활성** |
| #134 문화기반시설 | "✅ 키 발급 완료 CULTURE_KEY" | 🔴 **두 경로 다 막힘** (data.go.kr 미승인 + kcisa 401) |
| #97~101 기상청 | 🔑 | ✅ **작동**(KMA_KEY) |
| #39~41 부동산원 | 🔑 | ✅ **작동**(RONE_KEY) |
| #117 학교 | "✅ NEIS_KEY" | ✅ 확인 |
| #134b 공연시설 KOPIS | "✅ KOPIS_KEY" | ✅ 확인 |

---

*검증: scripts/verify_apis.py, scripts/verify_apis2.py (2026-06-26). 키 비노출.*
</content>
