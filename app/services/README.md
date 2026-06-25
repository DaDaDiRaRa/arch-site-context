# services/

서버 함수(흐름의 각 단계). CLAUDE.md 5장 아키텍처 기준.

| 모듈 | 모드 | 역할 | 상태 |
|---|---|---|---|
| `kakao.py` | B | `resolve_coord` 주소→좌표 / `search_keyword` / `search_keyword_complete`(45건 상한 회피 적응분할) | ✅ P1·P1.5 |
| `geo.py` | B | `haversine_m` 거리 / `radius_band` 밴드 / `bbox`·`split_rect` 분할 | ✅ P1·P1.5 |
| `juso.py` | A·B | `search_address` 행안부 도로명주소 정규화 + 법정동코드(admCd) | ✅ P1.6 |
| `resolve.py` | A·B | `resolve_address` 카카오(주)+JUSO(폴백) → 좌표 + 법정동·시군구코드 | ✅ P1.6 |
| `facilities.py` | B | 오케스트레이션: 검색→거리→밴드→중복제거→집계 | ✅ P1·P1.5 |
| `gov_data.py` | B | 공공데이터포털 경로당 등 공식시설 보강 | ⏸ 보류 (data.go.kr 키 미등록 code 30) |
| `map_compose.py` | B | `compose_map` VWorld 타일 + 핀 + 원 + 범례 | ⬜ P2~P3 |
| `region.py` | A | `resolve_region` (resolve.py의 sgg_code 활용) | ⬜ P4 |
| `select.py` | A | `select_items` matrix.json 적용 | ⬜ P4 |
| `kosis.py` | A | `fetch_stats` KOSIS 조회 + 캐시 | ⬜ P5 |
| `implications.py` | A | `derive_implications` implications.json 규칙 | ⬜ P4 |
| `narrative.py` | A | `compose_narrative` Claude 1회 + 규칙 폴백 | ⬜ P6 |
| `diagnose.py` | P11 | `build_diagnosis` 수급진단 — A수요(stats)×B공급(facilities) 교차, supply_demand.json 규칙. `cross_rules`는 P9 공용 | ✅ P11 |
| `compare.py` | P9 | `build_comparison` 여러 후보지 A·B·P11 나란히 (후보지당 resolve·시설검색 1회, 실패 격리). `gather_bundle`은 P10 공용 | ✅ P9 |
| `ask.py` | P10 | `build_answer` 물어보기 — 번들(A·B·P11) 위에서만 그라운디드 답변, 확인불가 하드블록, web=True 시 내장 web_search 폴백(외부·참고) | ✅ P10 |

원칙: 값은 실제 API에서 추출, 숫자는 코드/규칙, 데이터 밖이면 '확인 불가'로 멈춤.

## 외부 키 현황 (.env)

- `KAKAO_KEY` ✅ 검증 · `JUSO_API_KEY` ✅ 검증(개발키 — 운영 배포 시 운영키 필요)
- `DATA_GO_KR_API_KEY` ⏸ code 30(미등록) — 데이터셋 활용신청·전파 대기. 엔드포인트/필드는 확정:
  `tn_pubr_public_vill_hall_sen_cent_api` (전국마을회관및경로당표준데이터), 필드 `FLCT_NM`·`LAT`·`LOT`·`LCTN_ROAD_NM_ADDR`·`BUSI_COD_NM`
- `EUM_*`(토지이음) ⬜ 정체성 결정 보류 · `VWORLD_KEY` ⬜ P2 · `KOSIS_KEY` ⬜ P5
