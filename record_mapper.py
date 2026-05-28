"""kintone レコード(JSON) → main.py の customer dict 形式へ変換"""

import re
from datetime import date

SHINSETSU_ALIASES = {"新規入会", "新設", "新規開設"}

# 現状回線: ホワイトリスト方式（記載以外はすべて「その他」）
LINE_TYPE_COLLAB = {
    "フレッツ", "ピカラ光", "SONET光", "softbank光", "docomo光",
    "OCN光", "nifty光", "BIGLOBE光", "コミュファ光", "その他コラボ",
}
LINE_TYPE_NONE = {"未契約"}

# 住居形態 × 所有形態 → So-net 側 building_type
# 「分譲」は「持家」に正規化してから引く
BUILDING_MAP = {
    ("一戸建て", "持家"): "戸建(持家)",
    ("一戸建て", "賃貸"): "戸建(賃貸)",
    ("集合住宅", "持家"): "集合住宅(分譲)",
    ("集合住宅", "賃貸"): "集合住宅(賃貸)",
}

# 申込プラン → So-net フォームの course
COURSE_MAP = {
    "so-net光Mプラン（新規開設・戸建て）": "So-net光M_戸建_西日本",
    "so-net光Mプラン（新規開設・MS）": "So-net光M_マンション_西日本",
    "so-net光10ギガプラン（新規開設・戸建て）": "So-net光10G_戸建_西日本",
    "so-net光10ギガプラン（新規開設・MS）": "So-net光10G_マンション_西日本",
}

# 設定不要オプション: So-netコード → kintone fieldCode
# 値が「〇」なら申込、それ以外は未申込
SIMPLE_OPTIONS = [
    ("ASPP", "ドロップダウン_26"),  # 安心サポートプラス
    ("AVVA", "ドロップダウン_30"),  # バレッドライフ
    ("DTRC", "ドロップダウン_29"),  # 備えて安心 データ復旧
    ("ISWL", "ドロップダウン_25"),  # みやブル+弁護士費用保証
    ("JTBB", "ドロップダウン_27"),  # Benefit Station
    ("KOMW", "ドロップダウン_28"),  # くらしのお守りワイド
    ("SAFE", "ドロップダウン_45"),  # S-SAFE
    ("SIDK", "ドロップダウン_45"),  # S-SAFE ID Keeper (SAFEと同フィールド)
    ("UNXT", "ドロップダウン_68"),  # U-NEXT for So-net
]

# So-net option_detail 画面のチェックボックスインデックス
SO_NET_CHECKBOX_INDEX = {
    "ASPP": 0, "AVVA": 1, "DTRC": 2, "ISWL": 3, "JTBB": 4,
    "KOMW": 5, "SAFE": 6, "SIDK": 7, "UNXT": 8,
}

# 現在の電話サービス: kintone値 → So-net UP4315_telSrvcCd 値
PHONE_SERVICE_MAP = {
    "NTT加入電話": "W001",
    "NTT加入電話ライトプラン": "W002",
    "auひかり電話": "W111",
    "auひかりちゅら": "W112",
    "ケーブルプラス電話": "W113",
    "J:COM PHONE": "W115",
    "ケーブルライン": "W131",
    "おとくライン": "W132",
    "ホワイト光電話": "W134",
    "その他(NURO光電話)": "W135",  # 念のため半角括弧も対応
    "その他（NURO光電話）": "W135",
    "コミュファ光電話": "W141",
    "eo光電話": "W151",
    "メガエッグ光電話": "W161",
    "BBIQ光電話": "W171",
    # docomo光電話, OCN光, BBフォン光, メタルプラス電話, ピカラ光でんわ → W999
}


def map_phone_service(value: str) -> str:
    """現在の電話サービス kintone値 → So-netコード(未マッチはW999)"""
    return PHONE_SERVICE_MAP.get((value or "").strip(), "W999")

PREFS = (
    "北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|"
    "茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|"
    "新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|"
    "滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|"
    "鳥取県|島根県|岡山県|広島県|山口県|"
    "徳島県|香川県|愛媛県|高知県|"
    "福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県"
)


