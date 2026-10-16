#!/usr/bin/env python3
"""Earth BPM 빌드 스크립트.

data/*.csv(USGS 실시간 피드·FDSN 카탈로그의 지진 기록, NOAA NCEI 세계 쓰나미 데이터베이스의 쓰나미 기록)와
data/land.json(world-atlas 110m 육지 윤곽)을 src/earth-bpm.template.html에 넣어
한 장짜리 HTML을 만든다.

    python3 build.py                     # index.html (완전한 HTML 문서, GitHub Pages용)
    python3 build.py --artifact PATH     # 같은 내용을 claude.ai 아티팩트용 조각 HTML로
    python3 build.py --local DIR         # three.js를 DIR(npm three@0.128.0 패키지)에서 읽는 테스트용
    python3 build.py --three URL         # three.js를 URL에서 읽는 테스트용 (로컬 웹 서버)

악기 소리는 voices/*.mp3를 페이지 옆에서 불러오므로, 웹 서버(GitHub Pages 등)로 열어야 들린다.
    python3 build.py --out PATH          # 출력 경로 바꾸기
"""
import csv, json, sys, os, re, math, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UTC = dt.timezone.utc
KST = dt.timezone(dt.timedelta(hours=9))
ERA_FILE = "hist_m7_1900_2026.csv"
TSUNAMI_FILE = "tsunami_noaa_1900_2026.csv"

# USGS CSV를 텍스트로 옮기며 깨진 지명 복원
FIX = {
    "?funato": "Ōfunato", "?arai": "Ōarai", "T?no": "Tōno", "?tsuchi": "Ōtsuchi",
    "Nurda??": "Nurdağı", "Kahramanmara?": "Kahramanmaraş", "Pazarc?k": "Pazarcık",
    "Ça?layancerit": "Çağlayancerit", "Do?an?ehir": "Doğanşehir", "Af?in": "Afşin",
    "G?ksun": "Göksun", "Ye?ilyurt": "Yeşilyurt", "K?r?khan": "Kırıkhan",
    "Yaylada??": "Yayladağı", "Uzunba?": "Uzunbağ", "Ak?ada?": "Akçadağ",
    "B?niy?s": "Bāniyās", "A?a?? Karafak?l?": "Aşağı Karafakılı", "Gölba??": "Gölbaşı",
    "Kod?ri??": "Kodāri", "Panauti??": "Panauti", "Saruhanl?": "Saruhanlı",
    "Salm?s": "Salmās", "Shing?": "Shingū", "Shizunai-furukawach?": "Shizunai-furukawachō", "?yama": "Ōyama",
    "Comand?u": "Comandău", "Ayvac?k": "Ayvacık", "Bhach?u": "Bhachāu", "Muzaffar?b?d": "Muzaffarābād",
    "P?deg?n-e Manj?l": "Pādegān-e Manjīl", "Tenn?": "Tennō", "?alabja": "Halabja", "B?my?n": "Bāmyān",
    "Do?ubayaz?t": "Doğubayazıt", "T?kest?n": "Tākestān", "?iso": "Ōiso", "Nistore?ti": "Nistorești",
    "Q?’en": "Qā’en", "Ca?oca": "Cașoca", "Kh?sh": "Khāsh",
}


def fix_place(p):
    for k, v in FIX.items():
        p = p.replace(k, v)
    return p.replace("?", "").replace("'", "’")


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
                    # 1900년대 초 기록 몇몇은 깊이가 비어 있다 (페이지에서 "깊이 미상"으로 보여준다)
                    depth=float(r["depth"]) if r["depth"] else None,
                    mag=float(r["mag"]), id=r["id"], place=fix_place(r["place"]),
                ))
    rows.sort(key=lambda r: r["t"])
    return rows


def pack(rows):
    t0 = rows[0]["t"]
    ev = [[round((r["t"] - t0).total_seconds(), 3), round(r["lat"], 4), round(r["lon"], 4),
           None if r["depth"] is None else round(r["depth"], 2), r["mag"], r["id"], r["place"]] for r in rows]
    return t0.timestamp(), ev


