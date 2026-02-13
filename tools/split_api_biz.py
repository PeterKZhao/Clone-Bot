#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
from pathlib import Path

ROOT_GROUP_ID = "cn.iocoder.boot"
ROOT_ARTIFACT_ID = "future"
ROOT_POM = Path("pom.xml")

# 只对这些 artifactId 前缀做拆分
MODULE_PREFIX = "future-module-"

# 已经是 api/biz 的不再拆
SKIP_SUFFIXES = ("-api", "-biz")

# 是否尝试搬运 Java 包到 api 模块（只搬 src/main/java 下的 .../api/...）
MOVE_API_PACKAGES = True


# -------------------------
# 基础文件操作
# -------------------------
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_text(p: Path, s: str):
    p.write_text(s, encoding="utf-8")


def is_root_pom(p: Path) -> bool:
    return p.resolve() == ROOT_POM.resolve()


def relpath_to_root(from_dir: Path) -> str:
    rp = os.path.relpath(ROOT_POM.resolve(), from_dir.resolve())
    return rp.replace("\\", "/")


# -------------------------
# POM 解析/修改（尽量用正则做“小手术”，避免洗掉注释与格式）
# -------------------------
RE_ARTIFACT_ID = re.compile(r"(<artifactId>\s*)([^<]+)(\s*</artifactId>)")
RE_PACKAGING = re.compile(r"<packaging>\s*([^<]+)\s*</packaging>")
RE_PARENT_BLOCK = re.compile(r"(<parent>\s*.*?</parent>)", re.DOTALL)
RE_MODULE_LINE = re.compile(r"^(\s*)<module>\s*([^<]+?)\s*</module>\s*$", re.MULTILINE)


def get_first_tag_value(xml: str, tag: str):
    m = re.search(rf"<{tag}>\s*([^<]+?)\s*</{tag}>", xml)
    return m.group(1).strip() if m else None


def get_project_artifact_id(pom_xml: str) -> str | None:
    """
    获取 <project> 的 artifactId（简单策略：取第一个不是 <parent> 块里的 artifactId）
    """
    parent_m = RE_PARENT_BLOCK.search(pom_xml)
    parent_span = parent_m.span(1) if parent_m else None

    for m in RE_ARTIFACT_ID.finditer(pom_xml):
        if parent_span and parent_span[0] <= m.start(0) <= parent_span[1]:
            continue
        return m.group(2).strip()
    return None


def get_packaging(pom_xml: str) -> str:
    m = RE_PACKAGING.search(pom_xml)
    return (m.group(1).strip() if m else "jar")


def set_project_artifact_id(pom_xml: str, new_artifact_id: str) -> str:
    """
    替换 <project> 的 artifactId（不改 parent 的 artifactId）
    """
    parent_m = RE_PARENT_BLOCK.search(pom_xml)
    parent_span = parent_m.span(1) if parent_m else None

    out = []
    last = 0
    replaced = False
    for m in RE_ARTIFACT_ID.finditer(pom_xml):
        if replaced:
            continue
        if parent_span and parent_span[0] <= m.start(0) <= parent_span[1]:
            continue
        out.append(pom_xml[last:m.start(2)])
        out.append(new_artifact_id)
        out.append(pom_xml[m.end(2):m.end(0)])
        last = m.end(0)
        replaced = True

    if not replaced:
        raise RuntimeError("No project <artifactId> found to replace.")
    out.append(pom_xml[last:])
    return "".join(out)


def ensure_parent_relativepath(pom_path: Path) -> bool:
    """
    若 parent 指向 root future，则补 <relativePath>（移动/新建模块后需要）[web:7]
    """
    txt = read_text(pom_path)
    m = RE_PARENT_BLOCK.search(txt)
    if not m:
        return False

    block = m.group(1)
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
    write_text(pom_path, new_txt)
    return True


def add_dependency_block(pom_xml: str, dep_xml: str) -> str:
    """
    把一个 <dependency>...</dependency> 块插入到第一个 <dependencies> 里。
    如果没有 <dependencies>，则创建一个。
    """
    if "<dependencies>" in pom_xml and "</dependencies>" in pom_xml:
        return re.sub(r"</dependencies>", f"{dep_xml}\n    </dependencies>", pom_xml, count=1)

    # 没有 dependencies 的情况：加在 </description> 后面或 </url> 后面，找不到就加在 </name> 后面
    insert_after_tags = ["</description>", "</url>", "</name>"]
    for t in insert_after_tags:
        if t in pom_xml:
            return pom_xml.replace(t, f"{t}\n\n    <dependencies>\n{dep_xml}\n    </dependencies>", 1)

    # 兜底：加在 <packaging> 后
    return re.sub(r"</packaging>", "</packaging>\n\n    <dependencies>\n" + dep_xml + "\n    </dependencies>", pom_xml, count=1)


