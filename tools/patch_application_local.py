#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from pathlib import Path

def patch_application_local_yaml():
    """修改 application-local.yaml 配置文件"""
    
    yaml_file = Path("apps/future-server/src/main/resources/application-local.yaml")
    
    if not yaml_file.exists():
        print(f"⚠️  配置文件不存在: {yaml_file}")
        return
    
    content = yaml_file.read_text(encoding='utf-8')
    
    # 1. 删除 Druid 自动配置排除项
    content = re.sub(
        r'^\s*- com\.alibaba\.druid\.spring\.boot\.autoconfigure\.DruidDataSourceAutoConfigure.*$\n',
        '',
        content,
        flags=re.MULTILINE
    )
    
    # 2. 修改数据库连接为 PostgreSQL（使用环境变量）
    # 修改 master 数据源 URL
    content = re.sub(
        r'url: jdbc:mysql://127\.0\.0\.1:3306/ruoyi-vue-pro\?[^\n]+',
        'url: jdbc:postgresql://${DB_HOST}:5432/future-vue-pro',
        content
    )
    
    # 修改数据库用户名和密码为环境变量
    content = re.sub(
        r'(\s+)(username: root)(\s+#[^\n]*)?\n\s+password: 123456',
        r'\1username: ${DB_USERNAME}\n\1password: ${DB_PASSWORD}',
        content
    )
    
    # 3. 修改 slave 数据源数据库名
    content = re.sub(
        r'jdbc:mysql://127\.0\.0\.1:3306/ruoyi-vue-pro\?',
        'jdbc:mysql://127.0.0.1:3306/future-vue-pro?',
        content
    )
    
    # 4. 修改 TDengine 数据库名（注释中）
    content = re.sub(
        r'ruoyi_vue_pro',
        'future_vue_pro',
        content
    )
    
    # 5. 修改 Redis 配置路径和使用环境变量
    content = re.sub(
        r'(\s+)# Redis 配置.*\n(\s+)redis:',
        r'\1# Redis 配置。Redisson 默认的配置足够使用，一般不需要进行调优\n\1data:\n\2redis:',
        content
    )
    
    content = re.sub(
        r'(\s+host: )127\.0\.0\.1( # 地址)',
        r'\1${REDIS_HOST}\2',
        content
    )
    
    content = re.sub(
        r'#\s*password: dev # 密码',
        'password: ${REDIS_PASSWORD} # 密码',
        content
    )
    
    # 6. 修改所有 yudao 相关配置为 future
    content = re.sub(r'\byudao:', 'future:', content)
    content = re.sub(r'芋道相关配置', 'Future相关配置', content)
    
    # 7. 修改日志包名
    content = re.sub(
        r'cn\.iocoder\.yudao\.module\.',
        'cn.iocoder.future.module.',
        content
    )
    
    # 8. 修改注释中的密码示例
    content = re.sub(r'Yudao@2024', 'Future@2024', content)
    
    yaml_file.write_text(content, encoding='utf-8')
    print(f"✅ 已修改配置文件: {yaml_file}")

def main():
    print("🚀 开始修改 application-local.yaml 配置...")
    patch_application_local_yaml()
    print("🎉 配置文件修改完成！")

if __name__ == "__main__":
    main()
