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
    
    print("🔧 开始修改配置文件...")
    
    # 1. 删除 Druid 自动配置排除项
    content = re.sub(
        r'^\s*- com\.alibaba\.druid\.spring\.boot\.autoconfigure\.DruidDataSourceAutoConfigure.*$\n',
        '',
        content,
        flags=re.MULTILINE
    )
    print("✅ 删除 Druid 自动配置排除项")
    
    # 2. 替换所有 MySQL 连接字符串为 PostgreSQL（包括注释和非注释行）
    # 匹配所有 MySQL URL（包括注释的）
    mysql_patterns = [
        # 主数据源 - MySQL 8.X
        (r'url: jdbc:mysql://127\.0\.0\.1:3306/ruoyi-vue-pro\?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true',
         'url: jdbc:postgresql://${DB_HOST}:5432/future-vue-pro'),
        
        # MySQL 5.X 示例（注释行）
        (r'#\s*url: jdbc:mysql://127\.0\.0\.1:3306/ruoyi-vue-pro\?useSSL=true&allowPublicKeyRetrieval=true&useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai&rewriteBatchedStatements=true',
         '#          url: jdbc:mysql://127.0.0.1:3306/future-vue-pro?useSSL=true&allowPublicKeyRetrieval=true&useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai&rewriteBatchedStatements=true'),
        
        # Slave 数据源
        (r'jdbc:mysql://127\.0\.0\.1:3306/ruoyi-vue-pro\?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&rewriteBatchedStatements=true&nullCatalogMeansCurrent=true',
         'jdbc:mysql://127.0.0.1:3306/future-vue-pro?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&rewriteBatchedStatements=true&nullCatalogMeansCurrent=true'),
    ]
    
    for pattern, replacement in mysql_patterns:
        content = re.sub(pattern, replacement, content)
    
    print("✅ 替换 MySQL 连接为 PostgreSQL")
    
    # 3. 修改数据库用户名和密码为环境变量（只修改非注释的 master 数据源）
    # 使用更精确的匹配，避免替换注释行
    content = re.sub(
        r'(master:\s*\n\s*url:.*\n.*\n.*\n.*\n.*\n.*\n.*\n.*\n\s*)username: root\s*\n\s*password: 123456',
        r'\1username: ${DB_USERNAME}\n          password: ${DB_PASSWORD}',
        content,
        flags=re.DOTALL
    )
    print("✅ 修改主数据源用户名密码为环境变量")
    
    # 4. 修改 slave 和其他数据库名从 ruoyi-vue-pro 到 future-vue-pro
    content = re.sub(
        r'jdbc:mysql://127\.0\.0\.1:3306/ruoyi-vue-pro\?',
        'jdbc:mysql://127.0.0.1:3306/future-vue-pro?',
        content
    )
    
    # 5. 修改 TDengine 数据库名（注释中）
    content = re.sub(
        r'ruoyi_vue_pro',
        'future_vue_pro',
        content
    )
    print("✅ 修改数据库名为 future-vue-pro")
    
    # 6. 修改 Redis 配置路径和使用环境变量
    # 先修改路径为 spring.data.redis
    content = re.sub(
        r'(\s+)# Redis 配置。[^\n]*\n(\s+)redis:',
        r'\1# Redis 配置。Redisson 默认的配置足够使用，一般不需要进行调优\n\1data:\n\2redis:',
        content
    )
    
    # 修改 Redis host 为环境变量
    content = re.sub(
        r'(\s+host: )127\.0\.0\.1( # 地址)',
        r'\1${REDIS_HOST}\2',
        content
    )
    
    # 修改 Redis password 为环境变量
    content = re.sub(
        r'#\s*password: dev # 密码，建议生产环境开启',
        'password: ${REDIS_PASSWORD} # 密码，建议生产环境开启',
        content
    )
    print("✅ 修改 Redis 配置为环境变量")
    
    # 7. 修改所有 yudao 相关配置为 future
    content = re.sub(r'\byudao:', 'future:', content)
    content = re.sub(r'芋道相关配置', 'Future相关配置', content)
    print("✅ 修改配置前缀为 future")
    
    # 8. 修改日志包名
    content = re.sub(
        r'cn\.iocoder\.yudao\.module\.',
        'cn.iocoder.future.module.',
        content
    )
    print("✅ 修改日志包名")
    
    # 9. 修改注释中的密码示例
    content = re.sub(r'Yudao@2024', 'Future@2024', content)
    
    yaml_file.write_text(content, encoding='utf-8')
    print(f"✅ 配置文件修改完成: {yaml_file}")

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 开始修改 application-local.yaml 配置")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    patch_application_local_yaml()
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🎉 配置文件修改完成！")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()
