#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 vless:// 解析为 sing-box 配置并启动本地 socks/http 代理"""
import os, json, sys, urllib.parse, subprocess, time, pathlib

def parse_vless(url: str):
    u = urllib.parse.urlparse(url.strip())
    if u.scheme != "vless":
        raise ValueError("not vless")
    uuid = u.username
    host = u.hostname
    port = u.port or 443
    qs = urllib.parse.parse_qs(u.query)
    get = lambda k, d="": qs.get(k, [d])[0]
    # 解码 path
    path = urllib.parse.unquote(get("path", "/"))
    # host header
    ws_host = get("host", host)
    sni = get("sni", host)
    fp = get("fp", "chrome")
    security = get("security", "tls")
    flow = get("flow", "")
    insecure = get("insecure", "0") == "1" or get("allowInsecure", "0") == "1"
    return {
        "uuid": uuid, "host": host, "port": port,
        "sni": sni, "ws_host": ws_host, "path": path,
        "fp": fp, "security": security, "flow": flow, "insecure": insecure,
        "type": get("type", "ws"),
    }

def make_config(p, socks_port=10808, http_port=10809):
    tls_enabled = p["security"] == "tls"
    outbound = {
        "type": "vless",
        "tag": "proxy",
        "server": p["host"],
        "server_port": p["port"],
        "uuid": p["uuid"],
        "flow": p["flow"] if p["flow"] else None,
        "packet_encoding": "",
        "transport": {
            "type": "ws",
            "path": p["path"],
            "headers": {"Host": p["ws_host"]},
            "max_early_data": 0,
            "early_data_header_name": "Sec-WebSocket-Protocol"
        }
    }
    if not outbound["flow"]:
        outbound.pop("flow")
    if tls_enabled:
        outbound["tls"] = {
            "enabled": True,
            "server_name": p["sni"],
            "insecure": p["insecure"],
            "utls": {"enabled": True, "fingerprint": p["fp"] or "chrome"}
        }
    cfg = {
        "log": {"level": "info"},
        "inbounds": [
            {"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": socks_port},
            {"type": "http", "tag": "http-in", "listen": "127.0.0.1", "listen_port": http_port}
        ],
        "outbounds": [outbound, {"type": "direct", "tag": "direct"}, {"type": "block", "tag": "block"}],
        "route": {"rules": [], "final": "proxy"}
    }
    return cfg

def main():
    vless = os.environ.get("VLESS_NODE") or os.environ.get("WEIRDHOST_PROXY") or ""
    vless = vless.strip().strip('"').strip("'")
    if not vless.startswith("vless://"):
        print("[vless_helper] 未检测到 vless://，跳过")
        return 0
    # 兼容部分用户把 vless 填在 WEIRDHOST_PROXY，启动后需把代理改为本地 socks
    print(f"[vless_helper] 检测到 VLESS 节点，解析中...")
    try:
        p = parse_vless(vless)
        cfg = make_config(p)
        cfg_path = "/tmp/singbox.json"
        pathlib.Path(cfg_path).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[vless_helper] 已生成 {cfg_path}")
        print(json.dumps(cfg, ensure_ascii=False, indent=2)[:2000])
        # 写 GITHUB_ENV 供下一步使用
        gha_env = os.environ.get("GITHUB_ENV")
        if gha_env:
            with open(gha_env, "a") as f:
                f.write("WEIRDHOST_PROXY=socks5://127.0.0.1:10808\n")
                f.write("HTTPS_PROXY=socks5://127.0.0.1:10808\n")
                f.write("HTTP_PROXY=socks5://127.0.0.1:10808\n")
            print("[vless_helper] 已写入 GITHUB_ENV，代理指向 socks5://127.0.0.1:10808")
        return 0
    except Exception as e:
        print(f"[vless_helper] 解析失败: {e}")
        import traceback; traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
