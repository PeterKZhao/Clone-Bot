#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
from pathlib import Path

ROOT_GROUP_ID = "cn.iocoder.boot"
MODULE_PREFIX = "future-module-"
SKIP_SUFFIXES = ("-api", "-biz")

# 不参与 api/biz 拆分的模块（参考 yudao-cloud，system/infra 保持整体）
SKIP_MODULES = {
    "future-module-system",
    "future-module-infra",
}

MOVE_API_PACKAGES = True
GROUP_MALL_TRADE_FOLDER = True


# ---------- 通用读写 ----------
def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_text(p: Path, s: str):
    p.write_text(s, encoding="utf-8")


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


# ---------- 轻量 POM 处理 ----------
RE_PARENT_BLOCK = re.compile(r"(<parent>\s*.*?</parent>)", re.DOTALL)
RE_ARTIFACT = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>")
RE_GROUP = re.compile(r"<groupId>\s*([^<]+?)\s*</groupId>")
RE_RELATIVE = re.compile(r"<relativePath>\s*([^<]*?)\s*</relativePath>")
RE_PACKAGING = re.compile(r"<packaging>\s*([^<]+?)\s*</packaging>")

RE_MODULE_LINE = re.compile(r"^(\s*)<module>\s*([^<]+?)\s*</module>\s*$", re.MULTILINE)
RE_DEP_BLOCK = re.compile(r"<dependency>\s*.*?</dependency>", re.DOTALL)
RE_DEP_G = re.compile(r"<groupId>\s*([^<]+?)\s*</groupId>")
RE_DEP_A = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>")
RE_DEP_T = re.compile(r"<type>\s*([^<]+?)\s*</type>")
RE_DEP_C = re.compile(r"<classifier>\s*([^<]+?)\s*</classifier>")


def get_project_artifact_id_only(pom_xml: str) -> str | None:
    pm = RE_PARENT_BLOCK.search(pom_xml)
    ps = pm.span(1) if pm else None
    for m in RE_ARTIFACT.finditer(pom_xml):
        if ps and ps[0] <= m.start(0) <= ps[1]:
            continue
        return m.group(1).strip()
    return None


def get_parent_ga(pom_xml: str) -> tuple[str | None, str | None]:
    pm = RE_PARENT_BLOCK.search(pom_xml)
    if not pm:
        return None, None
    block = pm.group(1)
    gm = RE_GROUP.search(block)
    am = RE_ARTIFACT.search(block)
    return (gm.group(1).strip() if gm else None), (am.group(1).strip() if am else None)


def get_project_group_id_only(pom_xml: str) -> str | None:
    pm = RE_PARENT_BLOCK.search(pom_xml)
    ps = pm.span(1) if pm else None
    for m in RE_GROUP.finditer(pom_xml):
        if ps and ps[0] <= m.start(0) <= ps[1]:
            continue
        return m.group(1).strip()
    return None


def set_project_artifact_id(pom_xml: str, new_aid: str) -> str:
    pm = RE_PARENT_BLOCK.search(pom_xml)
    ps = pm.span(1) if pm else None
    out = []
    last = 0
    replaced = False
    for m in RE_ARTIFACT.finditer(pom_xml):
        if replaced:
            break
        if ps and ps[0] <= m.start(0) <= ps[1]:
            continue
        out.append(pom_xml[last : m.start(1)])
        out.append(new_aid)
        last = m.end(1)
        replaced = True
    if not replaced:
        raise RuntimeError("No project <artifactId> found to replace.")
    out.append(pom_xml[last:])
    return "".join(out)


def has_packaging_pom(pom_xml: str) -> bool:
    m = RE_PACKAGING.search(pom_xml)
    return bool(m and m.group(1).strip() == "pom")


def dedupe_modules(xml: str) -> str:
    lines = xml.splitlines(True)
    seen = set()
    out = []
    for line in lines:
        m = RE_MODULE_LINE.match(line.rstrip("\n"))
        if not m:
            out.append(line)
            continue
        mod = m.group(2).strip()
        if mod in seen:
            continue
        seen.add(mod)
        out.append(line)
    return "".join(out)