# ---------------- NOAA 쓰나미 기록 ----------------
COUNTRY_KO = {
    "ALBANIA": "알바니아", "ALGERIA": "알제리", "ANTARCTICA": "남극", "ARGENTINA": "아르헨티나", "AUSTRALIA": "오스트레일리아",
    "BRAZIL": "브라질", "BULGARIA": "불가리아", "CANADA": "캐나다", "CHILE": "칠레", "CHINA": "중국", "COLOMBIA": "콜롬비아",
    "COSTA RICA": "코스타리카", "CROATIA": "크로아티아", "CUBA": "쿠바", "DOMINICAN REPUBLIC": "도미니카공화국",
    "EAST CHINA SEA": "동중국해", "ECUADOR": "에콰도르", "EGYPT": "이집트", "EL SALVADOR": "엘살바도르", "FIJI": "피지",
    "FINLAND": "핀란드", "FRANCE": "프랑스", "FRENCH POLYNESIA": "프랑스령 폴리네시아", "GHANA": "가나", "GREECE": "그리스",
    "GREENLAND": "그린란드", "GUADELOUPE (FRENCH TERRITORY)": "과들루프", "GUATEMALA": "과테말라", "HAITI": "아이티",
    "HONDURAS": "온두라스", "ICELAND": "아이슬란드", "INDIA": "인도", "INDONESIA": "인도네시아", "IRAN": "이란",
    "ITALY": "이탈리아", "JAMAICA": "자메이카", "JAPAN": "일본", "JORDAN": "요르단", "KERMADEC ISLANDS": "케르마데크 제도",
    "MARTINIQUE (FRENCH TERRITORY)": "마르티니크", "MEXICO": "멕시코", "MONTSERRAT": "몬트세랫", "MOROCCO": "모로코",
    "NETHERLANDS": "네덜란드", "NEW CALEDONIA": "뉴칼레도니아", "NEW ZEALAND": "뉴질랜드", "NICARAGUA": "니카라과",
    "NORWAY": "노르웨이", "PAKISTAN": "파키스탄", "PANAMA": "파나마", "PAPUA NEW GUINEA": "파푸아뉴기니", "PERU": "페루",
    "PHILIPPINES": "필리핀", "RUSSIA": "러시아", "SAINT VINCENT AND THE GRENADINES": "세인트빈센트 그레나딘",
    "SAMOA": "사모아", "SCOTLAND": "영국 스코틀랜드", "SOLOMON ISLANDS": "솔로몬 제도", "SOUTH AFRICA": "남아프리카공화국",
    "SOUTH KOREA": "대한민국", "SPAIN": "스페인", "SWITZERLAND": "스위스", "TAIWAN": "대만", "TONGA": "통가",
    "TRINIDAD AND TOBAGO": "트리니다드 토바고", "TURKEY": "튀르키예", "UK": "영국", "UK TERRITORY": "영국령",
    "UKRAINE": "우크라이나", "USA": "미국", "USA TERRITORY": "미국령", "VANUATU": "바누아투", "VENEZUELA": "베네수엘라",
    "VIETNAM": "베트남", "WALLIS AND FUTUNA (FRENCH TERRITORY)": "왈리스 푸투나",
}
US_STATE = {"AK": "알래스카", "HI": "하와이", "CA": "캘리포니아", "WA": "워싱턴주", "OR": "오리건"}
# 지진과 짝이 없는 쓰나미 가운데 따로 들려줄 만큼 뚜렷한 곳 (나머지는 영어 지명을 그대로 보여준다)
LOC_KO = {
    "KRAKATAU": "크라카타우 화산", "TONGA ISLANDS": "통가 제도", "STROMBOLI ISLAND": "스트롬볼리섬",
    "TAAN FJORD, AK": "탄 피오르", "TRACY ARM, AK": "트레이시암 피오르", "KARRAT FJORD, GREENLAND": "카라트 피오르",
    "DICKSON FJORD, GREENLAND": "딕슨 피오르", "PAATUUT, GREENLAND": "파투트", "SOUFRIERE HILLS VOLCANO": "수프리에르힐스 화산",
    "PERSIAN GULF": "페르시아만", "SULAWESI": "술라웨시섬", "HAWAII": "하와이", "SKAGWAY, AK": "스캐그웨이",
    "PEDERSEN LAGOON, AK": "페데르센 석호", "BUREYA, FAR EASTERN RUSSIA": "부레야강", "ABUYOG, LEYTE": "레이테섬 아부요그",
    "SOUTH LHONAK LAK, SIKKIM": "시킴 남로낙 호수", "COLUMBIA RIVER VALLEY, WA": "컬럼비아강 계곡",
}
# NOAA 쓰나미 기록의 지명(영어 표기 그대로) → 한국어. "="로 시작하면 나라 이름까지 통째로 바꾸고, "+"로 시작하면 나라 이름 뒤에 바로 붙인다.
TS_PLACE = {
    "513 Lake, Hualcan Glacier": "우알칸 빙하 513 호수", "Acapulco": "아카풀코", "Aegean Sea": "에게해",
    "Aleutian Islands, AK": "알류샨 열도", "Algiers": "알제", "Alika, Hawaii": "알리카", "Altar Volcano": "알타르 화산",
    "Andaman Islands": "안다만 제도", "Andaman Islands, India": "안다만 제도", "Andreanof Islands, AK": "안드레아노프 제도",
    "Anegawa, Japan": "아네가와", "Aoshan": "아오산", "Aratozawa, Japan": "아라토자와", "Askja Lake": "아스캬 호수",
    "Atka, Aleutian Islands, AK": "알류샨 열도 애트카섬", "Auckland Islands": "오클랜드 제도", "Bali Sea": "발리해",
    "Balleny Islands": "발레니 제도", "Banda Sea": "반다해", "Basse-terre, Les Saintes": "레생트 제도", "Bering Island": "베링섬",
    "Bismarck Sea": "비스마르크해", "Black Sea": "흑해", "Bocas del Toro": "보카스델토로", "Bonin Islands": "오가사와라 제도",
    "Bougainville Island": "부건빌섬", "British Columbia": "브리티시컬럼비아", "Cape Mendocino, N. California": "=미국 캘리포니아 · 멘도시노곶",
    "Cariaco-cumana": "카리아코-쿠마나", "Caspian Sea": "카스피해", "Celebes Sea": "셀레베스해", "Central Adriatic": "아드리아해 중부",
    "Central Chile": "=칠레 중부", "Chehalis Lake, Chilliwack": "칠리왁 체헤일리스 호수", "Ciutadella, Menorca Island": "메노르카섬 시우타데야",
    "Corinthos-patras Gulf": "코린토스-파트라스만", "Crete": "크레타섬", "Crimea, Black Sea": "흑해 크림반도", "Cumana": "쿠마나",
    "Dalk Glacier": "달크 빙하", "Dayantang, Enshi": "언스 다옌탕", "Dead Sea": "사해", "Disenchantment Bay, AK": "디스인챈트먼트만",
    "Dodecanese Islands": "도데카니사 제도", "Drake Passage": "드레이크 해협", "E. Coast Honshu Island": "혼슈 동쪽 연안",
    "E. Honshu Island": "혼슈 동부", "E. Mindanao Island": "민다나오섬 동부", "E. Taiwan-ryukyu Islands": "대만 동쪽 류큐 열도",
    "Easter Island Region": "이스터섬 부근", "Eastern Sicily": "시칠리아섬 동부", "Ecstall River, BC": "엑스톨강",
    "El Salvador-guatemala": "=엘살바도르-과테말라", "El Salvador-nicaragua": "=엘살바도르-니카라과", "Fatu Hiva": "파투히바섬",
    "Fiji Islands": "=피지 제도", "Flores Sea": "플로레스해", "Fort-de-france": "포르드프랑스",
    "Fox Islands, Aleutian Islands, AK": "알류샨 열도 폭스 제도", "Futuna": "푸투나섬", "Gisborne": "기즈번",
    "Grand Banks, Newfoundland": "뉴펀들랜드 그랜드뱅크스", "Guam, Mariana Islands": "=미국령 괌", "Guangdong Province": "광둥성",
    "Gulf of Alaska, AK": "알래스카만", "Gulf of Corinth: Aiyion": "코린토스만 에이요", "Gulf of Elat-aqaba": "아카바만",
    "Gulf of Fonseca": "폰세카만", "Gulf of Gökova": "괴코바만", "Gulf of Iskenderun": "이스켄데룬만",
    "Haiti & Dominican Republic": "=아이티 · 도미니카공화국", "Halifax, Nova Scotia": "노바스코샤 핼리팩스", "Halmahera": "할마헤라섬",
    "Hokkaido Island": "홋카이도", "Honshu Island": "혼슈", "Honshu: S Coast": "혼슈 남쪽 연안", "Honshu: W Coast": "혼슈 서쪽 연안",
    "Hyuganada Sea": "휴가나다", "Ilulissat Icefjord, Greenland": "일룰리사트 빙하 피오르", "Ionian Calabria": "칼라브리아 이오니아해 연안",
    "Ionian Sea": "이오니아해", "Irian Jaya": "이리안자야", "Isla Cañas, Panama": "카냐스섬", "Iwate, Japan": "이와테현",
    "Izu Islands, Japan": "이즈 제도", "Japan:  Off Fukushima": "후쿠시마 앞바다", "Java Sea": "자와해", "Java": "자와섬",
    "Juan de Grijalva, Chiapas": "치아파스주 후안데그리할바", "Kadovar Island, Papua New Guinea": "카도바르섬",
    "Kamchatka Peninsula, Russia": "캄차카반도", "Kamchatka": "캄차카", "Kangra, India": "캉그라",
    "Karymskoye, Kamchatka, Russia": "캄차카 카림스코예 호수", "Kashima, Japan": "가시마", "Kasu Cone": "카수 화구",
    "Kepulauan Alor": "알로르 제도", "Kermadec Islands": "케르마데크 제도", "Kobe, Japan": "고베", "Kocaeli, Turkey": "코자엘리",
    "Kodiak Island, AK": "코디액섬", "Kozu-shima Island, Honshu": "고즈시마", "Lago Argentino": "아르헨티노 호수",
    "Lago de Atitlan": "아티틀란 호수", "Lake Taupo, North Island": "북섬 타우포 호수", "Lesbos": "레스보스섬", "Limon, Pandora": "리몬",
    "Little Nicobar Island": "리틀니코바르섬", "Lituya Bay, AK": "리투야만", "Loen": "로엔", "Loyalty Islands": "로열티 제도",
    "Luzon Island": "루손섬", "Lysefjoren, Western Norway": "뤼세피오르", "Macquarie Island": "매쿼리섬", "Maine": "=미국 메인주",
    "Mancuto": "만쿠토", "Mariana Trench, N. Mariana Islands": "=미국령 북마리아나 제도 · 마리아나 해구", "Marmara Sea": "마르마라해",
    "Matavanu Volcano": "마타바누 화산", "Messina Strait, Ionian Sea": "메시나 해협", "Mindanao Island, Philippines": "민다나오섬",
    "Molucca Sea": "몰루카해", "Mount Pelee": "펠레산", "N. Algeria": "=알제리 북부", "N. California": "=미국 캘리포니아 북부",
    "N. Kuril Islands": "쿠릴 열도 북부", "N. Luzon Island": "루손섬 북부", "N. Moluccas Islands": "말루쿠 제도 북부", "N. Peru": "=페루 북부",
    "NW. Irian Jaya": "이리안자야 북서부", "NW. Sumatra": "수마트라섬 북서부", "New Britain": "뉴브리튼섬", "North Aegean Sea": "에게해 북부",
    "North of Honduras": "=온두라스 북쪽 바다", "Northern Australia": "=오스트레일리아 북부", "Northern Chile": "=칠레 북부",
    "Northwest Venezuela": "=베네수엘라 북서부", "Noto Peninsula, Japan": "노토반도", "Notre Dame de la Salette": "노트르담드라살레트",
    "Odessa": "오데사", "Off Boso Peninsula": "보소반도 앞바다", "Off Coast Gwadar": "과다르 앞바다", "Off Coast of Honduras": "=온두라스 앞바다",
    "Off Coast of Oaxaca": "오악사카 앞바다", "Off Coast": "+앞바다", "Off East Coast of Honshu Island": "혼슈 동쪽 앞바다",
    "Off East Coast of South Island": "남섬 동쪽 앞바다", "Off Fukushima Prefecture": "후쿠시마현 앞바다",
    "Off Northeast Coast Honshu": "혼슈 북동쪽 앞바다", "Off SE Coast of Cuba": "=쿠바 남동쪽 앞바다", "Off Sanriku": "산리쿠 앞바다",
    "Off W. Coast of N Sumatra": "북수마트라 서쪽 앞바다", "Off W. Coast of Sumatra": "수마트라섬 서쪽 앞바다",
    "Off West Coast of South Island": "남섬 서쪽 앞바다", "Off the Coast near Santa Marta": "산타마르타 앞바다",
    "Philippine Sea": "필리핀해", "Philippine Trench": "필리핀 해구", "Port-au-prince": "포르토프랭스", "Puerto Rico": "=미국령 푸에르토리코",
    "Puerto Rico: Mona Passage": "=미국령 푸에르토리코 · 모나 해협", "Puysegur Trench": "퓌세귀르 해구",
    "Qinggan River, Hubei Province": "후베이성 칭간강", "Quang Nam": "꽝남성", "Rabaul Harbor": "라바울항",
    "Rat Islands, Aleutian Islands, AK": "알류샨 열도 랫 제도", "Ritter Island, Papua New Guinea": "리터섬", "Ryukyu Islands": "류큐 열도",
    "S of Raoul Island, Kermadec Islands": "케르마데크 제도 라울섬 남쪽", "S. California": "=미국 캘리포니아 남부",
    "S. Kuril Islands": "쿠릴 열도 남부", "S. Mexico": "=멕시코 남부", "S. Peru": "=페루 남부", "S. of Honshu Island": "혼슈 남쪽",
    "SE Raoul Island, Kermadec Islands": "라울섬 남동쪽", "SE. Alaska, AK": "=미국 알래스카 남동부", "SW. Corinth Gulf": "코린토스만 남서부",
    "SW. Honshu Island": "혼슈 남서부", "SW. Sumatra": "수마트라섬 남서부", "Sagami Bay": "사가미만", "Sakhalin Island": "사할린섬",
    "Samar Island": "사마르섬", "Samar Sea": "사마르해", "Samoa Islands": "=사모아 제도", "Sand Point, AK": "샌드포인트",
    "Sanriku": "산리쿠", "Santa Cruz Is. Vanuatu": "산타크루스 제도", "Santa Cruz Islands": "산타크루스 제도", "Scotia Sea": "스코샤해",
    "Sea of Japan": "동해", "Seram Island": "세람섬", "Shumagin Islands, AK": "슈마긴 제도", "Solomon Sea": "솔로몬해",
    "Soufriere Volcano": "수프리에르 화산", "South Coast Honshu Island": "혼슈 남쪽 연안", "South Indian Ocean": "남인도양",
    "South Island": "남섬", "South Maluku": "말루쿠 남부", "South of Java": "자와섬 남쪽", "Southern Atlantic Ocean": "남대서양",
    "Southern Chile": "=칠레 남부", "Statland": "스타틀란", "Sumatra": "수마트라섬", "Taal, Luzon Island": "루손섬 탈 화산",
    "Taiwan Strait": "대만 해협", "Taiwan:  Southeast of": "=대만 남동쪽 바다", "Taku Inlet, Juneau, AK": "주노 타쿠만",
    "Tanon Strait": "타뇬 해협", "Tasman Sea": "태즈먼해", "Tatar Strait": "타타르 해협", "Thompson River": "톰프슨강",
    "Timor Sea": "티모르해", "Tohuku, Japan": "도호쿠", "Tolaga Bay, North Island": "북섬 톨라가만",
    "Tyrrhenian Calabria": "칼라브리아 티레니아해 연안", "Tyrrhenian Sea": "티레니아해", "Utah": "=미국 유타주",
    "W. Corinth Gulf": "코린토스만 서부", "W. Luzon Island": "루손섬 서부", "West Coast, USA": "=미국 서부 해안",
    "Western Norway": "=노르웨이 서부", "White River Valley": "화이트강 계곡", "Whitehorse, Yukon": "유콘 화이트호스",
    "Wu Gorge, Wushan County": "우산현 우샤 협곡", "Wushan, Chongqing": "충칭 우산", "Xiaowan Reservoir, Yunnan Province": "윈난성 샤오완 저수지",
    "Zhaojun Bridge, Hubei Province": "후베이성 자오쥔교",
}
TS_LINK_CAUSES = {0, 1, 2, 3, 4, 5}         # 지진이 끼어 있거나 원인을 모르는 쓰나미만 지진과 짝짓는다
TS_LINK_WINDOW = {0: 180, 1: 5400, 2: 18 * 3600}  # 시각을 아는 정도(분·시·일)에 따라 허용하는 시각 차(초)
TS_LINK_KM = 600


