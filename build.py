#!/usr/bin/env python3
"""Earth BPM 빌드 스크립트.

data/*.csv(USGS 실시간 피드·FDSN 카탈로그에서 받은 실제 지진 기록)와
data/land.json(world-atlas 110m 육지 윤곽)을 src/earth-bpm.template.html에 넣어
한 장짜리 HTML을 만든다.

    python3 build.py                     # index.html (완전한 HTML 문서, GitHub Pages용)
    python3 build.py --artifact PATH     # 같은 내용을 claude.ai 아티팩트용 조각 HTML로
    python3 build.py --local DIR         # three.js를 DIR(npm three@0.128.0 패키지)에서 읽는 테스트용
    python3 build.py --three URL         # three.js를 URL에서 읽는 테스트용 (로컬 웹 서버)

악기 소리는 voices/*.mp3를 페이지 옆에서 불러오므로, 웹 서버(GitHub Pages 등)로 열어야 들린다.
    python3 build.py --out PATH          # 출력 경로 바꾸기
"""
import csv, json, sys, os, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# USGS CSV를 텍스트로 옮기며 깨진 지명 복원
FIX = {
    "?funato": "Ōfunato", "?arai": "Ōarai", "T?no": "Tōno", "?tsuchi": "Ōtsuchi",
    "Nurda??": "Nurdağı", "Kahramanmara?": "Kahramanmaraş", "Pazarc?k": "Pazarcık",
    "Ça?layancerit": "Çağlayancerit", "Do?an?ehir": "Doğanşehir", "Af?in": "Afşin",
    "G?ksun": "Göksun", "Ye?ilyurt": "Yeşilyurt", "K?r?khan": "Kırıkhan",
    "Yaylada??": "Yayladağı", "Uzunba?": "Uzunbağ", "Ak?ada?": "Akçadağ",
    "B?niy?s": "Bāniyās", "A?a?? Karafak?l?": "Aşağı Karafakılı", "Gölba??": "Gölbaşı",
    "Kod?ri??": "Kodāri", "Panauti??": "Panauti", "Saruhanl?": "Saruhanlı",
}


def fix_place(p):
    for k, v in FIX.items():
        p = p.replace(k, v)
    return p.replace("?", "")


def parse_time(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=dt.timezone.utc)


