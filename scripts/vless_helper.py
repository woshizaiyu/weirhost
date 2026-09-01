#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 vless:// / trojan:// / ss:// / vmess:// 解析为 sing-box 配置并启动本地 socks/http 代理"""
import os, json, sys, urllib.parse, subprocess, time, pathlib, base64

def parse_vless(url: str):
    u = urllib.parse.urlparse(url.strip())
    if u.scheme != "vless":
        raise ValueError("not vless")
    uuid = u.username
    host = u.hostname
    port = u.port or 443
    qs = urllib.parse.parse_qs(u.query)
    get = lambda k, d="": qs.get(k, [d])[0]
    path = urllib.parse.unquote(get("path", "/"))
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

def parse_trojan(url: str):
    u = urllib.parse.urlparse(url.strip())
    if u.scheme != "trojan":
        raise ValueError("not trojan")
    pwd = urllib.parse.unquote(u.username or "")
    host = u.hostname
    port = u.port or 443
    qs = urllib.parse.parse_qs(u.query)
    get = lambda k, d="": qs.get(k, [d])[0]
    path = urllib.parse.unquote(get("path", "/"))
    ws_host = get("host", host)
    sni = get("sni", host) or get("peer", host)
    fp = get("fp", "chrome")
    security = get("security", "tls")
    insecure = get("insecure", "0") == "1" or get("allowInsecure", "0") == "1"
    return {
        "password": pwd, "host": host, "port": port,
        "sni": sni, "ws_host": ws_host, "path": path,
        "fp": fp, "security": security, "insecure": insecure,
        "type": get("type", "ws"),
    }

def make_config(p, proto="vless", socks_port=10808, http_port=10809):
    if proto == "vless":
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
    elif proto == "trojan":
        tls_enabled = p["security"] == "tls"
        outbound = {
            "type": "trojan",
            "tag": "proxy",
            "server": p["host"],
            "server_port": p["port"],
            "password": p["password"],
            "transport": {
                "type": "ws",
                "path": p["path"],
                "headers": {"Host": p["ws_host"]},
            }
        }
        if tls_enabled:
            outbound["tls"] = {
                "enabled": True,
                "server_name": p["sni"],
                "insecure": p["insecure"],
                "utls": {"enabled": True, "fingerprint": p["fp"] or "chrome"}
            }
    else:
        raise ValueError(f"unsupported {proto}")
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

def pick_node():
    for k in ("NODE_LINK", "VLESS_NODE", "TROJAN_NODE", "WEIRDHOST_PROXY", "PROXY_NODE"):
        v = os.environ.get(k, "").strip().strip('"').strip("'")
        if v and v.split("://")[0] in ("vless", "trojan", "vmess", "ss", "socks5", "http", "https"):
            return v, k
    return "", ""

def main():
    node, src = pick_node()
    if not node:
        print("[vless_helper] 未检测到节点，跳过")
        return 0
    # 直连代理直接透传
    if node.startswith("socks5://") or node.startswith("http://") or node.startswith("https://"):
        print(f"[vless_helper] 检测到直连代理 {node[:30]}***，透传")
        gha_env = os.environ.get("GITHUB_ENV")
        if gha_env:
            with open(gha_env, "a") as f:
                f.write(f"WEIRDHOST_PROXY={node}\n")
                f.write(f"HTTPS_PROXY={node}\n")
                f.write(f"HTTP_PROXY={node}\n")
        return 0
    scheme = node.split("://")[0]
    if scheme not in ("vless", "trojan"):
        print(f"[vless_helper] 暂不支持 {scheme}，仅支持 vless/trojan/socks5/http")
        return 0
    print(f"[vless_helper] 检测到 {scheme.upper()} 节点 ({src})，解析中...")
    try:
        if node.startswith("vless://"):
            p = parse_vless(node)
            cfg = make_config(p, proto="vless")
        elif node.startswith("trojan://"):
            p = parse_trojan(node)
            cfg = make_config(p, proto="trojan")
        else:
            raise ValueError("unknown scheme")
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
