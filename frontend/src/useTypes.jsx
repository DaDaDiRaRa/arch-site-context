// 2계층 용도 카탈로그 — 백엔드 /use-types (app/data/use_type_map.json)가 단일 진실.
// 법적 용도(건축법 별표1)를 그룹핑해 드롭다운에 노출, 백엔드가 분석 프로파일로 해석.
// 데이터 한정 용도(관광·산업·물류 등)는 ⚠ 캐비엇 표시 — 인구통계로 차별화 못 함(정직).
import { useEffect, useState } from "react";

// 기본 선택값 — 가장 흔한 법적 용도 (프로파일 '주거'로 해석됨).
export const DEFAULT_USE_TYPE = "공동주택";

let _cache = null;
let _promise = null;

function loadCatalog() {
  if (_cache) return Promise.resolve(_cache);
  if (!_promise) {
    _promise = fetch("/use-types")
      .then((r) => r.json())
      .then((j) => (_cache = j))
      .catch(() => (_cache = { groups: [], data_limited: [] }));
  }
  return _promise;
}

export function useUseTypeCatalog() {
  const [cat, setCat] = useState(_cache);
  useEffect(() => {
    let alive = true;
    loadCatalog().then((c) => alive && setCat(c));
    return () => {
      alive = false;
    };
  }, []);
  return cat;
}

// <select> 자식으로 넣는 <optgroup>/<option> 묶음. 각 탭의 select 스타일은 그대로 유지.
export function UseTypeOptions({ catalog }) {
  if (!catalog || !(catalog.groups || []).length) {
    return <option value={DEFAULT_USE_TYPE}>{DEFAULT_USE_TYPE}</option>;
  }
  const limited = new Set(catalog.data_limited || []);
  return (
    <>
      {catalog.groups.map((g) => (
        <optgroup key={g.group} label={g.group}>
          {g.uses.map((u) => (
            <option key={u} value={u}>
              {limited.has(u) ? `${u} ⚠` : u}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );
}