def tsunami_time(r):
    """NOAA 기록의 발생 시각과 정확도(0 분까지 앎, 1 시까지, 2 날짜까지, 3 달까지, 4 해만)."""
    y, mo, d = int(r["year"]), int(r["month"] or 0), int(r["day"] or 0)
    if not mo:
        return dt.datetime(y, 7, 1, tzinfo=UTC), 4
    if not d:
        return dt.datetime(y, mo, 15, tzinfo=UTC), 3
    if r["hour"] == "":
        return dt.datetime(y, mo, d, 12, tzinfo=UTC), 2
    t = dt.datetime(y, mo, d, int(r["hour"]), int(r["minute"] or 0), tzinfo=UTC) + dt.timedelta(seconds=float(r["second"] or 0))
    return t, (0 if r["minute"] != "" else 1)


def title_en(s):
    small = {"of", "the", "and", "de", "del", "la", "los", "las", "near"}
    out = [w.capitalize() if i == 0 or w.lower() not in small else w.lower() for i, w in enumerate(s.lower().split(" "))]
    return re.sub(r"\b(Ak|Bc|Wa|Usa|Uk|Se|Sw|Ne|Nw)\b", lambda m: m.group(0).upper(), " ".join(out))


def tsunami_names(country, loc):
    """(한국어 이름, 영어 원문) — 나라는 한국어로, 지명은 아는 곳만 한국어로."""
    ko = COUNTRY_KO.get(country, title_en(country))
    m = re.search(r", (AK|HI|CA|WA|OR)$", loc)
    if country == "USA" and (m or "HAWAII" in loc):
        ko = "미국 " + US_STATE[m.group(1) if m else "HI"]
    place = TS_PLACE.get(title_en(loc)) or LOC_KO.get(loc)
    if place and place.startswith("="):
        ko = place[1:]
    elif place and place.startswith("+"):
        ko += " " + place[1:]
    elif place and not ko.endswith(place):
        ko += " · " + place
    same = loc.upper() == country.upper() or loc.upper().endswith(", " + country.upper())
    en = title_en(loc) if same else f"{title_en(loc)}, {title_en(country)}"
    return ko, en


