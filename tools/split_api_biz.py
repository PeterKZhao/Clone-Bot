#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
from pathlib import Path

ROOT_GROUP_ID = "cn.iocoder.boot"
MODULE_PREFIX = "future-module-"
SKIP_SUFFIXES = ("-api", "-biz")

# 是否把 biz/src/main/java/**/api/** 迁移到 api 模块
MOVE_API_PACKAGES = True

# 是否对 mall 的 trade 做“trade/ 目录聚合”（可选；不影响编译，只是更像你设计的结构）
GROUP_MALL_TRADE_FOLDER = True


# ---------- 通用读写 ----------
def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_text(p: Path, s: str):
    p.write_text(s, encoding="utf-8")


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


# ---------- 轻量 POM 处理（避免格式被洗） ----------
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
    """取 project 自身的 artifactId（不取 parent 的）"""
    pm = RE_PARENT_BLOCK.search(pom_xml)
    ps = pm.span(1) if pm else None
    for m in RE_ARTIFACT.finditer(pom_xml):
        if ps and ps[0] <= m.start(0) <= ps[1]:
            continue
        return m.group(1).strip()
    return None


def get_parent_ga(pom_xml: str) -> tuple[str | None, str | None]:
    """取 parent 的 (groupId, artifactId)"""
    pm = RE_PARENT_BLOCK.search(pom_xml)
    if not pm:
        return None, None
    block = pm.group(1)
    gm = RE_GROUP.search(block)
    am = RE_ARTIFACT.search(block)
    gid = gm.group(1).strip() if gm else None
    aid = am.group(1).strip() if am else None
    return gid, aid


def get_project_group_id_only(pom_xml: str) -> str | None:
    """取 project 自身的 groupId（不取 parent 的）；项目里可能没有"""
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
        out.append(pom_xml[last:m.start(1)])
        out.append(new_aid)
        out.append(pom_xml[m.end(1):])
        replaced = True
        return "".join(out)

    raise RuntimeError("No project <artifactId> found to replace.")


def has_packaging_pom(pom_xml: str) -> bool:
    m = RE_PACKAGING.search(pom_xml)
    return bool(m and m.group(1).strip() == "pom")


def dedupe_modules(xml: str) -> str:
    """同一个 pom.xml 内，去掉重复 <module> 行（保留第一次出现）"""
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
    gid = (RE_DEP_G.search(dep_xml).group(1).strip() if RE_DEP_G.search(dep_xml) else "")
    aid = (RE_DEP_A.search(dep_xml).group(1).strip() if RE_DEP_A.search(dep_xml) else "")
    typ = (RE_DEP_T.search(dep_xml).group(1).strip() if RE_DEP_T.search(dep_xml) else "jar")
    cls = (RE_DEP_C.search(dep_xml).group(1).strip() if RE_DEP_C.search(dep_xml) else "")
    return (gid, aid, typ, cls)


def remove_self_and_dedupe_deps(pom_xml: str) -> str:
    """
    - 去掉依赖自己（会导致 FATAL: referencing itself）
    - 去重重复依赖（警告依赖重复）
    """
    gid_proj = get_project_group_id_only(pom_xml) or ROOT_GROUP_ID
    aid_proj = get_project_artifact_id_only(pom_xml)
    if not aid_proj:
        return pom_xml

    seen = set()

    def repl(m):
        dep = m.group(0)
        k = dep_key(dep)

        # 自引用：groupId + artifactId 与自身一致
        if k[0] == gid_proj and k[1] == aid_proj:
            return ""

        # 去重
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

    # 没有 dependencies：尽量插在 </description> / </url> / </name> / </packaging> 后
    for anchor in ["</description>", "</url>", "</name>", "</packaging>"]:
        if anchor in pom_xml:
            return pom_xml.replace(anchor, anchor + "\n\n    <dependencies>\n" + dep_xml + "    </dependencies>", 1)

    return pom_xml + "\n    <dependencies>\n" + dep_xml + "    </dependencies>\n"


