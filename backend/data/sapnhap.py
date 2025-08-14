"""Convert raw sapnhap.json to a more manageable format from https://sapnhap.bando.com.vn/"""

import json
import pathlib

p = pathlib.Path("backend/data/sapnhap.json")
data = json.loads(p.read_text(encoding="utf-8"))

map_keys = {
    "0": "stt",
    "1": "matinh",
    "2": "ma",
    "3": "tentinh",
    "4": "loai",
    "5": "ten_px_moi",
    "6": "ma_cay",
    "7": "dientich_km2",
    "8": "dan_so",
    "9": "truso_hanhchinh_moi",
    "10": "kinh_do",
    "11": "vi_do",
    "12": "sap_nhap_tu",
    "13": "ma_xa_truoc",
    "14": "khoa_tim_kiem",
}

out = []
for item in data:
    new = {(map_keys.get(k, k)): v for k, v in item.items() if k not in map_keys or k in map_keys}
    # optionally drop the old duplicates:
    for k in [
        "id",
        "tenhc",
        "dientichkm2",
        "dansonguoi",
        "trungtamhc",
        "kinhdo",
        "vido",
        "truocsapnhap",
        "maxa",
        "khoa",
        "cay",
    ]:
        new.pop(k, None)
    out.append(new)

p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
