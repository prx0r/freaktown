#!/usr/bin/env python3
"""Ella's inbox scanner — Zoho Mail API over OAuth (EU region).

Usage:
  python scan.py                 # show new mail since last scan
  python scan.py --all           # show latest 10 regardless of state
  python scan.py --show <id>     # full content of one message

State lives in emails/.state.json (seen message IDs).
Tokens: reads agent-vault, refreshes as needed (rotation-safe).
Required OAuth scopes: ZohoMail.folders.READ, ZohoMail.messages.READ
(+ the org scopes for setup).
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state.json"
BASE = "https://mail.zoho.eu/api"
ACCOUNT_HINT = 20106757905  # tom@egoic.ai zuid; also the messages accountId


def load_tokens() -> dict:
    with open("/root/.agent-vault/vault.json") as f:
        v = json.load(f)
    return {
        "client_id": v["ZOHO_CLIENT_ID"],
        "client_secret": v["ZOHO_CLIENT_SECRET"],
        "refresh_token": json.load(open("/root/.zohomail/store.json"))["ZOHO_REFRESH_TOKEN"],
    }


def access_token() -> str:
    t = load_tokens()
    r = httpx.post(
        "https://accounts.zoho.eu/oauth/v2/token",
        params={"refresh_token": t["refresh_token"], "grant_type": "refresh_token",
                "client_id": t["client_id"], "client_secret": t["client_secret"]},
        timeout=30).json()
    if "access_token" not in r:
        raise SystemExit(f"token refresh failed: {str(r)[:150]}")
    if r.get("refresh_token"):
        s_path = "/root/.zohomail/store.json"
        s = json.load(open(s_path))
        s["ZOHO_REFRESH_TOKEN"] = r["refresh_token"]
        json.dump(s, open(s_path, "w"), indent=2)
    return r["access_token"]


def api(method: str, path: str, token: str, **kw):
    r = httpx.request(method, BASE + path,
                      headers={"Authorization": f"Zoho-oauthtoken {token}",
                               "Accept": "application/json",
                               "Content-Type": "application/json"},
                      timeout=60, **kw)
    if r.status_code >= 400:
        raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text[:200]}")
    return r.json().get("data", r.json())


def get_inbox_id(token: str) -> str:
    data = api("GET", f"/accounts/{ACCOUNT_HINT}/folders", token)
    folders = data if isinstance(data, list) else data.get("folders", [])
    for f in folders:
        if (f.get("folderName") or "").upper() == "INBOX":
            return f["folderId"]
    raise SystemExit("INBOX folder not found")


def list_messages(token: str, folder_id: str, limit: int = 10):
    data = api("GET", f"/accounts/{ACCOUNT_HINT}/messages/view",
               token, params={"folderId": folder_id, "limit": limit,
                              "sort": "desc", "sortby": "date"})
    return data if isinstance(data, list) else data.get("messages", [])


def message_info(token: str, msg_id: str):
    return api("GET", f"/accounts/{ACCOUNT_HINT}/messages/{msg_id}/info", token)


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"seen": []}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2))


def brief(m: dict) -> str:
    subj = (m.get("subject") or "(no subject)")[:70]
    frm = (m.get("fromAddress") or m.get("sender") or "?")[:40]
    date = str(m.get("receivedTime") or m.get("date") or "?")[:16]
    return f"{m.get('messageId', m.get('id', '?'))} | {date} | {frm} | {subj}"


def main() -> None:
    args = sys.argv[1:]
    token = access_token()
    folder_id = get_inbox_id(token)
    state = load_state()
    seen = set(state.get("seen", []))

    if args[:1] == ["--show"] and len(args) > 1:
        info = message_info(token, args[1])
        print(json.dumps(info, indent=2)[:3000])
        return

    msgs = list_messages(token, folder_id, limit=10)
    fresh = [m for m in msgs
             if str(m.get("messageId", m.get("id"))) not in seen]
    show = msgs if args[:1] == ["--all"] else fresh

    if not show:
        print("No new mail. Inbox is quiet. Ella is disappointed.")
        return

    print(f"{'NEW' if args[:1] != ['--all'] else 'LATEST'} MAIL ({len(show)}):\n")
    for m in show:
        mid = str(m.get("messageId", m.get("id")))
        print("  " + brief(m))
        try:
            info = message_info(token, mid)
            content = info.get("summary") or info.get("snippet") or ""
            if content:
                print("    " + str(content)[:300].replace("\n", " "))
        except SystemExit as e:
            print(f"    (detail fetch failed: {e})")
        seen.add(mid)
    save_state({"seen": sorted(seen)[-200:], "updated": time.time()})
    print(f"\nState saved ({len(seen)} seen tracked).")


if __name__ == "__main__":
    main()
