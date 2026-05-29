import csv
import os
import sys
import time
import traceback

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page

import kintone_client
import record_mapper

load_dotenv()

LOGIN_URL = "https://www.so-net.ne.jp/signup/sst/UISST0290.xhtml"
LOGIN_ID = os.getenv("SONET_LOGIN_ID")
PASSWORD = os.getenv("SONET_PASSWORD")

SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def screenshot(page: Page, name: str):
    """ページ全体のスクリーンショットを保存"""
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    print(f"  screenshot: {path}")

# コース選択のIDマッピング
# フォーマット: UP1060Useable_entry_{code}
# HCOE = 東日本, HCOW = 西日本
# 21 = M戸建, 22 = Mマンション, 23 = L戸建, 24 = Lマンション
# 31 = 10G戸建, 32 = 10Gマンション
COURSE_MAP = {
    "So-net光M_戸建_東日本": "HCOE2101",
    "So-net光M_マンション_東日本": "HCOE2201",
    "So-net光M_戸建_西日本": "HCOW2101",
    "So-net光M_マンション_西日本": "HCOW2201",
    "So-net光L_戸建_東日本": "HCOE2301",
    "So-net光L_マンション_東日本": "HCOE2401",
    "So-net光L_戸建_西日本": "HCOW2301",
    "So-net光L_マンション_西日本": "HCOW2401",
    "So-net光10G_戸建_東日本": "HCOE3101",
    "So-net光10G_マンション_東日本": "HCOE3201",
    "So-net光10G_戸建_西日本": "HCOW3101",
    "So-net光10G_マンション_西日本": "HCOW3201",
}

# 回線申し込み種別
ORDER_KIND_MAP = {
    "新設": "UP4320_orderKind1",
    "転用": "UP4320_orderKind2",
    "事業者変更": "UP4320_orderKind3",
}


def click_and_wait(page: Page, selector: str, wait: float = 3):
    """JSF対応: JS click → ナビゲーション待機"""
    page.evaluate(f"document.querySelector('{selector}').click()")
    time.sleep(1)
    page.wait_for_load_state("networkidle")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(wait)


def step1_login(page: Page):
    """ログイン"""
    print("[1/9] ログイン中...")
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")
    page.fill("#UP1390_loginId", LOGIN_ID)
    page.fill("#UP1390_password", PASSWORD)
    click_and_wait(page, "#UISST0290_login")
    print("  → ログイン完了")


def step2_agency_code(page: Page, row: dict):
    """代理店コード入力 + キャンペーン適用基準日"""
    print("[2/9] 代理店コード入力中...")
    page.fill("#UP1360_agentCd", row["agency_code"])
    click_and_wait(page, "#UP1360_confirm")

    page.fill("#UP1370_campaignApplyYear", row["campaign_year"])
    page.fill("#UP1370_campaignApplyMonth", row["campaign_month"])
    page.fill("#UP1370_campaignApplyDate", row["campaign_day"])
    click_and_wait(page, "#UISST0260_next")
    print("  → 代理店コード入力完了")


def step3_area_input(page: Page, row: dict):
    """利用エリア入力（郵便番号）"""
    print("[3/9] 利用エリア入力中...")
    page.fill("#UP1020_zipCd1", row["postal_code1"])
    page.fill("#UP1020_zipCd2", row["postal_code2"])
    click_and_wait(page, "#UISST0040_next")
    print("  → エリア入力完了")


def step4_course_select(page: Page, row: dict):
    """コース選択"""
    print("[4/9] コース選択中...")
    course = row.get("course", "So-net光M_戸建_西日本")
    course_code = COURSE_MAP.get(course, "HCOW2101")
    selector = f"#UP1060Useable_entry_{course_code}"
    click_and_wait(page, selector)
    print(f"  → コース選択完了: {course}")


def step5_line_application(page: Page, row: dict):
    """回線申し込み種別（新設/転用/事業者変更）"""
    print("[5/9] 回線種別選択中...")
    apply_type = row.get("line_apply_type", "新設")
    radio_id = ORDER_KIND_MAP.get(apply_type, "UP4320_orderKind1")
    page.click(f"#{radio_id}")
    time.sleep(0.5)
    click_and_wait(page, "#UISST0146_next")
    print(f"  → 回線種別選択完了: {apply_type}")