class MapError(Exception):
    pass


def _v(field: dict) -> str:
    if not field:
        return ""
    return field.get("value") or ""


def map_line_type(value: str) -> str:
    if value in LINE_TYPE_NONE:
        return "利用していない"
    if value in LINE_TYPE_COLLAB:
        return "フレッツ・他社コラボ"
    return "その他"


def split_birth(birth8: str) -> tuple[str, str, str]:
    s = (birth8 or "").strip()
    if not re.fullmatch(r"\d{8}", s):
        raise MapError(f"生年月日は8桁数字で指定してください: {s!r}")
    return s[0:4], s[4:6], s[6:8]


def split_phone(phone: str) -> tuple[str, str, str]:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) not in (10, 11):
        raise MapError(f"電話番号の桁数が想定外: {phone!r} ({len(digits)}桁)")
    head = digits[:3]
    if head in ("070", "080", "090"):
        return digits[:3], digits[3:7], digits[7:11]  # 携帯 3-4-4
    return digits[:3], digits[3:6], digits[6:10]  # 固定 3-3-4


def map_building_type(dwelling: str, ownership: str) -> str:
    ownership_norm = "持家" if ownership == "分譲" else ownership
    key = (dwelling, ownership_norm)
    if key not in BUILDING_MAP:
        raise MapError(f"住居形態の組み合わせ未対応: {dwelling!r} × {ownership!r}")
    return BUILDING_MAP[key]


def map_course(plan: str) -> str:
    if plan not in COURSE_MAP:
        raise MapError(f"未対応の申込プラン: {plan!r}")
    return COURSE_MAP[plan]


def split_address(addr: str) -> dict:
    """住所を pref/city/town/banchi/go に分割（best-effort）"""
    s = (addr or "").strip()
    out = {"pref": "", "city": "", "town": "", "banchi": "", "go": ""}
    if not s:
        return out

    m = re.match(rf"({PREFS})(.+)", s)
    if m:
        out["pref"] = m.group(1)
        s = m.group(2)

    m = re.match(r"(.+?[市区町村郡])(.+?[区]|)(.*)", s)
    if m:
        out["city"] = m.group(1) + m.group(2)
        s = m.group(3)

    # 末尾の番地・号
    hyphen = r"[-‐ー－]"
    # Pattern 1: N-M-K（丁目省略、ハイフン区切り3要素）→ N丁目を町名に追加、番地=M、号=K
    m = re.search(rf"(\d+)\s*{hyphen}\s*(\d+)\s*{hyphen}\s*(\d+)\s*号?$", s)
    if m:
        chome = m.group(1)
        out["banchi"] = m.group(2)
        out["go"] = m.group(3)
        s = s[: m.start()].rstrip("、 ") + chome + "丁目"
    else:
        # Pattern 2: N-M / N番地M号 / N番M号
        m = re.search(rf"(\d+)\s*(?:{hyphen}|番地?の?)\s*(\d+)\s*号?$", s)
        if m:
            out["banchi"] = m.group(1)
            out["go"] = m.group(2)
            s = s[: m.start()].rstrip("、 ")
        else:
            # Pattern 3: N番地 / N番（号なし）
            m = re.search(r"(\d+)\s*番地?$", s)
            if m:
                out["banchi"] = m.group(1)
                s = s[: m.start()].rstrip("、 ")
            else:
                # Pattern 4: 末尾の数字のみ
                m = re.search(r"(\d+)$", s)
                if m:
                    out["banchi"] = m.group(1)
                    s = s[: m.start()].rstrip("、 ")

    out["town"] = s.strip()
    return out


def collect_simple_options(record: dict) -> list[str]:
    """設定不要オプションのうち申込(〇)のSo-netコードを返す"""
    selected = []
    for code, field in SIMPLE_OPTIONS:
        if _v(record.get(field)).strip() == "〇":
            selected.append(code)
    return selected