# ---------- parent.relativePath 自动修复 ----------
def find_parent_pom_by_artifact_id(start_dir: Path, parent_artifact_id: str) -> Path | None:
    """
    从 start_dir 往上找，找到某一级目录下的 pom.xml，其 project.artifactId == parent_artifact_id
    """
    cur = start_dir.resolve()
    while True:
        candidate = cur / "pom.xml"
        if candidate.exists():
            try:
                xml = read_text(candidate)
                aid = get_project_artifact_id_only(xml)
                if aid == parent_artifact_id:
                    return candidate
            except Exception:
                pass
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def ensure_parent_relativepath_auto(pom_path: Path):
    """
    给任何“parent 在本仓库上层目录存在”的模块，写正确 relativePath。
    重点解决：模块被移动到更深层后，默认 ../pom.xml 指到错误 POM 的问题。
    """
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
        new_block = block.replace("</parent>", f"\n{indent}<relativePath>{rel}</relativePath>\n{indent}</parent>")

    new_xml = xml[:pm.start(1)] + new_block + xml[pm.end(1):]
    if new_xml != xml:
        write_text(pom_path, new_xml)


# ---------- 代码迁移（可选） ----------
def move_api_packages(biz_dir: Path, api_dir: Path) -> int:
    biz_java = biz_dir / "src" / "main" / "java"
    if not biz_java.exists():
        return 0

    moved = 0
    for api_pkg_dir in biz_java.rglob("api"):
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
    找到需要拆分的“base 模块目录”：
    - project artifactId = future-module-xxx（非 -api/-biz）
    - packaging != pom
    - 有 src/main/java（基本认为是业务 jar）
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


def sibling_existing_api_dir(base_dir: Path, base_aid: str) -> Path | None:
    """
    同级已存在 api 模块（trade 的典型情况：future-module-trade + future-module-trade-api）
    """
    api_dir = base_dir.parent / (base_dir.name + "-api")
    api_pom = api_dir / "pom.xml"
    if not api_pom.exists():
        return None
    try:
        xml = read_text(api_pom)
        aid = get_project_artifact_id_only(xml)
        if aid == base_aid + "-api":
            return api_dir
    except Exception:
        return None
    return None


def create_api_module_from_base(base_pom_xml: str, api_dir: Path, api_aid: str):
    """
    新建 api 模块：拷贝 base pom，改 artifactId，并删除“依赖 api_aid”的 dependency，避免自引用。
    目录只写 pom.xml（代码通过 MOVE_API_PACKAGES 决定是否迁移）。
    """
    ensure_dir(api_dir)
    api_xml = set_project_artifact_id(base_pom_xml, api_aid)

    # 删除 dependency 中 artifactId == api_aid（复制 trade 时会变成自引用）
    def drop_dep(m):
        dep = m.group(0)
        gm = RE_DEP_G.search(dep)
        am = RE_DEP_A.search(dep)
        if not am:
            return dep
        gid = gm.group(1).strip() if gm else ""
        aid = am.group(1).strip()
        if gid == ROOT_GROUP_ID and aid == api_aid:
            return ""
        return dep

    api_xml = RE_DEP_BLOCK.sub(drop_dep, api_xml)
    api_xml = remove_self_and_dedupe_deps(api_xml)

    write_text(api_dir / "pom.xml", api_xml)
    ensure_parent_relativepath_auto(api_dir / "pom.xml")


def rename_base_to_biz(base_dir: Path, biz_dir: Path, biz_aid: str, api_aid: str | None):
    if biz_dir.exists():
        # 幂等：如果已经存在 biz_dir，就不再重复操作
        return

    shutil.move(str(base_dir), str(biz_dir))
    biz_pom = biz_dir / "pom.xml"
    biz_xml = read_text(biz_pom)
    biz_xml = set_project_artifact_id(biz_xml, biz_aid)

    if api_aid:
        biz_xml = add_dep_if_missing(biz_xml, ROOT_GROUP_ID, api_aid)

    biz_xml = remove_self_and_dedupe_deps(biz_xml)