def load_tsunamis():
    out = []
    with open(os.path.join(DATA, TSUNAMI_FILE), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["latitude"] or not r["longitude"]:
                continue  # 위치가 없는 기록(대부분 기상 쓰나미)은 지구 위에 놓을 수 없어 뺀다
            t, approx = tsunami_time(r)
            num = lambda k, cast=float: cast(r[k]) if r[k] != "" else None
            ko, en = tsunami_names(r["country"], r["locationName"])
            out.append(dict(t=t, approx=approx, lat=float(r["latitude"]), lon=float(r["longitude"]),
                            h=num("maxWaterHeight"), runups=num("numRunups", int) or 0, deaths=num("deathsTotal", int) or 0,
                            id=int(r["id"]), cause=int(r["causeCode"] or 0), eqmag=num("eqMagnitude"), ko=ko, en=en))
    out.sort(key=lambda w: w["t"])
    return out


def haversine(a, b, c, d):
    x, y = math.radians(c - a), math.radians(d - b)
    h = math.sin(x / 2) ** 2 + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(y / 2) ** 2
    return 2 * 6371 * math.asin(min(1, math.sqrt(h)))


def scene_tsunamis(rows, tsunamis, t_lo, t_hi):
    """장면 시간 안의 쓰나미를 지진과 짝짓는다.

    시각 차(시각을 아는 정도에 따라 3분 · 1시간 반 · 18시간)와 진앙 거리(600 km 안)로 가장 가까운 지진 하나를 고른다.
    짝이 없는 쓰나미는 최대 높이 1 m 이상, 사망자 1명 이상, 관측 지점 10곳 이상 중 하나라도 맞을 때만 따로 넣는다.
    """
    out, used = [], set()
    for w in tsunamis:
        if not (t_lo <= w["t"] < t_hi):
            continue
        best = None
        win = TS_LINK_WINDOW.get(w["approx"])
        if win and w["cause"] in TS_LINK_CAUSES:
            for q in rows:
                gap = abs((q["t"] - w["t"]).total_seconds())
                if gap > win or q["id"] in used:
                    continue
                d = haversine(w["lat"], w["lon"], q["lat"], q["lon"])
                if d > TS_LINK_KM:
                    continue
                score = gap / 60 + d / 100 + (abs(w["eqmag"] - q["mag"]) * 2 if w["eqmag"] else 0)
                if best is None or score < best[0]:
                    best = (score, q["id"])
        if best:
            used.add(best[1])
        elif not ((w["h"] or 0) >= 1 or w["deaths"] >= 1 or w["runups"] >= 10):
            continue
        out.append([round(w["t"].timestamp(), 1), round(w["lat"], 3), round(w["lon"], 3), w["h"], w["runups"], w["id"],
                    w["cause"], w["ko"], w["en"], w["eqmag"], w["approx"], best[1] if best else ""])
    return out


SCENES = [
    dict(key="now", kind="now", files=["all_day.csv"],
         title="최근 24시간", year="NOW",
         filter="전 세계 · 모든 규모",
         blurb="USGS 실시간 피드에 올라온 최근 하루치 지진입니다. 아주 작은 지진까지 모두 들어 있습니다.",
         highlights={"aka2026ukynnb": "오늘 가장 큰 지진 · 알래스카 M5.6"}),
    dict(key="week", kind="week", files=["4.5_week.csv", "4.5_week_gapfill.csv"], days=7,
         title="최근 7일", year="WEEK",
         filter="전 세계 · 규모 4.5 이상",
         blurb="10월 10일 새벽(한국 시각) 파나마에서 M7.7이 일어났고, 여진이 며칠째 이어지고 있습니다.",
         highlights={"us6000u18k": "파나마 M7.7",
                     "us6000u1z5": "대서양 중앙 해령 M6.7",
                     "us6000u214": "6시간 38분 뒤 · 바로 옆에서 M6.8"}),
    dict(key="kamchatka", kind="past", files=["hist_2025_kamchatka.csv"],
         title="캄차카 대지진", year="2025", date="2025년 7월 30일", mainId="us6000qw60",
         filter="7월 29일 ~ 31일 · 규모 5 이상",
         blurb="태평양 전역에 쓰나미 경보가 울렸던 지진입니다. 45분 뒤 M6.9 여진이 이어졌습니다.",
         highlights={"us6000qw1a": "5시간 반 전 · 피지 남쪽 553km 깊이 M6.6",
                     "us6000qw60": "캄차카 대지진 · M8.8",
                     "us6000qw6q": "45분 뒤 · M6.9 여진"}),
    dict(key="turkey", kind="past", files=["hist_2023_turkey.csv"],
         title="튀르키예·시리아 대지진", year="2023", date="2023년 2월 6일", mainId="us6000jllz",
         filter="2월 5일 ~ 7일 · 규모 4.5 이상",
         blurb="현지 새벽 4시에 M7.8이 일어났고, 9시간 뒤 북쪽에서 M7.5가 한 번 더 일어났습니다.",
         highlights={"us6000jllz": "파자르즉 지진 · M7.8",
                     "us6000jlm1": "11분 뒤 · M6.7",
                     "us6000jlqa": "9시간 뒤 · 엘비스탄 지진 M7.5"}),
    dict(key="gyeongju", kind="past", files=["hist_2016_gyeongju.csv"],
         title="9·12 경주 지진", year="2016", date="2016년 9월 12일", mainId="us10006p1f",
         filter="9월 12일 ~ 13일 · 전 세계 규모 4 이상",
         blurb="한반도 계기 관측 이래 가장 강했던 지진입니다. 저녁 7시 44분 전진, 8시 32분 본진이 왔습니다. (기상청 규모 5.1·5.8, USGS 4.9·5.4)",
         highlights={"us10006p12": "경주 전진 · 저녁 7시 44분",
                     "us10006p1f": "경주 본진 · 저녁 8시 32분"}),
    dict(key="nepal", kind="past", files=["hist_2015_nepal.csv"],
         title="네팔 고르카 지진", year="2015", date="2015년 4월 25일", mainId="us20002926",
         filter="4월 25일 ~ 26일 · 규모 4.5 이상",
         blurb="히말라야 아래에서 일어나 카트만두 일대에 큰 피해를 남긴 지진입니다. 34분 뒤 M6.6 여진이 이어졌습니다.",
         highlights={"us20002926": "고르카 지진 · M7.8",
                     "us2000292y": "34분 뒤 · M6.6 여진"}),
    dict(key="tohoku", kind="past", files=["hist_2011_tohoku.csv"],
         title="동일본 대지진", year="2011", date="2011년 3월 11일", mainId="official20110311054624120_30",
         filter="3월 9일 ~ 12일 · 규모 5.5 이상",
         blurb="일본 관측 사상 가장 큰 지진입니다. 이틀 전 M7.3 전진이 먼저 울렸고, 본진 뒤 40분 사이 M7.9와 M7.7이 이어졌습니다.",
         highlights={"usp000hvhj": "이틀 전의 전진 · M7.3",
                     "official20110311054624120_30": "동일본 대지진 · M9.1",
                     "usp000hvpa": "29분 뒤 · 이바라키 앞바다 M7.9",
                     "usp000hvpg": "39분 뒤 · 먼바다 M7.7"}),
    dict(key="sumatra", kind="past", files=["hist_2004_sumatra.csv"],
         title="수마트라-안다만 대지진", year="2004", date="2004년 12월 26일", mainId="official20041226005853450_30",
         filter="12월 25일 ~ 27일 · 규모 5 이상",
         blurb="인도양 전체에 쓰나미를 일으킨 지진입니다. 본진 뒤 3시간 22분 만에 M7.2 여진이 이어졌습니다.",
         highlights={"official20041226005853450_30": "수마트라-안다만 대지진 · M9.1",
                     "usp000dbg6": "3시간 22분 뒤 · M7.2 여진"}),
]

# 1900년부터 10년씩 끊은 기록 장면 (USGS 카탈로그의 규모 7 이상 전부, 한국 시각 1월 1일 기준)
for _y in range(1900, 2030, 10):
    SCENES.append(dict(key=f"y{_y}", kind="era", files=[ERA_FILE], year=f"{_y}s", title=f"{_y}년대",
                       date=f"{_y}–{min(_y + 9, 2026)}년", filter="전 세계 · 규모 7 이상",
                       lo=dt.datetime(_y, 1, 1, tzinfo=KST), hi=dt.datetime(_y + 10, 1, 1, tzinfo=KST)))


def build_data():
    out = []
    tsunamis = load_tsunamis()
    with open(os.path.join(DATA, TSUNAMI_FILE), encoding="utf-8") as f:
        ts_years = {int(r["year"]) for r in csv.DictReader(f)}
    cache = {}
    for s in SCENES:
        key = tuple(s["files"])
        if key not in cache:
            cache[key] = load(*s["files"])
        rows = cache[key]
        if s.get("days"):
            end = rows[-1]["t"]
            rows = [r for r in rows if r["t"] >= end - dt.timedelta(days=s["days"])]
        if s.get("lo"):
            rows = [r for r in rows if s["lo"] <= r["t"] < s["hi"]]
            t_lo, t_hi = s["lo"], s["hi"]
        else:
            t_lo, t_hi = rows[0]["t"] - dt.timedelta(hours=1), rows[-1]["t"] + dt.timedelta(hours=1)
        t0, ev = pack(rows)
        ts = scene_tsunamis(rows, tsunamis, t_lo, t_hi)
        item = {k: v for k, v in s.items() if k not in ("files", "days", "lo", "hi")}
        item.update(t0=t0, ev=ev, ts=ts)
        if s["kind"] == "era" and not any(s["lo"].year <= y < s["hi"].year for y in ts_years):
            item["tsMissing"] = True  # NOAA에서 이 연대의 쓰나미 기록을 받지 못했다
        out.append(item)
        linked = sum(1 for w in ts if w[-1] != "")
        print(f"  {s['key']:10s} {len(ev):4d}건  M{min(r['mag'] for r in rows):.1f}~{max(r['mag'] for r in rows):.1f}"
              f"  쓰나미 {len(ts):3d}건 (지진과 짝 {linked})" + ("  쓰나미 기록 없음" if item.get("tsMissing") else ""),
              file=sys.stderr)
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
            '<meta name="description" content="1900년 이후 USGS 지진 기록과 NOAA 쓰나미 기록을 3D 지구와 소리로 듣는 Earth BPM">\n'
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