def build_customer(record: dict) -> dict:
    """kintone レコード(JSON) → customer dict 変換"""
    apply_type_raw = _v(record.get("文字列__1行__32"))
    if apply_type_raw not in SHINSETSU_ALIASES:
        raise MapError(f"未対応の申込区分: {apply_type_raw!r}（新設のみ対応）")

    by, bm, bd = split_birth(_v(record.get("文字列__1行__19")))
    p1, p2, p3 = split_phone(_v(record.get("文字列__1行__6")))
    building_type = map_building_type(
        _v(record.get("ドロップダウン_2")),
        _v(record.get("ドロップダウン_3")),
    )
    addr_raw = _v(record.get("文字列__1行__11"))
    addr = split_address(addr_raw)
    course = map_course(_v(record.get("申込みプラン")))
    line_type = map_line_type(_v(record.get("ドロップダウン_4")))

    today = date.today()

    return {
        "agency_code": _v(record.get("文字列__1行__36")),
        "sei": _v(record.get("旧契約者姓_漢字")),
        "mei": _v(record.get("旧契約者名_漢字")),
        "sei_kana": _v(record.get("旧契約者姓_カナ")),
        "mei_kana": _v(record.get("旧契約者名_カナ")),
        "gender": _v(record.get("ドロップダウン")),
        "birth_year": by, "birth_month": bm, "birth_day": bd,
        "postal_code1": _v(record.get("郵便番号前半")),
        "postal_code2": _v(record.get("郵便番号後半")),
        "town": addr["town"] or addr_raw,
        "banchi": addr["banchi"],
        "go": addr["go"],
        "building": _v(record.get("文字列__1行__12")),
        "room": _v(record.get("文字列__1行__13")),
        "phone1": p1, "phone2": p2, "phone3": p3,
        "building_type": building_type,
        "line_type": line_type,
        "line_apply_type": "新設",
        "course": course,
        "campaign_year": str(today.year),
        "campaign_month": f"{today.month:02d}",
        "campaign_day": f"{today.day:02d}",
        "tenyou_no": "",
        "simple_options": collect_simple_options(record),
        # Phase 2: 光電話関連
        "phone_apply": _v(record.get("ドロップダウン_0")),  # 新規発番/番ポあり/申込なし
        "phone_plan": _v(record.get("ドロップダウン_69")),  # 基本プラン/セットプラン
        "phone_options": (record.get("チェックボックス", {}) or {}).get("value", []) or [],
        "phone_existing_no": _v(record.get("文字列__1行__7")),
        "phone_existing_name_kanji": _v(record.get("文字列__1行__8")),
        "phone_existing_name_kana": _v(record.get("文字列__1行__9")),
        "phone_existing_carrier": _v(record.get("ドロップダウン_23")),
        # Phase 3: 光テレビ
        "tv_apply": _v(record.get("ドロップダウン_46")),  # 新規申込/継続利用/申込なし
        # Phase 4: ルーター（1G/10G）
        "router_v6plus_1g": _v(record.get("ドロップダウン_31")),  # 〇/×
        "wireless_lan_card_1g": _v(record.get("ドロップダウン_32")),  # 〇/×
        "router_wifi7_10g": _v(record.get("ドロップダウン_56")),  # 〇/×
        "wireless_lan_10g": _v(record.get("ドロップダウン_57")),  # 〇/×
    }


def parse_url(url: str) -> tuple[int, int]:
    """apclo-sonet://run?app=X&record=Y を (app_id, record_id) にパース"""
    import urllib.parse as up
    parsed = up.urlparse(url)
    if parsed.scheme != "apclo-sonet":
        raise MapError(f"不正なURLスキーム: {parsed.scheme!r}")
    qs = up.parse_qs(parsed.query)
    app = qs.get("app", [""])[0]
    record = qs.get("record", [""])[0]
    if not re.fullmatch(r"\d+", app) or not re.fullmatch(r"\d+", record):
        raise MapError(f"app/record は数値で指定してください: app={app!r}, record={record!r}")
    return int(app), int(record)
