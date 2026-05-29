"""kintone レコード(JSON) → main.py の customer dict 形式へ変換"""

import re
from datetime import date

# 新規 vs 事変/転用 判定は「事変番号F・T(11桁)」(文字列__1行__81) で行う:
#   空欄  → 新規開設 → 処理OK
#   値あり → 事変・転用 → 未対応エラー
# （旧仕様の「申込区分」フィールドでの判定は廃止）

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

# 住居形態の表記揺れ吸収（kintone 側の表記差）
DWELLING_ALIASES = {
    "一戸建て": "一戸建て",
    "戸建て": "一戸建て",
    "戸建": "一戸建て",
    "集合住宅": "集合住宅",
    "MS": "集合住宅",
    "ＭＳ": "集合住宅",
    "マンション": "集合住宅",
}

# 申込プラン → コース基本部分（戸建/マンション）。東西は住所から後付け
COURSE_BASE_MAP = {
    "so-net光Mプラン（新規開設・戸建て）": "So-net光M_戸建",
    "so-net光Mプラン（新規開設・MS）": "So-net光M_マンション",
    "so-net光10ギガプラン（新規開設・戸建て）": "So-net光10G_戸建",
    "so-net光10ギガプラン（新規開設・MS）": "So-net光10G_マンション",
}

# NTT東日本エリア（北海道、東北、関東、信越、山梨）
EAST_PREFS = {
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "長野県", "山梨県",
}


def determine_east_west(pref: str) -> str:
    """都道府県名 → 東日本 / 西日本"""
    return "東日本" if pref in EAST_PREFS else "西日本"

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


def extract_agency_code(record: dict) -> str:
    """キャンペーンコード新（label: 商品名：6桁コード）から6桁を抽出。
    未設定なら文字列__1行__36（旧 代理店コードフィールド）にフォールバック。"""
    campaign = _v(record.get("キャンペーンコード"))
    if campaign:
        # 「Tアシ1G標準：66EE14」 → 66EE14 を抽出（半角:も全角：も対応）
        m = re.search(r"[:：]\s*([A-Z0-9]{6})\s*$", campaign)
        if m:
            return m.group(1)
    return _v(record.get("文字列__1行__36"))

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
    dwelling_norm = DWELLING_ALIASES.get(dwelling.strip(), dwelling.strip())
    ownership_norm = "持家" if ownership == "分譲" else ownership
    key = (dwelling_norm, ownership_norm)
    if key not in BUILDING_MAP:
        raise MapError(f"住居形態の組み合わせ未対応: {dwelling!r} × {ownership!r}")
    return BUILDING_MAP[key]


def map_course(plan: str, pref: str = "") -> str:
    """申込プラン + 都道府県 → So-net フォームの course (東/西を住所から判定)"""
    if plan not in COURSE_BASE_MAP:
        raise MapError(f"未対応の申込プラン: {plan!r}")
    return f"{COURSE_BASE_MAP[plan]}_{determine_east_west(pref)}"


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


def _validate_consistency(record: dict):
    """kintoneレコード内の矛盾チェック（So-net側で弾かれる組合せを事前検出）"""
    phone_apply = _v(record.get("ドロップダウン_0"))
    wlan_1g = _v(record.get("ドロップダウン_32"))
    wlan_10g = _v(record.get("ドロップダウン_57"))
    # 無線LANカードは光電話の付属サービス → 光電話なしでは申込不可
    if phone_apply in ("", "申込なし"):
        if wlan_1g == "〇":
            raise MapError(
                "矛盾: 光電話=申込なし のとき【1G限定】無線LANカード=〇 は不可\n"
                "→ 光電話を申し込むか、無線LANカードを × にしてください"
            )
        if wlan_10g == "〇":
            raise MapError(
                "矛盾: 光電話=申込なし のとき【10G限定】10ギガ対応無線LANルーター=〇 は不可\n"
                "→ 光電話を申し込むか、無線LANルーターを × にしてください"
            )


def build_customer(record: dict) -> dict:
    """kintone レコード(JSON) → customer dict 変換"""
    # 事変番号F・T(11桁) で 新規 vs 事変/転用 判定
    jihen_no = _v(record.get("文字列__1行__81")).strip()
    if jihen_no:
        raise MapError(f"事変・転用は未対応です（事変番号F・T: {jihen_no!r}）。新規のみ自動入力できます。")

    _validate_consistency(record)

    by, bm, bd = split_birth(_v(record.get("文字列__1行__19")))
    p1, p2, p3 = split_phone(_v(record.get("文字列__1行__6")))
    building_type = map_building_type(
        _v(record.get("ドロップダウン_2")),
        _v(record.get("ドロップダウン_3")),
    )
    addr_raw = _v(record.get("文字列__1行__11"))
    addr = split_address(addr_raw)
    course = map_course(_v(record.get("申込みプラン")), addr.get("pref", ""))
    line_type = map_line_type(_v(record.get("ドロップダウン_4")))

    today = date.today()

    return {
        "agency_code": extract_agency_code(record),
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
