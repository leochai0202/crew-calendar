"""Isolated CAS radio-relationship diagnostics; never attempt authentication."""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


RADIO_SELECTOR = "input[type='radio'][name='sendType']"
RADIO_RELATIONS_JS = r"""(element) => {
    const selector = "input[type='radio'][name='sendType']";
    const flags = (node) => ({
        hasEmail: !!node && (node.textContent || "").includes("邮箱验证"),
        hasPhone: !!node && (node.textContent || "").includes("手机号验证")
    });
    const tag = (node) => !node ? "NONE" : node.nodeType === 3 ? "TEXT" :
        node.nodeType === 1 ? node.tagName : "OTHER";
    const summary = (node) => ({
        tag: tag(node),
        count: node && node.nodeType === 1 ? node.querySelectorAll(selector).length : 0,
        ...flags(node)
    });
    const sibling = (node) => ({exists: !!node, tag: tag(node), ...flags(node)});
    const ancestors = [];
    let ancestor = element.parentElement;
    for (let depth = 0; depth < 4; depth++) {
        ancestors.push(summary(ancestor));
        ancestor = ancestor ? ancestor.parentElement : null;
    }
    const form = element.closest("form");
    if (!form) throw new Error("SMOKE_RADIO_FORM_MISSING");
    const radios = Array.from(form.querySelectorAll(selector));
    const index = radios.indexOf(element);
    if (index < 0) throw new Error("SMOKE_RADIO_NOT_IN_FORM");
    const segment = (leading) => {
        const range = element.ownerDocument.createRange();
        if (leading) {
            if (index > 0) range.setStartAfter(radios[index - 1]);
            else range.setStart(element.parentNode, 0);
            range.setEndBefore(element);
        } else {
            range.setStartAfter(element);
            if (index + 1 < radios.length) range.setEndBefore(radios[index + 1]);
            else range.setEnd(element.parentNode, element.parentNode.childNodes.length);
        }
        // Text remains inside the browser; only fixed-word booleans leave it.
        const text = range.toString();
        return {hasEmail: text.includes("邮箱验证"), hasPhone: text.includes("手机号验证")};
    };
    return {
        checked: !!element.checked,
        labelsCount: element.labels ? element.labels.length : 0,
        parent: summary(element.parentElement), ancestors,
        next: sibling(element.nextSibling), prev: sibling(element.previousSibling),
        trailing: segment(false), leading: segment(true)
    };
}"""


def _emit(name: str, data: bool | int | str) -> None:
    """Only booleans, nonnegative counts and bounded tag names may be logged."""
    if type(data) is bool:
        safe = str(data).lower()
    elif type(data) is int and data >= 0:
        safe = str(data)
    elif type(data) is str and re.fullmatch(r"[A-Z][A-Z0-9-]{0,39}", data):
        safe = data
    else:
        raise RuntimeError("SMOKE_STRUCTURE_TYPE_INVALID")
    print(f"{name}={safe}")


def _emit_summary(prefix: str, summary: dict) -> None:
    _emit(f"{prefix}_TAG", summary["tag"])
    _emit(f"{prefix}_SENDTYPE_COUNT", summary["count"])
    _emit(f"{prefix}_HAS_EMAIL_TEXT", summary["hasEmail"])
    _emit(f"{prefix}_HAS_PHONE_TEXT", summary["hasPhone"])