def replace_dependency_artifact_ids(pom_xml: str, mapping: dict[str, str]) -> str:
    """
    只替换 <dependency>...<artifactId>xxx</artifactId>... 里的 artifactId。
    """
    def repl_dep_block(block: str) -> str:
        def repl_aid(m):
            aid = m.group(2).strip()
            if aid in mapping:
                return m.group(1) + mapping[aid] + m.group(3)
            return m.group(0)

        return RE_ARTIFACT_ID.sub(repl_aid, block)

    # 粗略按 dependency 块切片替换（避免误伤 project artifactId）
    parts = []
    idx = 0
    while True:
        s = pom_xml.find("<dependency>", idx)
        if s == -1:
            parts.append(pom_xml[idx:])
            break
        e = pom_xml.find("</dependency>", s)
        if e == -1:
            parts.append(pom_xml[idx:])
            break
        e2 = e + len("</dependency>")
        parts.append(pom_xml[idx:s])
        parts.append(repl_dep_block(pom_xml[s:e2]))
        idx = e2
    return "".join(parts)


def patch_modules_entries(pom_xml: str, dir_name_to_split: set[str]) -> str:
    """
    把 <module>future-module-xxx</module> 改成两行：
      <module>future-module-xxx-api</module>
      <module>future-module-xxx-biz</module>
    仅对“模块路径的最后一段目录名”在 dir_name_to_split 中的条目生效。
    """
    def repl(m):
        indent = m.group(1)
        mod = m.group(2).strip()
        last = mod.split("/")[-1]
        if last not in dir_name_to_split:
            return m.group(0)
        # 保持原来路径前缀不变
        prefix = "/".join(mod.split("/")[:-1])
        if prefix:
            api_path = f"{prefix}/{last}-api"
            biz_path = f"{prefix}/{last}-biz"
        else:
            api_path = f"{last}-api"
            biz_path = f"{last}-biz"
        return f"{indent}<module>{api_path}</module>\n{indent}<module>{biz_path}</module>"

    return RE_MODULE_LINE.sub(repl, pom_xml)


# -------------------------
# 拆分逻辑
# -------------------------
def discover_split_targets(repo_root: Path) -> list[Path]:
    """
    找到需要拆分的“叶子模块”目录：
    - artifactId 以 future-module- 开头
    - 非 -api/-biz
    - packaging 不是 pom（尽量只拆 jar 模块）
    - 存在 src/main/java（否则多半是父聚合 pom）
    """
    targets = []
    for pom in repo_root.rglob("pom.xml"):
        if is_root_pom(pom):
            continue
        txt = read_text(pom)
        aid = get_project_artifact_id(txt)
        if not aid:
            continue
        if not aid.startswith(MODULE_PREFIX):
            continue
        if aid.endswith(SKIP_SUFFIXES):
            continue
        if get_packaging(txt) == "pom":
            continue
        module_dir = pom.parent
        if not (module_dir / "src" / "main" / "java").exists():
            continue
        targets.append(module_dir)

    # 去重（同目录只一次）
    uniq = []
    seen = set()
    for d in targets:
        rp = str(d.resolve())
        if rp not in seen:
            seen.add(rp)
            uniq.append(d)
    return uniq


def move_api_packages(biz_dir: Path, api_dir: Path):
    """
    把 biz/src/main/java/**/api/** 移到 api/src/main/java/**/api/**（保留目录结构）
    只搬 “目录名为 api” 的包根，例如 cn/.../module/system/api/...
    """
    biz_java = biz_dir / "src" / "main" / "java"
    if not biz_java.exists():
        return 0

    moved = 0
    for api_pkg_dir in biz_java.rglob("api"):
        if not api_pkg_dir.is_dir():
            continue
        # 必须是 .../src/main/java/**/api（避免误伤其他路径）
        try:
            rel = api_pkg_dir.relative_to(biz_java)
        except ValueError:
            continue

        dst = api_dir / "src" / "main" / "java" / rel
        ensure_dir(dst.parent)

        # 如果目标已存在，跳过（防止重复运行）
        if dst.exists():
            continue

        shutil.move(str(api_pkg_dir), str(dst))
        moved += 1

    return moved


