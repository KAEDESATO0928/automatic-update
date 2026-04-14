"""複数パターンのテスト実行"""
import os
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
load_dotenv()

from main import (
    LOGIN_URL, LOGIN_ID, PASSWORD, SCREENSHOT_DIR,
    click_and_wait, screenshot,
    step1_login, step2_agency_code, step3_area_input,
    step4_course_select, step5_line_application,
    step6_option_service, step7_option_next,
    step8_member_info, step9_to_confirmation,
)

TEST_CASES = [
    {
        "name": "A_mansion_east_shinsetsu",
        "data": {
            "agency_code": "66EE14",
            "sei": "佐藤", "mei": "花子",
            "sei_kana": "サトウ", "mei_kana": "ハナコ",
            "gender": "女性",
            "birth_year": "1985", "birth_month": "6", "birth_day": "20",
            "postal_code1": "141", "postal_code2": "6010",
            "town": "大崎1丁目", "banchi": "11", "go": "1",
            "building": "ゲートシティ大崎", "room": "302",
            "phone1": "080", "phone2": "9876", "phone3": "5432",
            "building_type": "集合住宅(賃貸)",
            "line_type": "利用していない",
            "line_apply_type": "新設",
            "course": "So-net光M_マンション_東日本",
            "campaign_year": "2026", "campaign_month": "04", "campaign_day": "14",
        },
    },
    {
        "name": "B_kodate_west_tenyou",
        "data": {
            "agency_code": "66EE14",
            "sei": "鈴木", "mei": "一郎",
            "sei_kana": "スズキ", "mei_kana": "イチロウ",
            "gender": "男性",
            "birth_year": "1975", "birth_month": "12", "birth_day": "3",
            "postal_code1": "530", "postal_code2": "0001",
            "town": "北区梅田1丁目", "banchi": "3", "go": "1",
            "building": "", "room": "",
            "phone1": "070", "phone2": "1111", "phone3": "2222",
            "building_type": "戸建(持家)",
            "line_type": "フレッツ・他社コラボ",
            "line_apply_type": "転用",
            "tenyou_no": "W0123456789",
            "course": "So-net光M_戸建_西日本",
            "campaign_year": "2026", "campaign_month": "04", "campaign_day": "14",
        },
    },
    {
        "name": "C_mansion_west_jigyousha",
        "data": {
            "agency_code": "66EE14",
            "sei": "山田", "mei": "美咲",
            "sei_kana": "ヤマダ", "mei_kana": "ミサキ",
            "gender": "女性",
            "birth_year": "2000", "birth_month": "3", "birth_day": "31",
            "postal_code1": "812", "postal_code2": "0011",
            "town": "博多駅前1丁目", "banchi": "1", "go": "1",
            "building": "博多ビル", "room": "501",
            "phone1": "090", "phone2": "5555", "phone3": "6666",
            "building_type": "集合住宅(賃貸)",
            "line_type": "フレッツ・他社コラボ",
            "line_apply_type": "事業者変更",
            "tenyou_no": "T0123456789",
            "course": "So-net光L_マンション_西日本",
            "campaign_year": "2026", "campaign_month": "04", "campaign_day": "14",
        },
    },
]


def run_test(test_case, browser):
    name = test_case["name"]
    row = test_case["data"]

    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

    context = browser.new_context(viewport={"width": 1400, "height": 1000})
    page = context.new_page()

    try:
        step1_login(page)
        step2_agency_code(page, row)
        step3_area_input(page, row)
        step4_course_select(page, row)
        step5_line_application(page, row)
        step6_option_service(page, row)
        step7_option_next(page, row)
        step8_member_info(page, row)
        screenshot(page, f"{name}_08")
        step9_to_confirmation(page)
        screenshot(page, f"{name}_09")

        title = page.title()
        if "確認" in title or "confirm" in title.lower():
            print(f"  PASS: {title}")
        else:
            print(f"  FAIL: {title}")

    except Exception as e:
        print(f"  ERROR: {e}")
        screenshot(page, f"{name}_error")
    finally:
        context.close()


if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for tc in TEST_CASES:
            run_test(tc, browser)
        browser.close()

    print(f"\n{'='*60}")
    print("ALL TESTS DONE")
    print(f"{'='*60}")