def dep_key(dep_xml: str):
    gid = RE_DEP_G.search(dep_xml).group(1).strip() if RE_DEP_G.search(dep_xml) else ""
    aid = RE_DEP_A.search(dep_xml).group(1).strip() if RE_DEP_A.search(dep_xml) else ""
    typ = RE_DEP_T.search(dep_xml).group(1).strip() if RE_DEP_T.search(dep_xml) else "jar"
    cls = RE_DEP_C.search(dep_xml).group(1).strip() if RE_DEP_C.search(dep_xml) else ""
    return (gid, aid, typ, cls)


def remove_self_and_dedupe_deps(pom_xml: str) -> str:
    gid_proj = get_project_group_id_only(pom_xml) or ROOT_GROUP_ID
    aid_proj = get_project_artifact_id_only(pom_xml)
    if not aid_proj:
        return pom_xml
    seen = set()

    def repl(m):
        dep = m.group(0)
        k = dep_key(dep)
        if k[0] == gid_proj and k[1] == aid_proj:
            return ""
        if k in seen:
            return ""
        seen.add(k)
        return dep

    return RE_DEP_BLOCK.sub(repl, pom_xml)


def has_dep(pom_xml: str, gid: str, aid: str) -> bool:
    for m in RE_DEP_BLOCK.finditer(pom_xml):
        dep = m.group(0)
        gm = RE_DEP_G.search(dep)
        am = RE_DEP_A.search(dep)
        if gm and am and gm.group(1).strip() == gid and am.group(1).strip() == aid:
            return True
    return False


def add_dep_if_missing(pom_xml: str, gid: str, aid: str, version_expr="${revision}") -> str:
    if has_dep(pom_xml, gid, aid):
        return pom_xml
    dep_xml = f"""        <dependency>
            <groupId>{gid}</groupId>
            <artifactId>{aid}</artifactId>
            <version>{version_expr}</version>
        </dependency>
"""
    if "<dependencies>" in pom_xml and "</dependencies>" in pom_xml:
        return re.sub(r"</dependencies>", dep_xml + "    </dependencies>", pom_xml, count=1)
    for anchor in ["</description>", "</url>", "</name>", "</packaging>"]:
        if anchor in pom_xml:
            return pom_xml.replace(
                anchor,
                anchor + "\n\n    <dependencies>\n" + dep_xml + "    </dependencies>",
                1,
            )
    return pom_xml + "\n    <dependencies>\n" + dep_xml + "    </dependencies>\n"


# ---------- parent.relativePath 自动修复 ----------
def find_parent_pom_by_artifact_id(start_dir: Path, parent_artifact_id: str) -> Path | None:
    cur = start_dir.resolve()
    while True:
        candidate = cur / "pom.xml"
        if candidate.exists():
            try:
                xml = read_text(candidate)
                if get_project_artifact_id_only(xml) == parent_artifact_id:
                    return candidate
            except Exception:
                pass
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def ensure_parent_relativepath_auto(pom_path: Path):
    xml = read_text(pom_path)
    pm = RE_PARENT_BLOCK.search(xml)
    if not pm:
        return
    parent_gid, parent_aid = get_parent_ga(xml)
    if not parent_aid:
        return
    parent_pom = find_parent_pom_by_artifact_id(pom_path.parent, parent_aid)
    if not parent_pom:
        return
    rel = os.path.relpath(parent_pom.resolve(), pom_path.parent.resolve()).replace("\\", "/")
    block = pm.group(1)
    if RE_RELATIVE.search(block):
        new_block = RE_RELATIVE.sub(f"<relativePath>{rel}</relativePath>", block, count=1)
    else:
        indent_m = re.search(r"\n(\s*)<artifactId>", block)
        indent = indent_m.group(1) if indent_m else "        "
        new_block = block.replace(
            "</parent>",
            f"\n{indent}<relativePath>{rel}</relativePath>\n{indent}</parent>",
        )
    new_xml = xml[: pm.start(1)] + new_block + xml[pm.end(1) :]
    if new_xml != xml:
        write_text(pom_path, new_xml)


