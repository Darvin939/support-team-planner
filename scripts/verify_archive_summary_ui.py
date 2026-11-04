"""Production archive check with real login and WAL-safe database restoration."""
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:5093"


def fingerprint(connection):
    return hashlib.sha256("\n".join(connection.iterdump()).encode("utf-8")).hexdigest()


def main():
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 5093)) == 0:
            raise RuntimeError("Port 5093 is occupied; existing process will not be stopped")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output = ROOT / "logs" / ("archive-summary-ui-" + stamp)
    output.mkdir(parents=True, exist_ok=False)
    backup = ROOT / ("database.db.ui-test-" + stamp + ".bak")
    backup.touch(exist_ok=False)
    with sqlite3.connect(str(ROOT / "database.db")) as source:
        with sqlite3.connect(str(backup)) as target:
            source.backup(target)
            original = fingerprint(target)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = {"backup": str(backup), "output": str(output), "checks": []}
    backend = None
    log = (output / "backend.log").open("w", encoding="utf-8")
    try:
        subprocess.run(["npm.cmd", "run", "build"], cwd=ROOT / "frontend", env=env, check=True)
        with sqlite3.connect(str(ROOT / "database.db")) as db:
            team_id, team_name = db.execute("SELECT id,name FROM teams ORDER BY id LIMIT 1").fetchone()
            segment_id = db.execute("SELECT id FROM segments ORDER BY id LIMIT 1").fetchone()[0]
            description = "Краткая справка\nhttps://example.com/details\n" + "ДлиннаяСтрока" * 120 + "\nСтрока" * 35
            task_id = db.execute(
                "INSERT INTO tasks (team_id,segment_id,name,description,instruction_url,criticality,"
                "task_status,psi_status,completed_at) VALUES (?,?,?,?,?,'high','done','passed',datetime('now'))",
                (team_id, segment_id, "UI-ARCHIVE С инструкцией", description, BASE + "/login?instruction-test=1"),
            ).lastrowid
            db.execute(
                "INSERT INTO tasks (team_id,segment_id,name,task_status,completed_at) "
                "VALUES (?,?,?,'cancelled',datetime('now'))", (team_id, segment_id, "UI-ARCHIVE Без описания"),
            )
            db.execute("INSERT INTO assignments (task_id,date,block,status) VALUES (?,date('now'),'Проверка архива','success')", (task_id,))
        backend = subprocess.Popen([sys.executable, "support_planner.py"], cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT)
        for _ in range(80):
            if backend.poll() is not None:
                raise RuntimeError("Backend stopped; see " + str(output))
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
                page = browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
                page.set_default_timeout(10000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(BASE + "/login")
                page.locator("form input").nth(0).fill("admin")
                page.locator("form input").nth(1).fill("q12345678")
                page.locator("form button[type='submit']").click()
                page.wait_for_url("**/planning**")
                expect(page.locator(".ant-menu-item:visible").filter(has_text="Планирование")).to_be_visible()
                page.wait_for_timeout(700)
                if page.get_by_role("button", name="Понятно", exact=True).is_visible():
                    page.get_by_role("button", name="Понятно", exact=True).click()
                page.get_by_role("combobox").first.fill(team_name)
                page.locator(".ant-select-item-option:visible").filter(has_text=team_name).click()
                page.wait_for_url("**/planning/%s" % team_id)
                expect(page.get_by_role("heading", name="Планирование", exact=True)).to_be_visible()
                page.wait_for_timeout(1000)
                (output / "planning.txt").write_text(page.locator("body").inner_text() + "\nERRORS: " + repr(errors), encoding="utf-8")
                page.screenshot(path=str(output / "planning.png"), full_page=True)
                page.locator("button").filter(has_text="Архив").click()
                modal = page.get_by_role("dialog", name="Архив работ")
                expect(modal).to_be_visible()
                modal.get_by_placeholder("Поиск по названию и описанию").fill("UI-ARCHIVE")
                row = modal.locator(".ant-table-row").filter(has_text="UI-ARCHIVE С инструкцией")
                expect(row).to_be_visible()
                link = row.get_by_role("link", name="Инструкция ↗")
                expect(link).to_have_attribute("target", "_blank")
                expect(link).to_have_attribute("rel", "noopener noreferrer")
                with page.expect_popup() as popup:
                    link.click()
                popup.value.close()
                expect(modal.get_by_role("region", name="Информация о работе")).to_have_count(0)
                row.locator(".ant-table-row-expand-icon").click()
                info = modal.get_by_role("region", name="Информация о работе").first
                expect(info).to_contain_text("Критичность: Высокая")
                expect(info).to_contain_text("ПСИ: ПСИ пройдено")
                expect(info.get_by_role("link", name="https://example.com/details")).to_be_visible()
                expect(modal.get_by_text("Проверка архива", exact=True)).to_be_visible()
                result["checks"].append("real login, archive API, instruction popup without expanding, details and assignment timeline")
                for width, height, label in [(1440, 1000, "desktop"), (390, 844, "mobile")]:
                    page.set_viewport_size({"width": width, "height": height})
                    page.wait_for_timeout(300)
                    metrics = info.evaluate("""element => {
                        const description = element.lastElementChild;
                        const dialog = element.closest('[role=dialog]');
                        return {height: description.clientHeight, scrollHeight: description.scrollHeight,
                            width: description.clientWidth, scrollWidth: description.scrollWidth,
                            dialogWidth: dialog.clientWidth, dialogScrollWidth: dialog.scrollWidth,
                            whiteSpace: getComputedStyle(description).whiteSpace};
                    }""")
                    assert metrics["height"] <= 200 and metrics["scrollHeight"] > metrics["height"], metrics
                    assert metrics["scrollWidth"] <= metrics["width"] + 1, metrics
                    assert metrics["dialogScrollWidth"] <= metrics["dialogWidth"] + 1, metrics
                    assert metrics["whiteSpace"] == "pre-wrap", metrics
                    result[label] = metrics
                    page.screenshot(path=str(output / (label + ".png")), full_page=True)
                result["checks"].append("desktop/mobile description scroll, line breaks, wrapping, bounded modal width")
                page.set_viewport_size({"width": 1440, "height": 1000})
                empty_row = modal.locator(".ant-table-row").filter(has_text="UI-ARCHIVE Без описания")
                expect(empty_row.get_by_role("link")).to_have_count(0)
                empty_row.locator(".ant-table-row-expand-icon").click()
                expect(modal.get_by_role("region", name="Информация о работе").filter(has_text="Не требуется").get_by_text("—", exact=True)).to_be_visible()
                assert not errors, errors
                result["checks"].append("empty instruction and description; no JavaScript errors")
                result["passed"] = True
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
        with sqlite3.connect(str(backup)) as source:
            with sqlite3.connect(str(ROOT / "database.db")) as target:
                source.backup(target)
                target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert fingerprint(target) == original, "Restored database differs from backup"
        result["database_restored"] = True
        result["backend_stopped"] = backend is None or backend.poll() is not None
        (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
