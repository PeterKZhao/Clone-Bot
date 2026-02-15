#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import base64
import requests
from nacl import encoding, public

def encrypt_secret(public_key: str, secret_value: str) -> str:
    """使用 libsodium 加密 secret"""
    public_key_bytes = base64.b64decode(public_key)
    sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def get_public_key(owner: str, repo: str, token: str) -> tuple[str, str]:
    """获取仓库的公钥"""
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    return data["key_id"], data["key"]

def create_or_update_secret(owner: str, repo: str, secret_name: str, 
                            encrypted_value: str, key_id: str, token: str):
    """创建或更新仓库 secret"""
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    payload = {
        "encrypted_value": encrypted_value,
        "key_id": key_id
    }
    
    response = requests.put(url, json=payload, headers=headers)
    response.raise_for_status()
    
    if response.status_code == 201:
        print(f"✅ 创建 secret: {secret_name}")
    elif response.status_code == 204:
        print(f"✅ 更新 secret: {secret_name}")

def main():
    # 从环境变量获取参数
    gh_pat = os.environ.get("GH_PAT")
    owner = os.environ.get("OWNER")
    new_repo = os.environ.get("NEW_REPO")
    
    # 需要复制的 secrets 列表
    secrets_to_copy = [
        "DB_HOST",
        "DB_PASSWORD",
        "REDIS_HOST",
        "REDIS_PASSWORD",
        "SSH_HOST",
        "SSH_KEY",
        "SSH_PORT",
        "SSH_USER"
    ]
    
    if not all([gh_pat, owner, new_repo]):
        print("❌ 缺少必需的环境变量: GH_PAT, OWNER, NEW_REPO")
        sys.exit(1)
    
    print(f"🔐 开始复制 secrets 到 {owner}/{new_repo}...")
    
    try:
        # 1. 获取目标仓库的公钥
        print(f"📥 获取 {new_repo} 的公钥...")
        key_id, public_key = get_public_key(owner, new_repo, gh_pat)
        print(f"✅ 获取公钥成功 (key_id: {key_id})")
        
        # 2. 遍历所有 secrets 并复制
        copied = 0
        skipped = 0
        
        for secret_name in secrets_to_copy:
            secret_value = os.environ.get(secret_name)
            
            if not secret_value:
                print(f"⚠️  跳过 {secret_name}: 环境变量不存在或为空")
                skipped += 1
                continue
            
            # 3. 加密 secret
            encrypted_value = encrypt_secret(public_key, secret_value)
            
            # 4. 创建/更新 secret
            create_or_update_secret(
                owner, new_repo, secret_name,
                encrypted_value, key_id, gh_pat
            )
            copied += 1
        
        print(f"\n🎉 完成！已复制 {copied} 个 secrets，跳过 {skipped} 个")
        
    except requests.HTTPError as e:
        print(f"❌ HTTP 错误: {e}")
        print(f"响应内容: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