def _save_page_html(page: Page, name: str):
    """ページHTMLを page_html/ に保存（デバッグ用）"""
    os.makedirs("page_html", exist_ok=True)
    path = os.path.join("page_html", f"{name}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page.content())
    print(f"  HTML saved: {path}")


# 光電話プラン: kintone値 → So-net radio value
PHONE_PLAN_MAP = {
    "基本プラン": "810200",
    "セットプラン": "810201",
}

# 光電話 付加サービス: kintoneのチェック値 → So-netのcheckboxインデックス
PHONE_OPTION_INDEX = {
    "発信者番号表示サービス": 0,
    "ナンバーリクエスト": 1,
    "通話中着信サービス": 2,
    "着信転送サービス": 3,
    "着信拒否サービス": 4,
    "着信お知らせメール": 5,
    "ダブルチャネル": 6,
    "マイナンバー": 7,
}


def _configure_phone(page: Page, row: dict):
    """UIOPT4100 (光電話設定画面) の入力"""
    phone_apply = row.get("phone_apply", "")
    print(f"  光電話申込: {phone_apply}")

    # NTEL 「選択する」ボタンで UIOPT4100 へ遷移
    page.evaluate("UP1310_addOption('NTEL')")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    _save_page_html(page, "phone_config")

    # 申込種別: 「利用していない（新規申込）」を選択
    page.check("#UP9700_orderKind1")
    time.sleep(0.5)  # JS で displayTarget が表示されるのを待つ

    # プラン選択
    plan = row.get("phone_plan", "基本プラン")
    plan_value = PHONE_PLAN_MAP.get(plan, "810200")
    page.evaluate(
        f"document.querySelector('input[name=\"UP9170_NTEL01\"][value=\"{plan_value}\"]').click()"
    )
    print(f"    ✓ プラン: {plan} (value={plan_value})")

    # 付加サービス（複数チェック）
    phone_options = row.get("phone_options", [])
    for opt in phone_options:
        idx = PHONE_OPTION_INDEX.get(opt)
        if idx is None:
            print(f"    ⚠ 未対応の付加サービス: {opt}")
            continue
        page.check(f"#UP9170_selectOptionName_check_2_{idx}")
        print(f"    ✓ 付加サービス: {opt} (check_2_{idx})")

    # 番号取得方法
    if phone_apply == "番ポあり":
        page.check("#UP9720_portabilityFlg2")  # value=1 番号ポータビリティ
        print("    ✓ 番号取得方法: 番号ポータビリティ")
    else:  # 新規発番
        page.check("#UP9720_portabilityFlg1")  # value=0 新規採番
        print("    ✓ 番号取得方法: 新規採番")

    # 決定 → UISST0230 (option select) に戻る、カートに光電話が入った状態
    click_and_wait(page, "#UIOPT4100_next")
    time.sleep(1)
    print("  → 光電話設定完了（UISST0230 に戻る）")


def _configure_router(page: Page, row: dict):
    """UIOPT0030 (v6プラス対応ルーター設定画面) 配送先=契約者と同じ前提で記入"""
    print("  v6プラス対応ルーター 申込: 〇")

    # JPRT 「選択する」ボタンで UIOPT0030 へ遷移
    page.evaluate("UP1310_addOption('JPRT')")
    page.wait_for_load_state("networkidle")
    time.sleep(1)

    # 配送先郵便番号
    page.fill("#UP9650_zipCode1", row.get("postal_code1", ""))
    page.fill("#UP9650_zipCode2", row.get("postal_code2", ""))
    # 郵便番号から検索ボタンで都道府県・市区町村を自動補完
    page.click("#UP9650_searchAddress")
    time.sleep(1.5)
    print("    ✓ 郵便番号検索で都道府県/市区町村自動補完")

    # 町名・番地（kintoneの分割結果を結合）
    town = row.get("town", "")
    banchi = row.get("banchi", "")
    go = row.get("go", "")
    if banchi and go:
        section = f"{town}{banchi}-{go}"
    elif banchi:
        section = f"{town}{banchi}"
    else:
        section = town
    page.fill("#UP9650_section", section)
    print(f"    ✓ 配送先町名: {section}")

    # 建物名、部屋番号
    if row.get("building"):
        page.fill("#UP9650_building", row["building"])
    if row.get("room"):
        page.fill("#UP9650_roomNumber", row["room"])

    # 氏名
    page.fill("#UP9650_lastName", row.get("sei", ""))
    page.fill("#UP9650_firstName", row.get("mei", ""))

    # 配送先電話番号
    page.fill("#UP9650_tel1", row.get("phone1", ""))
    page.fill("#UP9650_tel2", row.get("phone2", ""))
    page.fill("#UP9650_tel3", row.get("phone3", ""))

    # 連絡先電話番号
    page.fill("#UP9650_contactTel1", row.get("phone1", ""))
    page.fill("#UP9650_contactTel2", row.get("phone2", ""))
    page.fill("#UP9650_contactTel3", row.get("phone3", ""))

    # 決定
    click_and_wait(page, "#UIOPT0030_next")
    time.sleep(1)
    print("  → ルーター設定完了（UISST0230 に戻る）")


def _configure_tv(page: Page, row: dict):
    """UIOPT4110 (光テレビ設定画面) の入力。新規申込/継続利用どちらも同じ操作"""
    tv_apply = row.get("tv_apply", "")
    print(f"  光テレビ申込: {tv_apply}")

    # NTTV 「選択する」ボタンで UIOPT4110 へ遷移
    page.evaluate("UP1310_addOption('NTTV')")
    page.wait_for_load_state("networkidle")
    time.sleep(1)

    # 申込種別: 「利用していない（新規申込）」を選択（ラジオは1個のみ）
    page.check("#UP9700_orderKind1")
    time.sleep(0.5)
    print("    ✓ 申込種別: 利用していない（新規申込）")

    # 決定
    click_and_wait(page, "#UIOPT4110_next")
    time.sleep(1)
    print("  → 光テレビ設定完了（UISST0230 に戻る）")


def step5b_10g_router(page: Page, row: dict):
    """10Gコース時、UISST0230 の前に挟まる10ギガ対応ルーター選択画面 (UISST0070, form UIOPT4635)"""
    cur_url = page.url
    if "UISST0070" not in cur_url:
        return  # 10Gコース以外はこの画面は出ない
    print("[5b] 10ギガ対応ルーター画面...")
    want_wifi7 = row.get("router_wifi7_10g") == "〇"
    want_10g_wlan = row.get("wireless_lan_10g") == "〇"

    if want_wifi7:
        # value=1 Wi-Fi7 → 配送先入力あり
        page.check("#UP9665_nert_apply_ari")
        time.sleep(0.5)
        _fill_10g_wifi7_delivery(page, row)
        print("  ✓ Wi-Fi7対応10ギガルーター + 配送先入力")
    elif want_10g_wlan:
        # value=2 10G LAN ルーター → 配送先入力不要
        page.check("#UP9665_ntrt_apply_ari")
        print("  ✓ 10ギガ対応無線LANルーターをレンタル")
    else:
        # value=0 ご自身で用意
        page.check("#UP9665_apply_nashi")
        print("  ✓ ご自身で用意")

    click_and_wait(page, "#UIOPT4635_next")

    # 10ギガ対応ルーター画面は2段階(入力→確認)。確認段階が残ってたら再度決定
    for _ in range(2):  # 最大2回まで再クリック
        time.sleep(1)
        if "UISST0230" in page.url:
            break  # 通常オプション画面に到達
        if page.locator("#UIOPT4635_next").count() > 0:
            print(f"  10Gルーター段階継続 ({page.url}) → 再度決定")
            click_and_wait(page, "#UIOPT4635_next")
        else:
            break

    print("  → 10ギガ対応ルーター選択完了")


def _fill_10g_wifi7_delivery(page: Page, row: dict):
    """UIOPT4635 で Wi-Fi7 選択時の配送先入力 (UP9667_*)"""
    page.fill("#UP9667_zipCode1", row.get("postal_code1", ""))
    page.fill("#UP9667_zipCode2", row.get("postal_code2", ""))
    page.click("#UP9667_searchAddress")
    time.sleep(1.5)

    town = row.get("town", "")
    banchi = row.get("banchi", "")
    go = row.get("go", "")
    if banchi and go:
        addr = f"{town}{banchi}-{go}"
    elif banchi:
        addr = f"{town}{banchi}"
    else:
        addr = town
    page.fill("#UP9667_town", addr)

    if row.get("building"):
        page.fill("#UP9667_building", row["building"])
    if row.get("room"):
        page.fill("#UP9667_roomNumber", row["room"])
    page.fill("#UP9667_familyName", row.get("sei", ""))
    page.fill("#UP9667_firstName", row.get("mei", ""))
    page.fill("#UP9667_tel1", row.get("phone1", ""))
    page.fill("#UP9667_tel2", row.get("phone2", ""))
    page.fill("#UP9667_tel3", row.get("phone3", ""))
    # 連絡先電話番号 (緊急) — Wi-Fi7選択時は必須
    page.fill("#UP9667_telEmrg1", row.get("phone1", ""))
    page.fill("#UP9667_telEmrg2", row.get("phone2", ""))
    page.fill("#UP9667_telEmrg3", row.get("phone3", ""))


def step6_option_service(page: Page, row: dict):
    """オプションサービス: 光電話 → 一括選択 → 詳細画面で個別チェック → 決定"""
    print("[6/9] オプションサービス選択中...")
    print(f"  current URL: {page.url}")

    # 1Gは UISST0230、10Gは UIOPT4635 で同じ form id="UISST0230" を持つ
    if "UISST0230" not in page.url and "UIOPT4635" not in page.url:
        page_id = page.url.rsplit("/", 1)[-1].split(".")[0]
        _save_page_html(page, f"unknown_{page_id}")
        screenshot(page, f"unknown_{page_id}")
        print(f"  ⏸ 想定外URL ({page.url}): HTML保存して停止")
        page.wait_for_event("close", timeout=0)
        return

    # === 光電話 (NTEL) ===
    phone_apply = row.get("phone_apply", "")
    if phone_apply and phone_apply != "申込なし":
        _configure_phone(page, row)

    # === 光テレビ (NTTV) ===
    tv_apply = row.get("tv_apply", "")
    if tv_apply and tv_apply != "申込なし":
        _configure_tv(page, row)

    # === v6プラス対応ルーター (JPRT) — 1G のみ ===
    # 10G のルーター/Wi-Fi7 は step5b で既に処理済み
    if row.get("router_v6plus_1g") == "〇":
        _configure_router(page, row)

    # === 設定不要オプション（シンプル9個） ===
    # 「入力項目無しオプション一括選択」ボタンで option_detail へ遷移
    click_and_wait(page, "#UP1500_option_select")

    selected = row.get("simple_options", [])
    if selected:
        print(f"  申込オプション: {selected}")
        for code in selected:
            idx = record_mapper.SO_NET_CHECKBOX_INDEX.get(code)
            if idx is None:
                print(f"  ⚠ 未対応オプションコード: {code}")
                continue
            selector = f"#UP3020_checked_{idx}"
            page.check(selector)
            print(f"    ✓ {code} → {selector}")
    else:
        print("  申込オプションなし")

    click_and_wait(page, "#UIOPT0100_next")
    print("  → オプションサービス選択完了")


def step7_option_next(page: Page, row: dict):
    """オプション確認 → 次のページへ進む"""
    print("[7/9] オプション確認 → 次へ...")
    page.click("#submit", force=True)
    # 入会情報入力ページの姓フィールドが出現するまで待つ（URL不変でも判定可能）
    try:
        page.wait_for_selector("#UP2010_usrFamilyNameKnj", timeout=20000)
        print("  → 次のページへ進んだ")
    except Exception:
        page_id = page.url.rsplit("/", 1)[-1].split(".")[0]
        _save_page_html(page, f"step7_stuck_{page_id}")
        screenshot(page, f"07_stuck_{page_id}")
        print(f"  ⏸ 次のページへ進めず HTML保存して停止")
        page.wait_for_event("close", timeout=0)


def step8_member_info(page: Page, row: dict):
    """入会情報入力"""
    print("[8/9] 入会情報入力中...")
    print(f"  URL: {page.url}")
    # ID存在チェック
    has_sei_field = page.locator("#UP2010_usrFamilyNameKnj").count()
    print(f"  #UP2010_usrFamilyNameKnj 要素数: {has_sei_field}")
    if has_sei_field == 0:
        page_id = page.url.rsplit("/", 1)[-1].split(".")[0]
        _save_page_html(page, f"step8_unknown_{page_id}")
        screenshot(page, f"08_unknown_{page_id}")
        print(f"  ⏸ 想定外の入会情報ページ HTML保存して停止")
        page.wait_for_event("close", timeout=0)
        return

    # お名前
    page.fill("#UP2010_usrFamilyNameKnj", row["sei"])
    page.fill("#UP2010_usrFirstNameKnj", row["mei"])

    # カタカナ
    page.fill("#UP2010_usrFamilyNameKana", row["sei_kana"])
    page.fill("#UP2010_usrFirstNameKana", row["mei_kana"])

    # 性別
    if row.get("gender", "男性") == "男性":
        page.click("#UP2010_sex_0")  # value=1 男性
    else:
        page.click("#UP2010_sex_1")  # value=2 女性

    # 生年月日 (selectのvalueはゼロパディングなし: "1","2",...,"12")
    page.select_option("#UP2010_birthYearKind_Year", row["birth_year"])
    time.sleep(0.5)
    page.select_option("#UP2010_birthYearKind_Month", str(int(row["birth_month"])))
    time.sleep(0.5)
    page.select_option("#UP2010_birthYearKind_Day", str(int(row["birth_day"])))

    # 住所（入会証送付先）- 郵便番号から検索で自動入力
    page.fill("#UP2010_usrAddrZipCd1", row["postal_code1"])
    page.fill("#UP2010_usrAddrZipCd2", row["postal_code2"])
    page.click("#UP2010_searchAddress")
    time.sleep(5)

    # 町名・番地 - 検索後に自動入力されるのを待ってから上書き
    page.fill("#UP2010_usrAddrTownName", row.get("town", ""))
    page.fill("#UP2010_usrAddrBlock1", row.get("banchi", ""))
    page.fill("#UP2010_usrAddrBlock2", row.get("go", ""))

    # マンション・ビル名、部屋番号
    building = row.get("building", "")
    if building:
        page.fill("#UP2010_usrAddrBuildingName", building)
    room = row.get("room", "")
    if room:
        page.fill("#UP2010_usrAddrRoomNo", room)

    # 連絡先電話番号
    page.fill("#UP2010_telNo1", row.get("phone1", ""))
    page.fill("#UP2010_telNo2", row.get("phone2", ""))
    page.fill("#UP2010_telNo3", row.get("phone3", ""))

    # 日中の連絡先: 「ご連絡先電話番号」と同じ
    page.click("#UP2010_contactTelKbn0")  # value=0: 同じ

    # お支払い方法: 決済情報をあとで登録
    page.click("#UP2030_paymentKindKbn_kessaiatodetoroku")  # value=06

    # --- 回線種別による分岐 ---
    apply_type = row.get("line_apply_type", "新設")
    is_shinsetsu = (apply_type == "新設")

    # 転用/事業者変更の場合: 承諾番号と契約者名
    if not is_shinsetsu:
        tenyou_no = row.get("tenyou_no", "")
        if tenyou_no:
            if apply_type == "転用":
                page.fill("#UP4300_divAgreeNo", tenyou_no)
            else:  # 事業者変更
                page.fill("#UP4300_bizdivAgreeNo", tenyou_no)
        # 契約者名（カタカナ）
        page.fill("#UP4300_contractFamilyNameKana", row["sei_kana"])
        page.fill("#UP4300_contractFirstNameKana", row["mei_kana"])
        # 事業者変更は漢字名も必要
        if apply_type == "事業者変更":
            knj_sei = page.locator("#UP4300_contractFamilyNameKnj")
            if knj_sei.count() > 0:
                page.fill("#UP4300_contractFamilyNameKnj", row["sei"])
                page.fill("#UP4300_contractFirstNameKnj", row["mei"])

        # 重要説明事項に同意する
        page.evaluate("""(function() {
            var cb = document.getElementById('UP4300_confirmAgreement');
            if (cb && !cb.checked) cb.click();
        })()""")

    # --- 利用場所住所 ---
    # 新設: UP4311_*, 転用/事業者変更: UP4310_*
    addr_prefix = "UP4311" if is_shinsetsu else "UP4310"

    # 「会員情報をコピー」ボタン
    copy_btn = page.locator(f"#{addr_prefix}_copyUserAdrsInfo")
    if copy_btn.count() > 0:
        copy_btn.click()
        time.sleep(2)

    # 郵便番号を手動セット（フォールバック）
    page.evaluate(f"""(function() {{
        var z1 = document.getElementById('{addr_prefix}_zipCd1');
        var z2 = document.getElementById('{addr_prefix}_zipCd2');
        if (z1 && !z1.value) z1.value = '{row["postal_code1"]}';
        if (z2 && !z2.value) z2.value = '{row["postal_code2"]}';
    }})()""")

    # 検索実行（非表示の場合もあるのでJS click）
    page.evaluate(f"""(function() {{
        var btn = document.getElementById('{addr_prefix}_searchAddress');
        if (btn) btn.click();
    }})()""")
    time.sleep(7)

    # モーダル処理
    modal_btns = page.locator(".modal-dialog-actions button, .modal-dialog a")
    if modal_btns.count() > 0:
        modal_btns.first.click()
        time.sleep(3)
    page.evaluate("document.querySelectorAll('.modal-overlay, .modal-dialog').forEach(e => e.remove())")
    time.sleep(1)

    # 住所検索で自動入力されない場合、入会証送付先から直接コピー
    pref_id = f"{addr_prefix}_prfct" if is_shinsetsu else f"{addr_prefix}_prfct"
    pref_val = page.evaluate(f"(function(){{ var e=document.getElementById('{pref_id}'); return e?e.value:''; }})()")

    if not pref_val:
        # readonly/disabled解除
        city_id = f"{addr_prefix}_cityName"
        sect_id = "UP4311_sectName" if is_shinsetsu else f"{addr_prefix}_townName"
        fields = [
            f"{addr_prefix}_prfct", city_id, sect_id,
            f"{addr_prefix}_block1", f"{addr_prefix}_block2", f"{addr_prefix}_block3",
            f"{addr_prefix}_buildingName", f"{addr_prefix}_roomNo",
            f"{addr_prefix}_constDwellingform",
        ]
        import json
        fields_json = json.dumps(fields)
        page.evaluate(f"""(function() {{
            var targets = {fields_json};
            targets.forEach(function(id) {{
                var el = document.getElementById(id);
                if (el) {{
                    el.classList.remove('d-gray-readonly');
                    el.removeAttribute('readonly');
                    el.removeAttribute('disabled');
                    if (el.tagName === 'SELECT') {{
                        var opts = el.querySelectorAll('option');
                        opts.forEach(function(o) {{ o.disabled = false; }});
                    }}
                }}
            }});
        }})()""")
        time.sleep(0.5)

        # 値をコピー
        page.evaluate(f"""(function() {{
            function copyVal(srcId, dstId) {{
                var s = document.getElementById(srcId);
                var d = document.getElementById(dstId);
                if (s && d) d.value = s.value;
            }}
            copyVal('UP2010_usrAddrPrfct', '{addr_prefix}_prfct');
            copyVal('UP2010_usrAddrCityName', '{city_id}');
            copyVal('UP2010_usrAddrTownName', '{sect_id}');
            copyVal('UP2010_usrAddrBlock1', '{addr_prefix}_block1');
            copyVal('UP2010_usrAddrBlock2', '{addr_prefix}_block2');
            copyVal('UP2010_usrAddrBuildingName', '{addr_prefix}_buildingName');
            copyVal('UP2010_usrAddrRoomNo', '{addr_prefix}_roomNo');
        }})()""")
        time.sleep(1)

    # 建物タイプ
    BUILDING_TYPE_MAP = {
        "戸建(持家)": "01", "戸建(賃貸)": "02",
        "集合住宅(分譲)": "03", "集合住宅(賃貸)": "04",
    }
    building_type = row.get("building_type", "")
    bt_value = BUILDING_TYPE_MAP.get(building_type, "")
    if bt_value:
        page.evaluate(f"""(function() {{
            var sel = document.getElementById('{addr_prefix}_constDwellingform');
            if (sel) {{
                sel.classList.remove('d-gray-readonly');
                var opts = sel.querySelectorAll('option');
                opts.forEach(function(o) {{ o.disabled = false; }});
                sel.value = '{bt_value}';
            }}
        }})()""")

    # 提供判定ボタン（新設のみ）
    if is_shinsetsu:
        page.evaluate("var btn = document.querySelector('input[value=\"提供判定\"]'); if (btn) btn.click();")
        time.sleep(5)
        page.evaluate("document.querySelectorAll('.modal-overlay, .modal-dialog').forEach(e => e.remove())")
        time.sleep(1)

    # 現在ご利用中の光回線（新設のみ）
    if is_shinsetsu:
        LINE_STATUS_MAP = {
            "利用していない": "UP7050_exist_line_kbn_0",
            "フレッツ・他社コラボ": "UP7050_exist_line_kbn_1",
            "その他": "UP7050_exist_line_kbn_2",
        }
        line_status_id = LINE_STATUS_MAP.get(row.get("line_type", "利用していない"), "UP7050_exist_line_kbn_0")
        page.evaluate(f"document.getElementById('{line_status_id}').click()")

    # 工事希望日: 取得可能な最短の工事日を希望する
    page.evaluate("document.getElementById('UP4375_constReqKbn1').click()")

    # 無線LANカード: kintone値で制御 (〇=チェック / それ以外=外す)
    want_wlan = (row.get("wireless_lan_card_1g") == "〇") or (row.get("wireless_lan_10g") == "〇")
    page.evaluate(f"""(function() {{
        var cb = document.getElementById('UP4350_wirelessLan');
        if (!cb) return;
        if ({str(want_wlan).lower()}) {{
            if (!cb.checked) cb.click();
        }} else {{
            if (cb.checked) cb.click();
        }}
    }})()""")
    print(f"  ✓ 無線LANカード: {'申込' if want_wlan else '未申込'}")

    # 利用場所住所セクションの値をテキストで出力
    addr_values = page.evaluate("""
        (function() {
            var ids = ['UP4311_zipCd1','UP4311_zipCd2','UP4311_constDwellingform',
                       'UP4311_prfct','UP4311_cityName','UP4311_sectName',
                       'UP4311_townName_noMust','UP4311_block1','UP4311_block2',
                       'UP4311_buildingName','UP4311_roomNo'];
            var result = {};
            ids.forEach(function(id) {
                var el = document.getElementById(id);
                if (el) result[id] = el.value;
            });
            return result;
        })()
    """)
    print("  利用場所住所の値:")
    for k, v in addr_values.items():
        print(f"    {k}: '{v}'")

    screenshot(page, "08_usage_address")
    print("  → 入会情報入力完了")


def step9_to_confirmation(page: Page):
    """次のページへ進む → 確認画面で停止"""
    print("[9/9] 確認画面へ遷移中...")
    click_and_wait(page, "#submit")

    # ページタイトル確認
    title = page.title()
    print(f"  ページタイトル: {title}")

    # エラーメッセージを確認（ピンク背景のフィールドやcautionメッセージ）
    errors = page.evaluate("""(function() {
        var msgs = [];
        // d-cautionクラスで非表示でないもの
        document.querySelectorAll('p.d-caution').forEach(function(el) {
            if (!el.classList.contains('d-hide') && el.textContent.trim()) {
                msgs.push(el.textContent.trim());
            }
        });
        // サーバーエラー
        document.querySelectorAll('.serverError, .d-server-error, [class*="error"]').forEach(function(el) {
            if (el.textContent.trim()) msgs.push('SERVER: ' + el.textContent.trim());
        });
        // 上部の赤帯メッセージ
        document.querySelectorAll('p.d-guidance, div.d-guidance').forEach(function(el) {
            var t = el.textContent.trim();
            if (t && t.indexOf('誤り') >= 0) msgs.push('GUIDANCE: ' + t);
        });
        return msgs;
    })()""")
    if errors:
        print("  バリデーションエラー:")
        for e in errors:
            print(f"    - {e}")
        # エラーフィールドを特定（ピンク背景の入力欄）
        err_fields = page.evaluate("""(function() {
            var fields = [];
            document.querySelectorAll('.d-err-field, input.d-err-field, select.d-err-field').forEach(function(el) {
                fields.push({id: el.id, name: el.name, tag: el.tagName});
            });
            // d-cautionが表示されているものの親trのth
            document.querySelectorAll('p.d-caution:not(.d-hide)').forEach(function(el) {
                var tr = el.closest('tr');
                if (tr) {
                    var th = tr.querySelector('th');
                    if (th) fields.push({label: th.textContent.trim()});
                }
            });
            return fields;
        })()""")
        if err_fields:
            print("  エラーフィールド:")
            for f in err_fields:
                print(f"    {f}")
    else:
        print("  エラーなし")
    print("=" * 50)
    print("  ★ 確認画面に到達しました")
    print("  ★ 内容を確認し、問題なければ手動で申込ボタンを押してください")
    print("=" * 50)


def load_customers(csv_path: str) -> list[dict]:
    with open(csv_path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def process_customer(page: Page, row: dict, debug: bool = False):
    step1_login(page)
    step2_agency_code(page, row)
    step3_area_input(page, row)
    step4_course_select(page, row)
    step5_line_application(page, row)
    step5b_10g_router(page, row)
    step6_option_service(page, row)
    step7_option_next(page, row)
    if debug:
        screenshot(page, "07_before_member_info")
    step8_member_info(page, row)
    # 番ポありなら portability セクションを追加入力
    if row.get("phone_apply") == "番ポあり":
        step8b_portability(page, row)
    if debug:
        screenshot(page, "08_after_member_info")
    step9_to_confirmation(page)
    if debug:
        screenshot(page, "09_confirmation")


def step8b_portability(page: Page, row: dict):
    """番号ポータビリティ詳細入力（step8 member_info 画面の追加セクション）"""
    print("[8b/9] 番ポ詳細入力中...")

    # 注意事項確認
    page.check("#UP4315_banpoConfirmAgreement")
    print("  ✓ 注意事項確認")

    # 電話番号を3-3-4分割（固定電話想定）
    import re as _re
    raw = _re.sub(r"\D", "", row.get("phone_existing_no", "") or "")
    if len(raw) == 11 and raw[:3] in ("070", "080", "090"):
        p1, p2, p3 = raw[:3], raw[3:7], raw[7:11]
    elif len(raw) >= 10:
        p1, p2, p3 = raw[:3], raw[3:6], raw[6:10]
    else:
        p1, p2, p3 = raw[:3], raw[3:6], raw[6:]
    page.fill("#UP4315_banpoTelNo1", p1)
    page.fill("#UP4315_banpoTelNo2", p2)
    page.fill("#UP4315_banpoTelNo3", p3)
    print(f"  ✓ 電話番号: {p1}-{p2}-{p3}")

    # 電話サービス
    svc_code = record_mapper.map_phone_service(row.get("phone_existing_carrier", ""))
    page.select_option("#UP4315_telSrvcCd", svc_code)
    print(f"  ✓ 電話サービス: {row.get('phone_existing_carrier', '')!r} → {svc_code}")

    # 契約者名（固定電話名義人）— 自動補完値を上書き
    page.fill("#UP4315_telContractNamej1", row.get("phone_existing_name_kanji", ""))
    page.fill("#UP4315_telContractNamek1", row.get("phone_existing_name_kana", ""))
    print(f"  ✓ 契約者名: {row.get('phone_existing_name_kanji', '')} / {row.get('phone_existing_name_kana', '')}")
    print("  → 番ポ詳細入力完了")


def _show_error(title: str, message: str):
    """エラー表示: Windows MessageBox (ctypes、embedded Python でも動作)"""
    print(f"\n[ERROR] {title}: {message}", file=sys.stderr)
    try:
        import ctypes
        # MB_ICONERROR (0x10) | MB_SYSTEMMODAL (0x1000)
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10 | 0x1000)
    except Exception:
        pass


def _drive_one_customer(customer: dict, debug: bool = False):
    """1顧客を Firefox で処理してブラウザクローズまで待つ"""
    if not LOGIN_ID or not PASSWORD:
        _show_error("認証情報不足", ".env に SONET_LOGIN_ID と SONET_PASSWORD を設定してください。")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False, slow_mo=300)
        context = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = context.new_page()
        try:
            print(f"\n{'='*50}")
            print(f"顧客: {customer.get('sei','')} {customer.get('mei','')}")
            print(f"{'='*50}")
            process_customer(page, customer, debug=debug)
            print("\nブラウザで確認画面を確認してください。")
            print("タブ/ブラウザを閉じると処理を終了します。")
            page.wait_for_event("close", timeout=0)
        except Exception as e:
            print(f"\nエラーが発生しました: {e}")
            traceback.print_exc()
            if debug:
                try:
                    screenshot(page, "error")
                except Exception:
                    pass
            # ブラウザは閉じず操作者の判断に委ねる
            try:
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass
        finally:
            try:
                browser.close()
            except Exception:
                pass


