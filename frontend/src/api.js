// 백엔드 호출 헬퍼. 개발 시 Vite 프록시로 상대경로 호출 (CORS 없음).
// ErrorBlock({code,message}) 하드블록은 ApiError 로 던져 UI 가 구분 처리.

export class ApiError extends Error {
  constructor(message, { code, status } = {}) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function post(path, body) {
  let res;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError("서버에 연결할 수 없습니다. 백엔드(8000)가 떠 있는지 확인하세요.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // 하드블록: {code, message}  또는 FastAPI {detail}
    if (data && data.code) throw new ApiError(data.message || "확인 불가", { code: data.code, status: res.status });
    const detail = typeof data.detail === "string" ? data.detail : "요청을 처리하지 못했습니다.";
    throw new ApiError(detail, { status: res.status });
  }
  return data;
}

export const analyze = (address, use_type, year, resolution = "시군구", radius = 1000) =>
  post("/analyze", { address, use_type, year: year ?? null, resolution, radius });

export const facilities = (address, kinds, radii) =>
  post("/facilities", { address, kinds, radii });

export const facilitiesMap = (address, kinds, radii, basemap = "vworld") =>
  post("/facilities/map", { address, kinds, radii, basemap });

export const diagnose = (address, radius, resolution = "시군구") =>
  post("/diagnose", { address, radius, resolution });

export const compare = (addresses, use_type, radius, kinds) =>
  post("/compare", { addresses, use_type, radius, kinds });

export const ask = (address, question, use_type, radius, kinds, web = false) =>
  post("/ask", { address, question, use_type, radius, kinds, web });

export const site = (address) =>
  post("/site", { address });

export const seed = (address, radius = 1000) =>
  post("/seed", { address, radius });

export const readout = (address, project_type = "재건축", use_type = "주거") =>
  post("/readout", { address, project_type, use_type });
