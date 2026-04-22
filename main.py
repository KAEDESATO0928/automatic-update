import csv
import os
import sys
import time

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page

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


def step6_option_service(page: Page, row: dict):
    """オプションサービス: 一括選択 → 決定"""
    print("[6/9] オプションサービス選択中...")
    # 入力項目無しオプション一括選択
    click_and_wait(page, "#UP1500_option_select")

    # オプション詳細画面で決定（デフォルト選択のまま）
    click_and_wait(page, "#UIOPT0100_next")
    print("  → オプションサービス選択完了")


def step7_option_next(page: Page, row: dict):
    """オプション確認 → 次のページへ進む"""
    print("[7/9] オプション確認 → 次へ...")
    click_and_wait(page, "#submit")
    print("  → 次のページへ進んだ")


def step8_member_info(page: Page, row: dict):
    """入会情報入力"""
    print("[8/9] 入会情報入力中...")

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

    # 無線LANカード: チェック済みなら外す
    page.evaluate("""(function() {
        var cb = document.getElementById('UP4350_wirelessLan');
        if (cb && cb.checked) cb.click();
    })()""")

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
    step6_option_service(page, row)
    step7_option_next(page, row)
    if debug:
        screenshot(page, "07_before_member_info")
    step8_member_info(page, row)
    if debug:
        screenshot(page, "08_after_member_info")
    step9_to_confirmation(page)
    if debug:
        screenshot(page, "09_confirmation")


def run():
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
                    # ブラウザ表示モード: タブを閉じるまで待機
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


if __name__ == "__main__":
    run()
