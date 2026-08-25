"""건물 매싱 GLB(3D) 출력 — §8.15 두번째 항목의 세번째 산출물(SVG·DXF 다음).

arch-site-model(형제앱)은 `.3dm`(rhino3dm)·`.skp`(SketchUp 코드) 만 지원하고 glTF/GLB는
지원하지 않는다(2026-08-25 직접 소스 확인, `D:\\APPS\\arch-site-model` — `src/pipeline.py`가
`outputs`에서 "3dm"/"skp"만 분기, glb/gltf 문자열은 코드베이스 어디에도 없음). 대신 그 앱이
이미 반환하는 `geometry.buildings[]`(footprint+height, `_build_geometry()`가 만드는 값 —
우리 `map_slides.py`/`map_svg.py`가 이미 쓰는 바로 그 데이터)를 우리가 직접 박스 압출
(extrude)해 GLB로 만든다 — 형제앱 코드 변경 0, 새 의존성은 `pygltflib`(순수 파이썬) 뿐.

좌표계: glTF는 Y-up 우핸드. 우리 로컬미터는 (동=X, 북=Y, 높이=Z 별도 스칼라) ENU식이므로
glTF_pos = (동, 높이, -북) 으로 매핑(동×높이=−북, 우핸드 유지). 각 건물은 별도
Node+Mesh — `extras`에 높이·출처(`data-source-ref`와 같은 취지)를 실어 SVG/DXF 트랙과
동일한 provenance 관례를 유지한다.
"""
from __future__ import annotations

import numpy as np
import pygltflib as g

from app.deck import clients
import app.deck.style as k


