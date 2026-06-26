"""
터읽기 — 상권 분석 데모 (소상공인시장진흥공단 상가(상권)정보 API 실연동)

용도: data.go.kr '소상공인시장진흥공단_상가(상권)정보' API(storeListInRadius)를
      실제로 호출해 화면에 표시 → "API가 실제로 연동된 화면" 캡처용.

실행:  python demo/sangwon_demo.py
열기:  http://localhost:8765   (주소 입력 → 조회 → 캡처)

의존성 없음(파이썬 표준 라이브러리만). 키는 프로젝트 루트 .env 에서 읽음:
  - KAKAO_KEY            : 주소 → 좌표 (카카오 로컬)
  - DATA_GO_KR_API_KEY   : 상가(상권)정보 (소상공인시장진흥공단)
키는 서버에서만 사용 → 브라우저로 노출되지 않음.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
SGIS_BASE = "http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"
KAKAO_ADDR = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KW = "https://dapi.kakao.com/v2/local/search/keyword.json"


def load_env():
    env = {}
    path = os.path.join(ROOT, ".env")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()


def resolve_coord(address):
    """주소 → (lon, lat, 정규화주소). 카카오 주소검색 0건이면 키워드검색 폴백."""
    headers = {"Authorization": "KakaoAK " + ENV.get("KAKAO_KEY", "")}
    for url, key in ((KAKAO_ADDR, "query"), (KAKAO_KW, "query")):
        q = urllib.parse.urlencode({key: address, "size": 1})
        req = urllib.request.Request(url + "?" + q, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        docs = data.get("documents", [])
        if docs:
            d = docs[0]
            name = d.get("address_name") or d.get("place_name") or address
            return float(d["x"]), float(d["y"]), name
    raise ValueError("주소를 좌표로 변환하지 못했습니다: " + address)


def fetch_stores(lon, lat, radius):
    """storeListInRadius 전체 페이지 수집."""
    items, page = [], 1
    total = None
    while True:
        q = urllib.parse.urlencode({
            "serviceKey": ENV.get("DATA_GO_KR_API_KEY", ""),
            "radius": radius, "cx": lon, "cy": lat,
            "type": "json", "numOfRows": 1000, "pageNo": page,
        })
        with urllib.request.urlopen(SGIS_BASE + "?" + q, timeout=20) as r:
            data = json.load(r)
        body = data.get("body", {})
        total = body.get("totalCount", total)
        batch = body.get("items", []) or []
        items.extend(batch)
        if not batch or len(items) >= int(total or 0) or page >= 10:
            break
        page += 1
    return items, int(total or len(items))


def analyze(address, radius):
    lon, lat, name = resolve_coord(address)
    items, total = fetch_stores(lon, lat, radius)
    by_large = Counter(i.get("indsLclsNm") or "미분류" for i in items)
    stores = [{
        "name": i.get("bizesNm"),
        "lcls": i.get("indsLclsNm"), "mcls": i.get("indsMclsNm"), "scls": i.get("indsSclsNm"),
        "addr": i.get("rdnmAdr") or i.get("lnoAdr"),
    } for i in items]
    return {
        "address": name, "lon": lon, "lat": lat, "radius": radius,
        "total": total, "fetched": len(items),
        "by_large": by_large.most_common(),
        "stores": stores[:200],
        "source": "소상공인시장진흥공단 상가(상권)정보 (data.go.kr, storeListInRadius)",
    }


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>터읽기 — 상권 분석</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-slate-100 text-slate-800">
<div class="max-w-5xl mx-auto p-6">
  <header class="mb-5">
    <div class="flex items-baseline gap-3">
      <h1 class="text-2xl font-bold">터읽기 <span class="text-slate-400 font-normal">| 상권 분석</span></h1>
      <span class="text-xs text-slate-500">arch-site-context · 사내 건축 설계팀용</span>
    </div>
    <p class="text-sm text-slate-500 mt-1">대지 주소 반경 내 상가업소를 소상공인시장진흥공단 상가(상권)정보 API로 실시간 조회</p>
  </header>

  <div class="bg-white rounded-xl shadow-sm p-4 flex flex-wrap gap-3 items-end">
    <label class="flex-1 min-w-[260px]">
      <span class="block text-xs text-slate-500 mb-1">대지 주소</span>
      <input id="addr" value="서울특별시 영등포구 국회대로 608"
        class="w-full border rounded-lg px-3 py-2"/>
    </label>
    <label>
      <span class="block text-xs text-slate-500 mb-1">반경</span>
      <select id="radius" class="border rounded-lg px-3 py-2">
        <option value="300">300m</option><option value="500" selected>500m</option>
        <option value="1000">1000m</option>
      </select>
    </label>
    <button id="go" class="bg-blue-600 text-white rounded-lg px-5 py-2 font-semibold hover:bg-blue-700">조회</button>
  </div>

  <div id="status" class="text-sm text-slate-500 mt-4"></div>
  <div id="result" class="hidden mt-4 space-y-4"></div>

  <footer class="text-xs text-slate-400 mt-8 border-t pt-3">
    출처: 소상공인시장진흥공단 상가(상권)정보 (공공데이터포털 data.go.kr) ·
    엔드포인트 storeListInRadius · 좌표해석 카카오 로컬 ·
    서비스 https://arch-site-context-30350777436.asia-northeast3.run.app
  </footer>
</div>

<script>
const $ = s => document.querySelector(s);
async function run() {
  const addr = $("#addr").value.trim(), radius = $("#radius").value;
  $("#status").textContent = "조회 중… (실제 API 호출)";
  $("#result").classList.add("hidden");
  try {
    const res = await fetch("/api/sangwon?address=" + encodeURIComponent(addr) + "&radius=" + radius);
    const d = await res.json();
    if (d.error) { $("#status").textContent = "오류: " + d.error; return; }
    render(d);
    $("#status").textContent = "";
  } catch (e) { $("#status").textContent = "오류: " + e.message; }
}
function render(d) {
  const max = d.by_large.length ? d.by_large[0][1] : 1;
  const bars = d.by_large.map(([k,v]) =>
    `<div class="flex items-center gap-2 text-sm">
       <div class="w-28 text-right text-slate-600 shrink-0">${k}</div>
       <div class="flex-1 bg-slate-100 rounded"><div class="bg-blue-500 h-4 rounded" style="width:${Math.max(3,v/max*100)}%"></div></div>
       <div class="w-12 text-right tabular-nums">${v}</div>
     </div>`).join("");
  const rows = d.stores.map(s =>
    `<tr class="border-b last:border-0">
       <td class="py-1.5 pr-3 font-medium">${s.name||""}</td>
       <td class="py-1.5 pr-3 text-slate-500">${[s.lcls,s.mcls,s.scls].filter(Boolean).join(" › ")}</td>
       <td class="py-1.5 text-slate-500">${s.addr||""}</td>
     </tr>`).join("");
  $("#result").innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      ${card("대지 주소", d.address)}
      ${card("반경", d.radius + "m")}
      ${card("반경 내 상가", d.total.toLocaleString() + "개")}
      ${card("중심 좌표", d.lat.toFixed(5) + ", " + d.lon.toFixed(5))}
    </div>
    <div class="bg-white rounded-xl shadow-sm p-4">
      <h2 class="font-semibold mb-3">업종 대분류 분포</h2>${bars}
    </div>
    <div class="bg-white rounded-xl shadow-sm p-4">
      <h2 class="font-semibold mb-3">상가업소 목록 <span class="text-xs text-slate-400">(상위 ${d.stores.length}건 / 총 ${d.total.toLocaleString()}건)</span></h2>
      <div class="overflow-auto max-h-[420px]">
        <table class="w-full text-sm"><thead class="text-left text-slate-400 sticky top-0 bg-white">
          <tr><th class="py-1.5 pr-3">상호명</th><th class="py-1.5 pr-3">업종</th><th class="py-1.5">주소</th></tr>
        </thead><tbody>${rows}</tbody></table>
      </div>
    </div>`;
  $("#result").classList.remove("hidden");
}
function card(label, val) {
  return `<div class="bg-white rounded-xl shadow-sm p-3">
    <div class="text-xs text-slate-400">${label}</div>
    <div class="text-lg font-semibold mt-0.5">${val}</div></div>`;
}
$("#go").addEventListener("click", run);
$("#addr").addEventListener("keydown", e => { if (e.key === "Enter") run(); });
run();
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if parsed.path == "/api/sangwon":
            qs = urllib.parse.parse_qs(parsed.query)
            address = (qs.get("address", [""])[0]).strip()
            radius = (qs.get("radius", ["500"])[0]).strip()
            try:
                out = analyze(address, radius)
                return self._send(200, json.dumps(out, ensure_ascii=False))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, *a):
        pass  # 콘솔 조용히


if __name__ == "__main__":
    miss = [k for k in ("KAKAO_KEY", "DATA_GO_KR_API_KEY") if not ENV.get(k)]
    if miss:
        print("[경고] .env 에 다음 키가 비어 있음:", ", ".join(miss))
    print(f"터읽기 상권 데모 → http://localhost:{PORT}  (Ctrl+C 종료)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