# ---------- 代码迁移 ----------
def move_api_packages(biz_dir: Path, api_dir: Path) -> int:
    biz_java = biz_dir / "src" / "main" / "java"
    if not biz_java.exists():
        return 0
    moved = 0
    for api_pkg_dir in list(biz_java.rglob("api")):
        if not api_pkg_dir.is_dir():
            continue
        try:
            rel = api_pkg_dir.relative_to(biz_java)
        except ValueError:
            continue
        dst = api_dir / "src" / "main" / "java" / rel
        if dst.exists():
            continue
        ensure_dir(dst.parent)
        shutil.move(str(api_pkg_dir), str(dst))
        moved += 1
    return moved


# ---------- 拆分核心 ----------
def discover_base_modules(repo_root: Path) -> list[Path]:
    """
    找到需要拆分的模块，满足以下所有条件：
    - artifactId 以 future-module- 开头
    - 不在 SKIP_MODULES 中（system/infra 保持整体，参考 yudao-cloud）
    - 不已经是 -api 或 -biz 结尾
    - packaging 不是 pom（聚合模块不拆）
    - 有 src/main/java（真正的业务 jar）
    """
    targets = []
    for pom in repo_root.rglob("pom.xml"):
        if pom.resolve() == (repo_root / "pom.xml").resolve():
            continue
        xml = read_text(pom)
        aid = get_project_artifact_id_only(xml)
        if not aid:
            continue
        if not aid.startswith(MODULE_PREFIX):
            continue
        if aid in SKIP_MODULES:                          # ← 跳过 system / infra
            continue
        if aid.endswith(SKIP_SUFFIXES):
            continue
        if has_packaging_pom(xml):
            continue
        if not (pom.parent / "src" / "main" / "java").exists():
            continue
        targets.append(pom.parent)

    uniq, seen = [], set()
    for d in targets:
        rp = str(d.resolve())
        if rp not in seen:
            uniq.append(d)
            seen.add(rp)
    return sorted(uniq)


def create_api_module_from_base(base_pom_xml: str, api_dir: Path, api_aid: str):
    ensure_dir(api_dir)
    api_xml = set_project_artifact_id(base_pom_xml, api_aid)

    def drop_dep(m):
        dep = m.group(0)
        gm = RE_DEP_G.search(dep)
        am = RE_DEP_A.search(dep)
        if not am:
            return dep
        gid = gm.group(1).strip() if gm else ""
        if gid == ROOT_GROUP_ID and am.group(1).strip() == api_aid:
            return ""
        return dep

    api_xml = RE_DEP_BLOCK.sub(drop_dep, api_xml)
    api_xml = remove_self_and_dedupe_deps(api_xml)
    write_text(api_dir / "pom.xml", api_xml)
    ensure_parent_relativepath_auto(api_dir / "pom.xml")
    print(f"  ✅ 创建 api 模块: {api_dir}")


def rename_base_to_biz(base_dir: Path, biz_dir: Path, biz_aid: str, api_aid: str | None):
    if biz_dir.exists():
        print(f"  ℹ️  biz 模块已存在，跳过: {biz_dir}")
        return
    shutil.move(str(base_dir), str(biz_dir))
    biz_pom = biz_dir / "pom.xml"
    biz_xml = read_text(biz_pom)
    biz_xml = set_project_artifact_id(biz_xml, biz_aid)
    if api_aid:
        biz_xml = add_dep_if_missing(biz_xml, ROOT_GROUP_ID, api_aid)
    biz_xml = remove_self_and_dedupe_deps(biz_xml)
    write_text(biz_pom, biz_xml)
    ensure_parent_relativepath_auto(biz_pom)
    print(f"  ✅ 创建 biz 模块: {biz_dir}")


def update_parent_aggregator(parent_dir: Path, old_name: str, api_name: str, biz_name: str):
    pom = parent_dir / "pom.xml"
    if not pom.exists():
        return
    xml = read_text(pom)
    old_line_pattern = re.compile(
        r"(\s*)<module>\s*" + re.escape(old_name) + r"\s*</module>"
    )
    m = old_line_pattern.search(xml)
    if not m:
        return
    indent = m.group(1)
    new_lines = (
        f"{indent}<module>{api_name}</module>"
        f"{indent}<module>{biz_name}</module>"
    )
    xml = old_line_pattern.sub(new_lines, xml, count=1)
    xml = dedupe_modules(xml)
    write_text(pom, xml)
    print(f"  ✅ 更新聚合 pom: {pom}")