def diagnose_radio_relationships(page) -> None:
    form = page.locator("#fm1")
    if form.count() != 1 or not form.is_visible():
        raise RuntimeError("SMOKE_PASSWORD_FORM_NOT_READY")
    radios = form.locator(RADIO_SELECTOR)
    count = radios.count()
    _emit("SMOKE_RADIO_COUNT", count)
    if count != 2:
        raise RuntimeError("SMOKE_RADIO_COUNT_UNEXPECTED")

    for i in range(count):
        radio = radios.nth(i)
        relations = radio.evaluate(RADIO_RELATIONS_JS)
        prefix = f"SMOKE_RADIO_{i + 1}"
        _emit(f"{prefix}_VISIBLE", radio.is_visible())
        _emit(f"{prefix}_CHECKED", relations["checked"])
        _emit(f"{prefix}_LABELS_COUNT", relations["labelsCount"])
        _emit_summary(f"{prefix}_PARENT", relations["parent"])
        if len(relations["ancestors"]) != 4:
            raise RuntimeError("SMOKE_ANCESTOR_COUNT_INVALID")
        for depth, ancestor in enumerate(relations["ancestors"], 1):
            _emit_summary(f"{prefix}_ANCESTOR_{depth}", ancestor)
        for direction in ("next", "prev"):
            sibling = relations[direction]
            sibling_prefix = f"{prefix}_{direction.upper()}"
            _emit(f"{sibling_prefix}_EXISTS", sibling["exists"])
            _emit(f"{sibling_prefix}_TAG", sibling["tag"])
            _emit(f"{sibling_prefix}_HAS_EMAIL_TEXT", sibling["hasEmail"])
            _emit(f"{sibling_prefix}_HAS_PHONE_TEXT", sibling["hasPhone"])
        for direction in ("trailing", "leading"):
            segment = relations[direction]
            _emit(f"{prefix}_{direction.upper()}_SEGMENT_HAS_EMAIL", segment["hasEmail"])
            _emit(f"{prefix}_{direction.upper()}_SEGMENT_HAS_PHONE", segment["hasPhone"])

    for word, name in (("邮箱验证", "EMAIL"), ("手机号验证", "PHONE")):
        matches = form.get_by_text(word, exact=True)
        count = matches.count()
        _emit(f"SMOKE_{name}_TEXT_COUNT", count)
        _emit(f"SMOKE_{name}_TEXT_VISIBLE", sum(matches.nth(i).is_visible() for i in range(count)))


def _stage(stage: str, _details: dict) -> None:
    # Only fixed stage names from the formal panel-preparation function.
    print(f"SMOKE_LOGIN_STAGE={stage}")


def main() -> int:
    # Process-local removal: the unchanged workflow's credentials are not used.
    for name in (
        "CREW_USERNAME", "CREW_PASSWORD", "IMAP_EMAIL", "IMAP_AUTH_CODE",
        "CREW_PHONE", "CREW_LOGIN_PHONE", "CREW_STORAGE_STATE_B64",
        "CREW_PERSISTENT_PROFILE_DIR", "CREW_AUTH_BACKUP_PATH",
        "CREW_AUTH_CONTROL_PATH", "CREW_AUTH_DIAGNOSTIC_PATH",
        "DEBUG", "PWDEBUG", "GITHUB_TOKEN",
    ):
        os.environ.pop(name, None)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    reason = "SMOKE_SETUP_SAFE_FAILURE"
    try:
        from playwright.sync_api import sync_playwright

        from authenticate_crew_session import prepare_login_page_for_auth_method

        with tempfile.TemporaryDirectory(prefix="crew-email-smoke-") as profile:
            with sync_playwright() as playwright:
                context = None
                try:
                    context = playwright.chromium.launch_persistent_context(
                        user_data_dir=profile, channel="msedge", headless=True,
                    )
                    page = context.new_page()
                    reason = "SMOKE_NAVIGATION_SAFE_FAILURE"
                    page.goto(
                        "https://cp.9cair.com", wait_until="domcontentloaded",
                        timeout=90_000,
                    )
                    page.wait_for_url(
                        "https://cas.9cair.com/**", wait_until="domcontentloaded",
                        timeout=45_000,
                    )
                    reason = "SMOKE_PANEL_PREPARE_SAFE_FAILURE"
                    prepare_login_page_for_auth_method(page, stage_reporter=_stage)
                    # No credential fill, verification selection, request or submit.
                    reason = "SMOKE_RADIO_RELATION_SAFE_FAILURE"
                    diagnose_radio_relationships(page)
                    final = urlsplit(page.url)
                    print(f"SMOKE_FINAL_HOST={final.hostname or ''}")
                    print(f"SMOKE_FINAL_PATH={final.path or '/'}")
                finally:
                    if context is not None:
                        context.close()
        print("SMOKE_TEMP_PROFILE_DELETED=true")
        print("SMOKE_DIAGNOSTIC_RESULT=SUCCESS")
        return 0
    except Exception:
        print(f"SMOKE_DIAGNOSTIC_FAILURE_REASON={reason}")
        print("SMOKE_DIAGNOSTIC_RESULT=FAILED")
        return 1
    finally:
        print("EMAIL_OTP_REQUESTS=0")
        print("EMAIL_IMAP_READS=0")


if __name__ == "__main__":
    raise SystemExit(main())
