#!/usr/bin/env python3
"""Add admin.oddhobb.com to the figgsite tunnel REMOTE ingress config."""
import json
import urllib.request

ENV = "/home/ubuntu/freaktown/.env"
TID = "54295d83-e7e7-4741-b148-9e0ccf4382f2"


def api(method, path, data=None):
    env = dict(
        line.strip().split("=", 1)
        for line in open(ENV)
        if line.strip() and not line.strip().startswith("#") and "=" in line
    )
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": "Bearer " + env["CLOUDFLARE_API_TOKEN"],
                 "Content-Type": "application/json"},
        method=method,
    )
    return json.load(urllib.request.urlopen(req, timeout=30))


def main():
    acct = dict(
        line.strip().split("=", 1)
        for line in open(ENV)
        if line.strip() and not line.strip().startswith("#") and "=" in line
    )["CLOUDFLARE_ACCOUNT_ID"]
    cur = api("GET", f"/accounts/{acct}/cfd_tunnel/{TID}/configurations")["result"]
    ver = cur["version"]
    cur = cur["config"]
    print("remote version:", ver)
    print("current hosts:", [r.get("hostname") for r in cur.get("ingress", [])])
    rest = [r for r in cur.get("ingress", []) if r.get("hostname") not in (None, "admin.oddhobb.com")]
    catch = [r for r in rest if "hostname" not in r]
    rest = [r for r in rest if "hostname" in r]
    rest.append({"hostname": "admin.oddhobb.com", "service": "http://127.0.0.1:8797"})
    r = api("PUT", f"/accounts/{acct}/cfd_tunnel/{TID}/configurations",
            {"config": {"ingress": rest + catch}, "version": ver})
    print("put success:", r.get("success"), str(r.get("errors"))[:200])


main()
