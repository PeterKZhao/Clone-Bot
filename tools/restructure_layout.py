# tools/restructure_layout.py
import os
import re
import shutil
from pathlib import Path

ROOT_ARTIFACT_ID = "future"
ROOT_GROUP_ID = "cn.iocoder.boot"
ROOT_POM = Path("pom.xml")

# 1) 目录移动计划：只移动顶层模块；模块内部结构先不拆
MOVE_PLAN = {
    "future-dependencies": "platform/future-dependencies",
    "future-framework": "platform/future-framework",
    "future-server": "apps/future-server",

    "future-module-system": "modules/core/system/future-module-system",
    "future-module-infra": "modules/core/infra/future-module-infra",

    "future-module-crm": "modules/biz/crm/future-module-crm",
    "future-module-erp": "modules/biz/erp/future-module-erp",
    "future-module-mall": "modules/biz/mall/future-module-mall",

    "future-module-member": "modules/extend/member/future-module-member",
    "future-module-bpm": "modules/extend/bpm/future-module-bpm",
    "future-module-report": "modules/extend/report/future-module-report",
    "future-module-mp": "modules/extend/mp/future-module-mp",
    "future-module-pay": "modules/extend/pay/future-module-pay",
    "future-module-ai": "modules/extend/ai/future-module-ai",
    "future-module-iot": "modules/extend/iot/future-module-iot",  # 如仍想保持注释，可不写进聚合 POM
}

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def move_dir(src: Path, dst: Path):
    if not src.exists():
        return
    if dst.exists():
        raise RuntimeError(f"Destination exists: {dst}")
    ensure_dir(dst.parent)
    shutil.move(str(src), str(dst))

def relpath_to_root(from_dir: Path) -> str:
    rp = os.path.relpath(ROOT_POM.resolve(), from_dir.resolve())
    return rp.replace("\\", "/")

PARENT_BLOCK = re.compile(r"(<parent>\s*.*?</parent>)", re.DOTALL)
def patch_parent_relativepath(pom_path: Path):
    txt = pom_path.read_text(encoding="utf-8")

    m = PARENT_BLOCK.search(txt)
    if not m:
        return False

    block = m.group(1)
    # 只给 “parent 是根 future” 的模块补 relativePath
    if f"<groupId>{ROOT_GROUP_ID}</groupId>" not in block:
        return False
    if f"<artifactId>{ROOT_ARTIFACT_ID}</artifactId>" not in block:
        return False
    if "<relativePath>" in block:
        return False

    indent_m = re.search(r"\n(\s*)<artifactId>", block)
    indent = indent_m.group(1) if indent_m else "        "

    rp = relpath_to_root(pom_path.parent)
    insert = f"\n{indent}<relativePath>{rp}</relativePath>"
    new_block = block.replace("</parent>", f"{insert}\n{indent}</parent>")

    new_txt = txt[:m.start(1)] + new_block + txt[m.end(1):]
    pom_path.write_text(new_txt, encoding="utf-8")
    return True

def write_aggregator_pom(pom_path: Path, artifact_id: str, modules: list[str]):
    ensure_dir(pom_path.parent)
    rp = relpath_to_root(pom_path.parent)
    modules_xml = "\n".join([f"        <module>{m}</module>" for m in modules])

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>{ROOT_GROUP_ID}</groupId>
        <artifactId>{ROOT_ARTIFACT_ID}</artifactId>
        <version>${{revision}}</version>
        <relativePath>{rp}</relativePath>
    </parent>

    <artifactId>{artifact_id}</artifactId>
    <packaging>pom</packaging>

    <modules>
{modules_xml}
    </modules>
</project>
"""
    pom_path.write_text(content, encoding="utf-8")

def main():
    if not ROOT_POM.exists():
        raise RuntimeError("Run this script at repo root (pom.xml not found).")

    # 1) Move
    for s, d in MOVE_PLAN.items():
        move_dir(Path(s), Path(d))

    # 2) Generate modules aggregator poms（按你规划的 core/biz/extend）
    #   这里不把 iot 默认加进去，你要启用就把它加入 extend_modules
    core_modules = ["core/system", "core/infra"]
    biz_modules = ["biz/crm", "biz/erp", "biz/mall"]
    extend_modules = ["extend/member", "extend/bpm", "extend/report", "extend/mp", "extend/pay", "extend/ai"]
    # extend_modules.append("extend/iot")  # 需要就打开

    write_aggregator_pom(Path("modules/pom.xml"), "future-modules", ["core", "biz", "extend"])
    write_aggregator_pom(Path("modules/core/pom.xml"), "future-modules-core", core_modules)
    write_aggregator_pom(Path("modules/biz/pom.xml"), "future-modules-biz", biz_modules)
    write_aggregator_pom(Path("modules/extend/pom.xml"), "future-modules-extend", extend_modules)

    # 3) 生成每个域的“目录级聚合 pom”，让你目录看起来就像你画的那样（每个域一个 pom.xml）
    # core
    write_aggregator_pom(Path("modules/core/system/pom.xml"), "future-core-system", ["future-module-system"])
    write_aggregator_pom(Path("modules/core/infra/pom.xml"), "future-core-infra", ["future-module-infra"])
    # biz
    write_aggregator_pom(Path("modules/biz/crm/pom.xml"), "future-biz-crm", ["future-module-crm"])
    write_aggregator_pom(Path("modules/biz/erp/pom.xml"), "future-biz-erp", ["future-module-erp"])
    write_aggregator_pom(Path("modules/biz/mall/pom.xml"), "future-biz-mall", ["future-module-mall"])
    # extend
    write_aggregator_pom(Path("modules/extend/member/pom.xml"), "future-ext-member", ["future-module-member"])
    write_aggregator_pom(Path("modules/extend/bpm/pom.xml"), "future-ext-bpm", ["future-module-bpm"])
    write_aggregator_pom(Path("modules/extend/report/pom.xml"), "future-ext-report", ["future-module-report"])
    write_aggregator_pom(Path("modules/extend/mp/pom.xml"), "future-ext-mp", ["future-module-mp"])
    write_aggregator_pom(Path("modules/extend/pay/pom.xml"), "future-ext-pay", ["future-module-pay"])
    write_aggregator_pom(Path("modules/extend/ai/pom.xml"), "future-ext-ai", ["future-module-ai"])
    # write_aggregator_pom(Path("modules/extend/iot/pom.xml"), "future-ext-iot", ["future-module-iot"])

    # 4) Patch relativePath for moved modules whose parent is root future
    changed = 0
    for pom in Path(".").rglob("pom.xml"):
        if pom == ROOT_POM:
            continue
        if patch_parent_relativepath(pom):
            changed += 1

    print(f"✅ done. patched parent relativePath count = {changed}")
    print("ℹ️ Next: update root pom.xml <modules> to point to platform/apps/modules (see below).")

if __name__ == "__main__":
    main()