def run_with_url(url: str, debug: bool = False):
    """apclo-sonet://run?app=X&record=Y を受けて kintone→Firefox 実行"""
    print(f"URL受信: {url}")
    try:
        app_id, record_id = record_mapper.parse_url(url)
    except record_mapper.MapError as e:
        _show_error("URLパース失敗", str(e))
        sys.exit(1)

    subdomain = os.getenv("KINTONE_SUBDOMAIN")
    token = os.getenv("KINTONE_API_TOKEN")
    if not subdomain or not token:
        _show_error("kintone設定不足", ".env に KINTONE_SUBDOMAIN / KINTONE_API_TOKEN を設定してください。")
        sys.exit(1)

    print(f"kintone取得: app={app_id}, record={record_id}")
    client = kintone_client.KintoneClient(subdomain, token)
    try:
        record = client.get_record(app_id, record_id)
    except kintone_client.KintoneError as e:
        _show_error("kintone取得失敗", str(e))
        sys.exit(1)

    try:
        customer = record_mapper.build_customer(record)
    except record_mapper.MapError as e:
        _show_error("レコード変換失敗", str(e))
        sys.exit(1)

    print("[変換後 customer dict]")
    for k, v in customer.items():
        print(f"  {k}: {v!r}")

    _drive_one_customer(customer, debug=debug)


