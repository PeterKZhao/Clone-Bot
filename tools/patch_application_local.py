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
    
    print(f"📖 读取配置文件: {yaml_file}")
    content = yaml_file.read_text(encoding='utf-8')
    print(f"✅ 文件大小: {len(content)} 字符")
    
    print("🔧 开始修改配置文件...")
    
    # 1. 删除 Druid 自动配置排除项
    print("  ➜ 删除 Druid 自动配置排除项...")
    content = re.sub(
        r'^\s*- com\.alibaba\.druid\.spring\.boot\.autoconfigure\.DruidDataSourceAutoConfigure[^\n]*\n',
        '',
        content,
        flags=re.MULTILINE
    )
    
    # 2. 替换 master 数据源的 MySQL URL 为 PostgreSQL
    print("  ➜ 替换主数据源 URL...")
    content = re.sub(
        r'url: jdbc:mysql://127\.0\.0\.1:3306/ruoyi-vue-pro\?[^\n]+# MySQL Connector/J 8\.X',
        'url: jdbc:postgresql://${DB_HOST}:5432/future-vue-pro # PostgreSQL',
        content
    )
    
    # 3. 替换 slave 数据源的数据库名
    print("  ➜ 替换从数据源数据库名...")
    content = re.sub(
        r'jdbc:mysql://127\.0\.0\.1:3306/ruoyi-vue-pro\?',
        'jdbc:mysql://127.0.0.1:3306/future-vue-pro?',
        content
    )
    
    # 4. 修改 master 数据源用户名密码（使用简单的行匹配）
    print("  ➜ 修改数据库用户名密码...")
    lines = content.split('\n')
    new_lines = []
    in_master_section = False
    master_url_found = False
    
    for i, line in enumerate(lines):
        # 检测是否进入 master 配置节
        if 'master:' in line and 'primary: master' not in line:
            in_master_section = True
            master_url_found = False
        
        # 如果在 master 节中找到 url
        if in_master_section and 'url: jdbc:postgresql://${DB_HOST}' in line:
            master_url_found = True
        
        # 替换 master 节中的用户名和密码
        if in_master_section and master_url_found:
            if re.match(r'\s+username: root\s*$', line):
                new_lines.append(re.sub(r'root', '${DB_USERNAME}', line))
                continue
            elif re.match(r'\s+password: 123456\s*$', line):
                new_lines.append(re.sub(r'123456', '${DB_PASSWORD}', line))
                in_master_section = False  # 结束 master 节
                continue
        
        # 检测是否离开 master 节（遇到下一个同级或上级配置）
        if in_master_section and master_url_found and line and not line.startswith('          '):
            if line.strip() and not line.startswith('#'):
                in_master_section = False
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    # 5. 修改 TDengine 数据库名（注释中）
    print("  ➜ 修改 TDengine 数据库名...")
    content = re.sub(r'ruoyi_vue_pro', 'future_vue_pro', content)
    
    # 6. 修改 Redis 配置为 spring.data.redis
    print("  ➜ 修改 Redis 配置路径...")
    content = re.sub(
        r'(\s+)# Redis 配置[^\n]*\n(\s+)redis:',
        r'\1# Redis 配置。Redisson 默认的配置足够使用，一般不需要进行调优\n\1data:\n\2redis:',
        content
    )
    
    # 7. 修改 Redis host 为环境变量
    print("  ➜ 修改 Redis host...")
    content = re.sub(
        r'host: 127\.0\.0\.1(\s+# 地址)',
        r'host: ${REDIS_HOST}\1',
        content
    )
    
    # 8. 修改 Redis password 为环境变量（取消注释）
    print("  ➜ 修改 Redis password...")
    content = re.sub(
        r'#\s*password: dev # 密码[^\n]*',
        'password: ${REDIS_PASSWORD} # 密码，建议生产环境开启',
        content
    )
    
    # 9. 修改配置前缀 yudao -> future
    print("  ➜ 修改配置前缀...")
    content = re.sub(r'\byudao:', 'future:', content)
    content = re.sub(r'芋道相关配置', 'Future相关配置', content)
    
    # 10. 修改日志包名
    print("  ➜ 修改日志包名...")
    content = re.sub(
        r'cn\.iocoder\.yudao\.module\.',
        'cn.iocoder.future.module.',
        content
    )
    
    # 11. 修改密码示例
    print("  ➜ 修改密码示例...")
    content = re.sub(r'Yudao@2024', 'Future@2024', content)
    
    # 写入文件
    print(f"💾 写入配置文件...")
    yaml_file.write_text(content, encoding='utf-8')
    print(f"✅ 配置文件修改完成: {yaml_file}")

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 开始修改 application-local.yaml 配置")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    try:
        patch_application_local_yaml()
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🎉 配置文件修改完成！")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return 0

if __name__ == "__main__":
    exit(main())