def load(*names):
    seen, rows = set(), []
    for n in names:
        with open(os.path.join(DATA, n), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                rows.append(dict(
                    t=parse_time(r["time"]), lat=float(r["latitude"]), lon=float(r["longitude"]),
                    depth=float(r["depth"]), mag=float(r["mag"]), id=r["id"], place=fix_place(r["place"]),
                ))
    rows.sort(key=lambda r: r["t"])
    return rows


def pack(rows):
    t0 = rows[0]["t"]
    ev = [[round((r["t"] - t0).total_seconds(), 3), round(r["lat"], 4), round(r["lon"], 4),
           round(r["depth"], 2), r["mag"], r["id"], r["place"]] for r in rows]
    return t0.timestamp(), ev


SCENES = [
    dict(key="now", kind="now", files=["all_day.csv"],
         title="지금 이 순간", year="NOW",
         filter="최근 24시간 · 모든 규모",
         blurb="USGS 실시간 피드에 올라온 최근 하루치 지진이에요. 아주 작은 떨림까지 모두 들어 있어요.",
         highlights={"aka2026ukynnb": "오늘 가장 큰 박동 · 알래스카 M5.6"}),
    dict(key="week", kind="week", files=["4.5_week.csv", "4.5_week_gapfill.csv"], days=7,
         title="이번 주의 큰 박동", year="7일",
         filter="최근 7일 · 규모 4.5 이상",
         blurb="10월 10일 새벽(한국 시각) 파나마에서 M7.7이 일어났고, 여진이 며칠째 이어지고 있어요.",
         highlights={"us6000u18k": "파나마 M7.7",
                     "us6000u1z5": "대서양 중앙 해령 M6.7",
                     "us6000u214": "6시간 38분 뒤 · 바로 옆에서 M6.8"}),
    dict(key="kamchatka", kind="past", files=["hist_2025_kamchatka.csv"],
         title="캄차카 대지진", year="2025", date="2025년 7월 30일", mainId="us6000qw60",
         filter="7월 29일 ~ 31일 · 규모 5 이상",
         blurb="태평양 전역에 쓰나미 경보가 울렸던 지진이에요. 45분 뒤 M6.9 여진이 이어졌어요.",
         highlights={"us6000qw1a": "5시간 반 전 · 피지 남쪽 553km 깊이 M6.6",
                     "us6000qw60": "캄차카 대지진 · M8.8",
                     "us6000qw6q": "45분 뒤 · M6.9 여진"}),
    dict(key="turkey", kind="past", files=["hist_2023_turkey.csv"],
         title="튀르키예·시리아 대지진", year="2023", date="2023년 2월 6일", mainId="us6000jllz",
         filter="2월 5일 ~ 7일 · 규모 4.5 이상",
         blurb="현지 새벽 4시에 M7.8이 일어났고, 9시간 뒤 북쪽에서 M7.5가 한 번 더 일어났어요.",
         highlights={"us6000jllz": "파자르즉 지진 · M7.8",
                     "us6000jlm1": "11분 뒤 · M6.7",
                     "us6000jlqa": "9시간 뒤 · 엘비스탄 지진 M7.5"}),
    dict(key="gyeongju", kind="past", files=["hist_2016_gyeongju.csv"],
         title="9·12 경주 지진", year="2016", date="2016년 9월 12일", mainId="us10006p1f",
         filter="9월 12일 ~ 13일 · 전 세계 규모 4 이상",
         blurb="한반도 계기 관측 이래 가장 강했던 지진이에요. 저녁 7시 44분 전진, 8시 32분 본진이 왔어요. (기상청 규모 5.1·5.8, USGS 4.9·5.4)",
         highlights={"us10006p12": "경주 전진 · 저녁 7시 44분",
                     "us10006p1f": "경주 본진 · 저녁 8시 32분"}),
    dict(key="nepal", kind="past", files=["hist_2015_nepal.csv"],
         title="네팔 고르카 지진", year="2015", date="2015년 4월 25일", mainId="us20002926",
         filter="4월 25일 ~ 26일 · 규모 4.5 이상",
         blurb="히말라야 아래에서 일어나 카트만두 일대에 큰 피해를 남긴 지진이에요. 34분 뒤 M6.6 여진이 이어졌어요.",
         highlights={"us20002926": "고르카 지진 · M7.8",
                     "us2000292y": "34분 뒤 · M6.6 여진"}),
    dict(key="tohoku", kind="past", files=["hist_2011_tohoku.csv"],
         title="동일본 대지진", year="2011", date="2011년 3월 11일", mainId="official20110311054624120_30",
         filter="3월 9일 ~ 12일 · 규모 5.5 이상",
         blurb="일본 관측 사상 가장 큰 지진이에요. 이틀 전 M7.3 전진이 먼저 울렸고, 본진 뒤 40분 사이 M7.9와 M7.7이 이어졌어요.",
         highlights={"usp000hvhj": "이틀 전의 전진 · M7.3",
                     "official20110311054624120_30": "동일본 대지진 · M9.1",
                     "usp000hvpa": "29분 뒤 · 이바라키 앞바다 M7.9",
                     "usp000hvpg": "39분 뒤 · 먼바다 M7.7"}),
    dict(key="sumatra", kind="past", files=["hist_2004_sumatra.csv"],
         title="수마트라-안다만 대지진", year="2004", date="2004년 12월 26일", mainId="official20041226005853450_30",
         filter="12월 25일 ~ 27일 · 규모 5 이상",
         blurb="인도양 전체에 쓰나미를 일으킨 지진이에요. 본진 뒤 3시간 22분 만에 M7.2 여진이 이어졌어요.",
         highlights={"official20041226005853450_30": "수마트라-안다만 대지진 · M9.1",
                     "usp000dbg6": "3시간 22분 뒤 · M7.2 여진"}),
]


def build_data():
    out = []
    for s in SCENES:
        rows = load(*s["files"])
        if s.get("days"):
            end = rows[-1]["t"]
            rows = [r for r in rows if r["t"] >= end - dt.timedelta(days=s["days"])]
        t0, ev = pack(rows)
        item = {k: v for k, v in s.items() if k not in ("files", "days")}
        item.update(t0=t0, ev=ev)
        out.append(item)
        print(f"  {s['key']:10s} {len(ev):4d}건  M{min(r['mag'] for r in rows):.1f}~{max(r['mag'] for r in rows):.1f}", file=sys.stderr)
    with open(os.path.join(DATA, "land.json")) as f:
        land = json.load(f)
    # 악기 소리(voices/*.mp3)의 칸 길이와 음 목록. 소리 파일은 페이지가 필요할 때 따로 불러온다.
    with open(os.path.join(HERE, "voices", "voices.json")) as f:
        vm = json.load(f)
    voices = {"notes": vm["notes"], "lead": vm["lead"],
              "voices": {k: {kk: vv for kk, vv in v.items() if kk != "program"} for k, v in vm["voices"].items()}}
    return {"scenes": out, "land": land, "voices": voices, "fetchedAt": "2026-10-15T23:58:00Z"}


def standalone(html):
    """아티팩트용 조각(<title>…<style>…<div id="app">…<script>)을 완전한 문서로 감싼다."""
    i = html.index('<div id="app">')
    head, body = html[:i].strip(), html[i:].strip()
    return ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<meta name="theme-color" content="#03040a">\n'
            '<meta name="description" content="USGS 실제 지진 기록을 3D 지구와 지구의 심장 소리로 듣는 Earth BPM">\n'
            f'{head}\n</head>\n<body>\n{body}\n</body>\n</html>\n')


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


def main():
    local, artifact, three = arg("--local"), arg("--artifact"), arg("--three")
    out_path = arg("--out") or artifact or os.path.join(HERE, "index.html")
    with open(os.path.join(HERE, "src", "earth-bpm.template.html"), encoding="utf-8") as f:
        html = f.read()
    data = json.dumps(build_data(), ensure_ascii=False, separators=(",", ":"))
    html = html.replace("/*__DATA__*/null", data)
    if local:
        html = html.replace("https://cdn.jsdelivr.net/npm/three@0.128.0", "file://" + os.path.abspath(local))
    if three:
        html = html.replace("https://cdn.jsdelivr.net/npm/three@0.128.0", three.rstrip("/"))
    if not artifact:
        html = standalone(html)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out_path} ({len(html)/1024:.0f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