def split_one_module(module_dir: Path) -> tuple[str, str, str]:
    """
    把 module_dir（artifactId=base）拆为：
      sibling base-api/
      sibling base-biz/  (原目录重命名)
    返回 (base, api_aid, biz_aid)
    """
    pom_path = module_dir / "pom.xml"
    pom_xml = read_text(pom_path)

    base_aid = get_project_artifact_id(pom_xml)
    if not base_aid:
        raise RuntimeError(f"artifactId not found in {pom_path}")

    if not base_aid.startswith(MODULE_PREFIX) or base_aid.endswith(SKIP_SUFFIXES):
        raise RuntimeError(f"Not splittable module artifactId={base_aid} @ {pom_path}")

    api_aid = base_aid + "-api"
    biz_aid = base_aid + "-biz"

    parent_dir = module_dir.parent
    api_dir = parent_dir / f"{module_dir.name}-api"
    biz_dir = parent_dir / f"{module_dir.name}-biz"

    # 已经拆过：直接跳过
    if api_dir.exists() and biz_dir.exists():
        print(f"ℹ️  already split, skip: {module_dir}")
        return base_aid, api_aid, biz_aid

    # 1) 先把原目录改名成 biz
    if biz_dir.exists():
        raise RuntimeError(f"biz dir already exists unexpectedly: {biz_dir}")
    shutil.move(str(module_dir), str(biz_dir))
    print(f"✅ rename to biz: {module_dir} -> {biz_dir}")

    # 2) 创建 api 目录与 pom
    ensure_dir(api_dir)
    api_pom_xml = pom_xml
    api_pom_xml = set_project_artifact_id(api_pom_xml, api_aid)
    write_text(api_dir / "pom.xml", api_pom_xml)
    print(f"✅ created api pom: {api_dir/'pom.xml'}")

    # 3) 修改 biz 的 artifactId，并追加依赖 api
    biz_pom_path = biz_dir / "pom.xml"
    biz_pom_xml = read_text(biz_pom_path)
    biz_pom_xml = set_project_artifact_id(biz_pom_xml, biz_aid)

    dep_xml = f"""        <dependency>
            <groupId>{ROOT_GROUP_ID}</groupId>
            <artifactId>{api_aid}</artifactId>
            <version>${{revision}}</version>
        </dependency>"""

    biz_pom_xml = add_dependency_block(biz_pom_xml, dep_xml)
    write_text(biz_pom_path, biz_pom_xml)
    print(f"✅ patched biz pom: {biz_pom_path}")

    # 4) 可选：搬运 api 包
    if MOVE_API_PACKAGES:
        moved_cnt = move_api_packages(biz_dir, api_dir)
        if moved_cnt > 0:
            print(f"✅ moved api package roots: {moved_cnt} (from {biz_dir.name} -> {api_dir.name})")

    # 5) parent relativePath 补齐（新 pom 需要）
    ensure_parent_relativepath(api_dir / "pom.xml")
    ensure_parent_relativepath(biz_dir / "pom.xml")

    return base_aid, api_aid, biz_aid


def main():
    repo_root = Path(".")
    if not ROOT_POM.exists():
        raise RuntimeError("❌ Run this script at repo root (pom.xml not found).")

    targets = discover_split_targets(repo_root)
    if not targets:
        print("ℹ️  no split targets found.")
        return

    # 先拆分，收集映射：base -> base-biz（用于全局替换依赖引用）
    base_to_biz = {}
    dir_names_to_split = set()  # 用于替换 <modules> 里的 module 路径（按目录名匹配）

    for d in sorted(targets):
        pom_xml = read_text(d / "pom.xml")
        base_aid = get_project_artifact_id(pom_xml)
        if not base_aid:
            continue

        base, api_aid, biz_aid = split_one_module(d)
        base_to_biz[base] = biz_aid
        # module 路径通常就是目录名（future-module-xxx）
        dir_names_to_split.add(d.name)

    # 现在 repo 中已经出现了 *-api / *-biz 目录，但父聚合 POM 的 <modules> 还是旧的，需要修正；
    # 同时所有依赖引用 future-module-xxx 也要改为 future-module-xxx-biz，保证构建不改业务语义
    patched_poms = 0
    for pom in repo_root.rglob("pom.xml"):
        if not pom.is_file():
            continue
        txt = read_text(pom)
        new_txt = txt

        # 1) 修正 <modules> 聚合路径（future-module-xxx -> future-module-xxx-api + future-module-xxx-biz）
        new_txt = patch_modules_entries(new_txt, dir_names_to_split)

        # 2) 修正 <dependency> 中的 artifactId（future-module-xxx -> future-module-xxx-biz）
        new_txt = replace_dependency_artifact_ids(new_txt, base_to_biz)

        if new_txt != txt:
            write_text(pom, new_txt)
            patched_poms += 1

    print(f"🎉 done. split_count={len(base_to_biz)}, patched_poms={patched_poms}")


if __name__ == "__main__":
    main()
