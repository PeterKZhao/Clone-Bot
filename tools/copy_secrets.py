#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import base64
import requests
from nacl import encoding, public
from typing import NamedTuple

REQUIRED_ENV_VARS = ("GH_PAT", "OWNER", "NEW_REPO")
SECRETS_TO_COPY = [
    "DB_HOST", "DB_USERNAME", "DB_PASSWORD",
    "REDIS_HOST", "REDIS_PASSWORD",
    "SSH_HOST", "SSH_KEY", "SSH_PORT", "SSH_USER",
]
GITHUB_API = "https://api.github.com"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class RepoConfig(NamedTuple):
    owner: str
    repo: str
    token: str


def make_headers(token: str) -> dict:
    return {**GITHUB_HEADERS, "Authorization": f"Bearer {token}"}


def encrypt_secret(public_key: str, secret_value: str) -> str:
    key_bytes = base64.b64decode(public_key)
    box = public.SealedBox(public.PublicKey(key_bytes))
    return base64.b64encode(box.encrypt(secret_value.encode())).decode()


def get_public_key(cfg: RepoConfig) -> tuple[str, str]:
    url = f"{GITHUB_API}/repos/{cfg.owner}/{cfg.repo}/actions/secrets/public-key"
    resp = requests.get(url, headers=make_headers(cfg.token), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data["key_id"], data["key"]


def upsert_secret(cfg: RepoConfig, secret_name: str, encrypted_value: str, key_id: str):
    url = f"{GITHUB_API}/repos/{cfg.owner}/{cfg.repo}/actions/secrets/{secret_name}"
    payload = {"encrypted_value": encrypted_value, "key_id": key_id}
    resp = requests.put(url, json=payload, headers=make_headers(cfg.token), timeout=10)
    resp.raise_for_status()
    action = "创建" if resp.status_code == 201 else "更新"
    print(f"✅ {action} secret: {secret_name}")


def main():
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        print(f"❌ 缺少必需的环境变量: {', '.join(missing)}")
        sys.exit(1)

    cfg = RepoConfig(
        owner=os.environ["OWNER"],
        repo=os.environ["NEW_REPO"],
        token=os.environ["GH_PAT"],
    )

    print(f"🔐 开始复制 secrets 到 {cfg.owner}/{cfg.repo}...")

    try:
        print(f"📥 获取 {cfg.repo} 的公钥...")
        key_id, pub_key = get_public_key(cfg)
        print(f"✅ 获取公钥成功 (key_id: {key_id})")

        copied, skipped = 0, 0
        for secret_name in SECRETS_TO_COPY:
            value = os.environ.get(secret_name)
            if not value:
                print(f"⚠️  跳过 {secret_name}: 环境变量不存在或为空")
                skipped += 1
                continue
            encrypted = encrypt_secret(pub_key, value)
            upsert_secret(cfg, secret_name, encrypted, key_id)
            copied += 1

        print(f"\n🎉 完成！已复制 {copied} 个 secrets，跳过 {skipped} 个")

    except requests.HTTPError as e:
        print(f"❌ HTTP 错误: {e}\n响应内容: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