def _ear_clip(poly2d: list[tuple[float, float]]) -> list[tuple[int, int, int]]:
    """단순다각형(오목 허용) 이어클리핑 삼각분할 → poly2d 인덱스 삼중항 목록.

    자기교차 없는 단순다각형을 가정(대지모델 footprint는 항상 그렇다). 퇴화 케이스는
    부분 결과라도 반환(크래시 대신 — 절대 원칙 3의 정신: 추정 대신 있는 만큼만).
    """
    n = len(poly2d)
    if n < 3:
        return []
    area = sum(poly2d[i][0] * poly2d[(i + 1) % n][1] - poly2d[(i + 1) % n][0] * poly2d[i][1] for i in range(n))
    idx = list(range(n)) if area >= 0 else list(range(n))[::-1]

    def is_convex(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0

    def point_in_tri(p, a, b, c):
        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = sign(p, a, b), sign(p, b, c), sign(p, c, a)
        has_neg, has_pos = (d1 < 0 or d2 < 0 or d3 < 0), (d1 > 0 or d2 > 0 or d3 > 0)
        return not (has_neg and has_pos)

    remaining = list(idx)
    tris: list[tuple[int, int, int]] = []
    guard = 0
    while len(remaining) > 3 and guard < 10000:
        guard += 1
        m = len(remaining)
        ear_found = False
        for i in range(m):
            i_prev, i_cur, i_next = remaining[(i - 1) % m], remaining[i], remaining[(i + 1) % m]
            a, b, c = poly2d[i_prev], poly2d[i_cur], poly2d[i_next]
            if not is_convex(a, b, c):
                continue
            if any(j not in (i_prev, i_cur, i_next) and point_in_tri(poly2d[j], a, b, c) for j in remaining):
                continue
            tris.append((i_prev, i_cur, i_next))
            remaining.pop(i)
            ear_found = True
            break
        if not ear_found:
            break
    if len(remaining) == 3:
        tris.append((remaining[0], remaining[1], remaining[2]))
    return tris


def _building_geometry(fp2d, height: float):
    """footprint(동,북 로컬미터)+높이 → glTF Y-up POSITION 목록 + 삼각형 인덱스(로컬, 0-based).

    바닥면·지붕면(이어클리핑) + 벽면(모서리마다 쿼드 2장). 법선은 안 심는다 — 재질을
    doubleSided 로 둬 뒷면컬링 없이 어느 방향에서 봐도 보이게(권선방향 정합성 불필요, 단순화).
    """
    n = len(fp2d)
    tris2d = _ear_clip(fp2d)
    positions = [(e, 0.0, -nn) for (e, nn) in fp2d] + [(e, height, -nn) for (e, nn) in fp2d]
    indices: list[int] = []
    for (i, j, kk) in tris2d:
        indices += [i, j, kk]
        indices += [i + n, kk + n, j + n]
    for i in range(n):
        j = (i + 1) % n
        b0, b1, t0, t1 = i, j, i + n, j + n
        indices += [b0, b1, t1, b0, t1, t0]
    return positions, indices


def build_site_glb(address: str, model_radius_m: int = 350) -> bytes:
    """주소 → 반경 내 건물 매싱 GLB(box-extrude, 대지=원점, 미터 단위)."""
    from app.services.site_seed import build_site
    try:
        s = build_site(address)
        lat, lon = s.lat, s.lon
    except Exception:  # noqa: BLE001 — 주소 해석 실패는 하드블록
        raise ValueError("주소 해석 실패")
    if lat is None:
        raise ValueError("주소 해석 실패")

    model = clients.fetch_model(address, model_radius_m)
    if not model:
        raise ValueError("건물 모델 없음 — arch-site-model 응답 실패(env SITEMODEL_URL 확인)")

    model_ox, model_oy = (model.get("stats") or {})["origin_offset"]
    site_x, site_y = k.latlon_to_local(lat, lon, model_ox, model_oy)

    all_positions: list[tuple[float, float, float]] = []
    all_indices: list[int] = []
    ranges = []  # (byte_offset_in_index_buffer, count, height, index_in_buildings)
    vertex_offset = 0
    buildings = (model.get("geometry") or {}).get("buildings") or []
    for bi, b in enumerate(buildings):
        fp = b.get("footprint") or []
        h = float(b.get("height") or 0.0)
        if len(fp) < 3 or h <= 0:
            continue
        fp2d = [(px - site_x, py - site_y) for px, py in fp]
        positions, indices = _building_geometry(fp2d, h)
        start = len(all_indices)
        all_positions.extend(positions)
        all_indices.extend(idx + vertex_offset for idx in indices)
        ranges.append((start, len(indices), h, bi))
        vertex_offset += len(positions)

    if not all_positions:
        raise ValueError("추출 가능한 건물 매싱 없음(반경 내 건물 0 또는 높이 정보 없음)")

    pos_arr = np.asarray(all_positions, dtype=np.float32)
    idx_arr = np.asarray(all_indices, dtype=np.uint32)
    idx_bytes = idx_arr.tobytes()
    pad = (4 - len(idx_bytes) % 4) % 4
    pos_bytes = pos_arr.tobytes()
    buf_bytes = idx_bytes + b"\x00" * pad + pos_bytes

    gltf = g.GLTF2()
    gltf.asset = g.Asset(version="2.0", generator="teoilgi/arch-site-context map_svg-track (site_glb.py, §8.15)")
    gltf.buffers.append(g.Buffer(byteLength=len(buf_bytes)))
    gltf.bufferViews.append(g.BufferView(buffer=0, byteOffset=0, byteLength=len(idx_bytes),
                                         target=g.ELEMENT_ARRAY_BUFFER))
    gltf.bufferViews.append(g.BufferView(buffer=0, byteOffset=len(idx_bytes) + pad, byteLength=len(pos_bytes),
                                         target=g.ARRAY_BUFFER))
    gltf.accessors.append(g.Accessor(bufferView=1, componentType=g.FLOAT, count=len(all_positions), type=g.VEC3,
                                     max=pos_arr.max(axis=0).tolist(), min=pos_arr.min(axis=0).tolist()))
    pos_accessor = 0
    gltf.materials.append(g.Material(
        pbrMetallicRoughness=g.PbrMetallicRoughness(baseColorFactor=[0.55, 0.60, 0.68, 1.0],
                                                    metallicFactor=0.0, roughnessFactor=0.9),
        doubleSided=True,
    ))

    scene_nodes = []
    for (start, count, h, bi) in ranges:
        acc_idx = len(gltf.accessors)
        gltf.accessors.append(g.Accessor(bufferView=0, componentType=g.UNSIGNED_INT, count=count,
                                         type=g.SCALAR, byteOffset=start * 4))
        mesh_idx = len(gltf.meshes)
        gltf.meshes.append(g.Mesh(primitives=[g.Primitive(attributes={"POSITION": pos_accessor},
                                                          indices=acc_idx, material=0)]))
        node_idx = len(gltf.nodes)
        gltf.nodes.append(g.Node(
            mesh=mesh_idx, name=f"building-{bi}",
            extras={"height_m": round(h, 1), "source_ref": "arch-site-model:geometry.buildings"},
        ))
        scene_nodes.append(node_idx)

    gltf.scenes.append(g.Scene(nodes=scene_nodes))
    gltf.scene = 0
    gltf.set_binary_blob(buf_bytes)
    return b"".join(gltf.save_to_bytes())