def run_with_csv():
    """customer_data.csv モード (旧仕様、後方互換)"""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    csv_path = args[0] if args else "customer_data.csv"
    customers = load_customers(csv_path)

    if not customers:
        print("顧客データがありません。customer_data.csv を確認してください。")
        return

    if not LOGIN_ID or not PASSWORD:
        print(".env に SONET_LOGIN_ID と SONET_PASSWORD を設定してください。")
        return

    debug = "--debug" in sys.argv
    headless = "--headless" in sys.argv or debug

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=headless, slow_mo=0 if headless else 300)
        context = browser.new_context(viewport={"width": 1400, "height": 1000})

        for i, customer in enumerate(customers):
            print(f"\n{'='*50}")
            print(f"顧客 {i+1}/{len(customers)}: {customer['sei']} {customer['mei']}")
            print(f"{'='*50}")

            page = context.new_page()
            try:
                process_customer(page, customer, debug=debug)

                if headless:
                    print("\n処理完了（headlessモード）")
                else:
                    print("\nブラウザで確認画面を確認してください。")
                    print("タブを閉じると次の顧客に進みます。")
                    page.wait_for_event("close", timeout=0)
            except Exception as e:
                print(f"\nエラーが発生しました: {e}")
                if debug:
                    screenshot(page, "error")
            finally:
                if not page.is_closed():
                    page.close()

        browser.close()
    print("\n全顧客の処理が完了しました。")


def run():
    """エントリポイント: argv[1] が apclo-sonet:// で始まるか判定して分岐"""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    debug = "--debug" in sys.argv
    if args and args[0].startswith("apclo-sonet://"):
        run_with_url(args[0], debug=debug)
    else:
        run_with_csv()


if __name__ == "__main__":
    run()
