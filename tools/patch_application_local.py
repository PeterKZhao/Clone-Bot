#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

def patch_application_local_yaml():
    """修改 application-local.yaml 配置文件"""
    
    yaml_file = Path("apps/future-server/src/main/resources/application-local.yaml")
    
    if not yaml_file.exists():
        print(f"⚠️  配置文件不存在: {yaml_file}")
        return
    
    print(f"📖 读取配置文件: {yaml_file}")
    content = yaml_file.read_text(encoding='utf-8')
    original_content = content  # 保存原始内容用于对比
    
    print("🔧 开始修改配置文件...")
    
    # 1. 删除 Druid 自动配置排除项
    print("  ➜ 删除 Druid 自动配置排除项...")
    content = content.replace(
        '      - com.alibaba.druid.spring.boot.autoconfigure.DruidDataSourceAutoConfigure # 排除 Druid 的自动配置，使用 dynamic-datasource-spring-boot-starter 配置多数据源\n',
        ''
    )
    
    # 2. 替换主数据源 MySQL URL 为 PostgreSQL
    print("  ➜ 替换主数据源 URL 为 PostgreSQL...")
    content = content.replace(
        '          url: jdbc:mysql://127.0.0.1:3306/future-vue-pro?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true # MySQL Connector/J 8.X 连接的示例',
        '          url: jdbc:mysql://${DB_HOST}:3306/future-vue-pro?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true # MySQL Connector/J 8.X 连接的示例'
#         '          url: jdbc:postgresql://:5432/future-vue-pro'
    )
    
    # 4. 替换主数据源用户名密码
    print("  ➜ 替换主数据源用户名密码...")
    # 精确匹配包含正确缩进的行
    content = content.replace(
        '          username: root\n          password: 123456\n          #          username: sa',
        '          username: ${DB_USERNAME}\n          password: ${DB_PASSWORD}\n          #          username: sa'
    )
    
    # 5. 修改 Redis 配置
    print("  ➜ 修改 Redis 配置...")
    # 修改为 spring.data.redis
    content = content.replace(
        '  # Redis 配置。Redisson 默认的配置足够使用，一般不需要进行调优\n  redis:',
        '  # Redis 配置。Redisson 默认的配置足够使用，一般不需要进行调优\n  data:\n    redis:'
    )
    
    # 修改 Redis host
    content = content.replace(
        '    host: 127.0.0.1 # 地址',
        '      host: ${REDIS_HOST} # 地址'
    )
    
    # 修改 Redis port
    content = content.replace(
        '    port: 6379 # 端口',
        '      port: 6379 # 端口'
    )
    
    # 修改 Redis database
    content = content.replace(
        '    database: 0 # 数据库索引',
        '      database: 0 # 数据库索引'
    )
    
    # 取消注释并设置 Redis password
    content = content.replace(
        '#      password: dev # 密码，建议生产环境开启',
        '        password: ${REDIS_PASSWORD} # 密码，建议生产环境开启'
    )
    
    # 6. 修改配置前缀
    print("  ➜ 修改配置前缀 yudao -> future...")
    content = content.replace('yudao:', 'future:')
    content = content.replace('芋道相关配置', 'Future相关配置')
    
    # 7. 修改日志包名
    print("  ➜ 修改日志包名...")
    content = content.replace('cn.iocoder.yudao.module.', 'cn.iocoder.future.module.')
    
    # 8. 修改密码示例
    print("  ➜ 修改密码示例...")
    content = content.replace('Yudao@2024', 'Future@2024')
    
    # 检查是否有修改
    if content == original_content:
        print("⚠️  警告：文件内容没有任何变化，可能模板已经改变")
    else:
        changes = sum(1 for a, b in zip(original_content, content) if a != b)
        print(f"✅ 文件已修改 ({changes} 个字符变更)")
    
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