def update_downstream_consumers(repo_root: Path, old_aid: str, biz_aid: str):
    """
    扫描全仓库 pom.xml，将对 old_aid 的依赖替换为 biz_aid。
    SKIP_MODULES 中的模块不参与拆分，因此也不会触发此函数，无需额外过滤。
    """
    for pom in repo_root.rglob("pom.xml"):
        xml = read_text(pom)
        current_aid = get_project_artifact_id_only(xml)
        if current_aid in (old_aid, biz_aid, old_aid + "-api"):
            continue

        result = []
        last = 0
        modified = False

        for m in RE_DEP_BLOCK.finditer(xml):
            dep = m.group(0)
            gm = RE_DEP_G.search(dep)
            am = RE_DEP_A.search(dep)
            if (
                gm and am
                and gm.group(1).strip() == ROOT_GROUP_ID
                and am.group(1).strip() == old_aid
            ):
                new_dep = dep[: am.start(1)] + biz_aid + dep[am.end(1) :]
                result.append(xml[last : m.start()])
                result.append(new_dep)
                last = m.end()
                modified = True

        if modified:
            result.append(xml[last:])
            write_text(pom, "".join(result))
            print(f"  ✅ 更新下游消费者: {pom}  ({old_aid} → {biz_aid})")


# ---------- 入口 ----------
def main():
    repo_root = Path(".")
    if not (repo_root / "pom.xml").exists():
        raise RuntimeError("❌ 请在项目根目录（pom.xml 所在处）运行此脚本")

    print("⏭️  跳过拆分的模块（保持整体）:")
    for s in sorted(SKIP_MODULES):
        print(f"   • {s}")

    base_modules = discover_base_modules(repo_root)
    print(f"\n🔍 发现 {len(base_modules)} 个待拆分模块:")
    for d in base_modules:
        print(f"   • {d}")

    if not base_modules:
        print("⚠️  未找到需要拆分的模块，退出")
        return

    # 第一轮：执行目录拆分
    split_map: dict[str, str] = {}  # old_aid -> biz_aid

    for base_dir in base_modules:
        base_pom = base_dir / "pom.xml"
        base_xml = read_text(base_pom)
        base_aid = get_project_artifact_id_only(base_xml)
        if not base_aid:
            print(f"⚠️  无法读取 artifactId，跳过: {base_dir}")
            continue

        api_aid = base_aid + "-api"
        biz_aid = base_aid + "-biz"
        api_dir = base_dir.parent / (base_dir.name + "-api")
        biz_dir = base_dir.parent / (base_dir.name + "-biz")

        print(f"\n✂️  拆分: {base_aid}")
        print(f"   ├── {api_aid}")
        print(f"   └── {biz_aid}")

        # 1. 创建 api 模块（必须在 move 之前，base_dir 还在原位）
        if not api_dir.exists():
            create_api_module_from_base(base_xml, api_dir, api_aid)
            if MOVE_API_PACKAGES:
                moved = move_api_packages(base_dir, api_dir)
                if moved:
                    print(f"  📦 迁移 api/** 包: {moved} 个目录")

        # 2. base 目录重命名为 biz
        rename_base_to_biz(base_dir, biz_dir, biz_aid, api_aid)

        # 3. 更新父聚合 pom 的 <modules> 列表
        update_parent_aggregator(base_dir.parent, base_dir.name, api_dir.name, biz_dir.name)

        split_map[base_aid] = biz_aid

    # 第二轮：统一更新所有下游消费者（如 future-server）
    print("\n🔄 更新下游消费者依赖声明...")
    for old_aid, biz_aid in split_map.items():
        update_downstream_consumers(repo_root, old_aid, biz_aid)

    print("\n🎉 全部拆分完成！")


if __name__ == "__main__":
    main()
