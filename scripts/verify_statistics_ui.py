"""Production statistics UI check. Run after npm run build in frontend.

Uses real login/API, backs up and restores SQLite, and stops its own backend.
Artifacts are stored in ignored logs/statistics-ui-* directories.
"""
import calendar
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:5093"


def main():
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 5093)) == 0:
            raise RuntimeError("Port 5093 is occupied; will not stop an existing process")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output = ROOT / "logs" / ("statistics-ui-" + stamp)
    output.mkdir(parents=True, exist_ok=False)
    backup = ROOT / ("database.db.ui-test-" + stamp + ".bak")
    backup.touch(exist_ok=False)
    source = sqlite3.connect(str(ROOT / "database.db"))
    target = sqlite3.connect(str(backup))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    backend = None
    result = {"backup": str(backup), "output": str(output), "checks": []}
    log = (output / "backend.log").open("w", encoding="utf-8")
    try:
        backend = subprocess.Popen([sys.executable, "support_planner.py"], cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT)
        for _ in range(80):
            if backend.poll() is not None:
                raise RuntimeError("Backend stopped before startup; see " + str(output))
            try:
                with urllib.request.urlopen(BASE + "/login", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("Backend did not start")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(BASE + "/login")
                page.locator("form input").nth(0).fill("admin")
                page.locator("form input").nth(1).fill("q12345678")
                page.locator("form button[type='submit']").click()
                page.wait_for_url("**/planning**")
                expect(page.locator(".ant-menu-item:visible").filter(has_text="Статистика")).to_be_visible()
                page.wait_for_timeout(700)
                if page.get_by_role("button", name="Понятно", exact=True).is_visible():
                    page.get_by_role("button", name="Понятно", exact=True).click()
                page.locator(".ant-menu-item:visible").filter(has_text="Статистика").click()
                page.wait_for_url("**/statistics")
                expect(page.get_by_role("heading", name="Активные работы по дням")).to_be_visible()
                today = date.today().isoformat()
                expect(page.locator('[data-date="%s"]' % today)).to_have_attribute("aria-pressed", "true")
                page.wait_for_function("!document.querySelector('.statistics-calendar-status').textContent.includes('…')")
                page.screenshot(path=str(output / "desktop-today.png"), full_page=True)
                calendar_height = page.locator('.statistics-calendar-card').bounding_box()['height']
                assert calendar_height <= 400, calendar_height
                page.get_by_role('button', name='Следующий месяц', exact=True).click()
                expect(page.locator('.statistics-calendar-month')).not_to_have_text('')
                assert abs(page.locator('.statistics-calendar-card').bounding_box()['height'] - calendar_height) <= 1
                page.get_by_role('button', name='Сегодня', exact=True).click()
                result['calendar_height_px'] = calendar_height
                result['checks'].append('compact calendar and stable month height')

                api = page.request.get(BASE + "/api/active-assignment-counts/0?start_date=2000-01-01&end_date=2099-12-31")
                assert api.ok, api.status
                available = api.json()
                target_date = max((item["date"] for item in available), default=today)
                target_day = date.fromisoformat(target_date)
                months = (target_day.year - date.today().year) * 12 + target_day.month - date.today().month
                assert abs(months) < 120, "Test data is more than ten years away"
                for _ in range(abs(months)):
                    page.get_by_role("button", name="Следующий месяц" if months > 0 else "Предыдущий месяц", exact=True).click()
                page.wait_for_function("!document.querySelector('.statistics-calendar-status').textContent.includes('…')")
                prefix = target_date[:7]
                counts = {item["date"]: item["count"] for item in available if item["date"].startswith(prefix)}
                for number in range(1, calendar.monthrange(target_day.year, target_day.month)[1] + 1):
                    key = "%s-%02d" % (prefix, number)
                    expect(page.locator('[data-date="%s"] .statistics-calendar-count' % key)).to_have_text(str(counts.get(key, 0)))
                result["checks"].append("all displayed counts match real API")

                button = page.locator('[data-date="%s"]' % target_date)
                button.focus()
                before = page.evaluate("window.scrollY")
                button.press("Enter")
                expect(button).to_have_attribute("aria-pressed", "true")
                assert page.evaluate("window.scrollY") == before
                day_api = page.request.get(BASE + "/api/active-assignments/0?start_date=%s&end_date=%s&limit=20&offset=0" % (target_date, target_date))
                assert day_api.ok
                details = day_api.json()
                if details["items"]:
                    expect(page.locator(".statistics-details .ant-table-row").first).to_contain_text(details["items"][0]["task_name"])
                else:
                    expect(page.get_by_text("Нет активных работ", exact=True)).to_be_visible()
                button.press("Space")
                expect(button).to_have_attribute("aria-pressed", "true")
                page.get_by_role("button", name="К списку работ", exact=True).click()
                assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Список активных работ"
                result["checks"].append("keyboard selection, no auto-scroll, explicit details focus")
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(output / "desktop-dark.png"), full_page=True)
                page.get_by_title("Светлая тема", exact=True).click()
                page.wait_for_timeout(350)
                page.screenshot(path=str(output / "desktop-light.png"), full_page=True)

                page.get_by_text("За период", exact=True).click()
                expect(page.get_by_role("heading", name="Работы за период", exact=False)).to_be_visible()
                inputs = page.locator(".ant-picker-range input")
                inputs.nth(0).fill(target_day.replace(day=1).strftime("%d.%m.%Y"))
                inputs.nth(0).press("Enter")
                inputs.nth(1).fill(target_day.strftime("%d.%m.%Y"))
                inputs.nth(1).press("Enter")
                page.get_by_role("heading", name="Статистика", exact=True).click()
                saved_range = [inputs.nth(i).input_value() for i in range(2)]
                page.get_by_text("По дням", exact=True).click()
                expect(page.locator('[data-date="%s"]' % target_date)).to_have_attribute("aria-pressed", "true")
                page.get_by_text("За период", exact=True).click()
                assert [page.locator(".ant-picker-range input").nth(i).input_value() for i in range(2)] == saved_range
                page.screenshot(path=str(output / "desktop-period.png"), full_page=True)
                result["checks"].append("period selection and dates preserved across modes")

                page.get_by_text("По дням", exact=True).click()
                teams = page.get_by_role("combobox", name="Команды", exact=True)
                teams.focus()
                teams.press("ArrowDown")
                teams.press("Enter")
                teams.press("Escape")
                expect(page.locator('[data-date="%s"]' % target_date)).to_have_attribute("aria-pressed", "true")
                page.wait_for_function("!document.querySelector('.statistics-calendar-status').textContent.includes('…')")
                result["checks"].append("team filtering preserves selected day")
                for width in (390, 320):
                    page.set_viewport_size({"width": width, "height": 844})
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(250)
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Horizontal page overflow at %d" % width
                    assert page.locator(".statistics-calendar-day").first.bounding_box()["width"] >= 28
                    page.screenshot(path=str(output / ("mobile-%d.png" % width)), full_page=True)
                result["checks"].append("390px and 320px layout without page overflow")
                page.get_by_text("За период", exact=True).click()
                page.locator(".ant-picker-range input").first.click()
                popup = page.locator(".statistics-period-popup:visible")
                expect(popup).to_be_visible()
                page.wait_for_timeout(350)
                bounds = popup.bounding_box()
                assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 321, bounds
                popup.screenshot(path=str(output / "mobile-period-popup.png"))
                page.keyboard.press("Escape")
                page.get_by_text("По дням", exact=True).click()
                result["checks"].append("mobile range picker fits viewport")
                page.get_by_role("button", name="Сегодня", exact=True).click()
                expect(page.locator('[data-date="%s"]' % today)).to_have_attribute("aria-pressed", "true")
                assert not errors, errors
                result["checks"].append("today action and no browser errors")
                result["status"] = "passed"
            finally:
                browser.close()
    finally:
        if backend is not None:
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()
                backend.wait(timeout=5)
        log.close()
        # Login/announcements can update user state, so restore even for read-only UI actions.
        source = sqlite3.connect(str(backup))
        target = sqlite3.connect(str(ROOT / "database.db"))
        try:
            source.backup(target)
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(source.iterdump()) == list(target.iterdump()), "Restored contents differ from backup"
            result["database_restored"] = True
        finally:
            target.close()
            source.close()
        (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
