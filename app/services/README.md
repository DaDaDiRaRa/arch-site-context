# services/

서버 함수(흐름의 각 단계). CLAUDE.md §5 아키텍처 기준.

## 핵심 흐름 모듈

| 모듈 | 모드 | 역할 | 상태 |
| --- | --- | --- | --- |
| `resolve.py` | A·B | `resolve_address` 카카오(주)+JUSO(폴백) → 좌표+법정동·시군구코드 | ✅ P1.6 |
| `kakao.py` | A·B | `resolve_coord` 주소→좌표 / `search_keyword_complete`(45건 상한 회피) / `coord_to_hcode`(행정동코드) | ✅ P1·P1.5 |
| `juso.py` | A·B | `search_address` 행안부 도로명주소 정규화+법정동코드(admCd) | ✅ P1.6 |
| `geo.py` | B | `haversine_m` 거리 / `radius_band` 밴드 / `bbox`·`split_rect` 분할 | ✅ P1·P1.5 |
| `facilities.py` | B | 오케스트레이션: 카카오→VWorld(경로당 등)→OSM 병합·거리·밴드·중복제거·집계 | ✅ P1·P1.5b |
| `vworld.py` | B·사이트 | 위성 타일 PNG / `search_vworld`(경로당·노인복지관) / `fetch_land_price`(개별공시지가) | ✅ P2·P1.5b·P14 |
| `map_compose.py` | B | `compose_map` VWorld 타일+핀+원+범례+축척 → PNG | ✅ P3 |
| `stats.py` | A | `collect_facts_by_items` matrix.json+KOSIS+에어코리아 → facts / `collect_common_facts` | ✅ P5 |
| `kosis.py` | A | `fetch_stats` KOSIS 조회+캐시 / `resolve_census_region` census 코드 역추출 | ✅ P5 |
| `airkorea.py` | A | `fetch_air_quality` PM2.5·PM10·O3·NO2 (시도 전체→시군구명 매칭) | ✅ P14 |
| `narrative.py` | A | `compose_narrative` Claude 1회+규칙 폴백 한 문단 서술 | ✅ P6 |
| `diagnose.py` | P11 | `build_diagnosis` 수급진단 — stats×facilities 교차, supply_demand.json 규칙(5개). `cross_rules` P9·P10 공용. `_collect_capacity` 어린이집 정원 보강 | ✅ P11 |
| `compare.py` | P9 | `build_comparison` 여러 후보지 A·B·P11 나란히, 후보지 실패 격리. `gather_bundle` P10 공용 | ✅ P9 |
| `ask.py` | P10 | `build_answer` 그라운디드 답변·확인불가 하드블록·web=True 시 web_search 폴백 | ✅ P10 |

## 신규 서비스 모듈 (/site·/seed 배선)

| 모듈 | 역할 | 출처 | 상태 |
| --- | --- | --- | --- |
| `molit.py` | `fetch_trades`(토지·아파트·연립·전월세 실거래 4종) / `fetch_building`(건축HUB 표제부+총괄표제부) | data.go.kr RTMS / BldRgstHubService | ✅ P14 |
| `kma.py` | `fetch_weather(lat,lon)` 좌표→격자→단기예보 기온·강수확률·하늘 | 기상청 apihub | ✅ P14 |
| `rone.py` | `fetch_price_index(region,statbl)` 지역별 매매가격지수 시계열 최신 | 부동산원 R-ONE | ✅ P14 |
| `neis.py` | `fetch_schools(sido,sigungu,level)` 시군구 학교 목록·종류별 집계 | 교육부 NEIS | ✅ P14 |
| `sangwon.py` | `fetch_store_district(lat,lon,radius)` 반경 내 점포수+업종 대분류 집계 | data.go.kr B553077 | ✅ P14 |
| `seoul.py` | `fetch_living_population(lat,lon)` 행정동별 생활인구 최신가용일 자동 (서울전용) | 서울시 INFO-000 | ✅ P14 |
| `kopis.py` | `fetch_venues(sido,sigungu)` 공연시설 목록·이름 필터 | KOPIS | ✅ P14 |
| `childcare.py` | `fetch_childcare(sgg_code)` 어린이집 개수·총정원(시군구) | 정보공개포털 cpmsapi021 | ✅ P14 |
| `culture.py` | `fetch_culture(sgg_code)` 문화기반시설총람 10종 by_type+total | data.go.kr B553457 | ✅ P14 |
| `site_seed.py` | `build_site`(주소→Site 공유 계약) / `build_project_seed` | 내부 | ✅ P14 |

## 인프라 모듈

| 모듈 | 역할 | 비고 |
| --- | --- | --- |
| `cache.py` | `Cache` 인터페이스(get/set) + `FileCache`(out/kosis_cache) | GCS 교체 가능 |
| `http_retry.py` | `request_with_retry` 5xx·네트워크만 재시도(지수백오프), 4xx 즉시 | 외부 GET 22곳 적용 |
| `osm.py` | Overpass 반경 검색 (카카오 보완, rate-limit 의도 제외) | 무료 |

## 미연결·보류

| 모듈 | 상태 | 이유 |
| --- | --- | --- |
| `gov_data.py` | ⏸ 보류 | data.go.kr 경로당(code 30) → VWorld 검색으로 우회 완료, 불필요 |

## 원칙

- 값은 실제 API에서 추출, 숫자는 코드/규칙, 데이터 밖이면 '확인 불가'로 멈춤 (CLAUDE.md §2)
- 모든 서비스 함수: `(Optional[dict], List[str])` graceful 반환 — 실패해도 앱 안 죽음
- 외부 GET: `http_retry.request_with_retry` 경유 (tiles·osm 제외)
- 키는 `.env`에만, 절대 커밋 금지
