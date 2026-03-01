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
RE_TAG = lambda t: re.compile(rf"<{t}>\s*([^<]+?)\s*</{t}>")
RE_ARTIFACT = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>")
RE_GROUP = re.compile(r"<groupId>\s*([^<]+?)\s*</groupId>")
RE_MODULE_LINE = re.compile(r"^(\s*)<module>\s*([^<]+?)\s*</module>\s*$", re.MULTILINE)
RE_DEP_BLOCK = re.compile(r"<dependency>\s*.*?</dependency>", re.DOTALL)

RE_DEP_G = re.compile(r"<groupId>\s*([^<]+?)\s*</groupId>")
RE_DEP_A = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>")
RE_DEP_T = re.compile(r"<type>\s*([^<]+?)\s*</type>")
RE_DEP_C = re.compile(r"<classifier>\s*([^<]+?)\s*</classifier>")


def get_project_ga(pom_xml: str):
    """
    返回 (groupId, artifactId)；artifactId 取 project 的，不取 parent 的
    """
    parent_m = RE_PARENT_BLOCK.search(pom_xml)
    parent_span = parent_m.span(1) if parent_m else None

    # groupId：project 里可能没有（继承 parent），这里不强依赖
    gid = None
    for m in re.finditer(r"<groupId>\s*([^<]+?)\s*</groupId>", pom_xml):
        if parent_span and parent_span[0] <= m.start(0) <= parent_span[1]:
            continue
        gid = m.group(1).strip()
        break

    aid = None
    for m in RE_ARTIFACT.finditer(pom_xml):
        if parent_span and parent_span[0] <= m.start(0) <= parent_span[1]:
            continue
        aid = m.group(1).strip()
        break

    return gid, aid


def set_project_artifact_id(pom_xml: str, new_aid: str) -> str:
    parent_m = RE_PARENT_BLOCK.search(pom_xml)
    parent_span = parent_m.span(1) if parent_m else None

    out = []
    last = 0
    replaced = False
    for m in RE_ARTIFACT.finditer(pom_xml):
        if replaced:
            continue
        if parent_span and parent_span[0] <= m.start(0) <= parent_span[1]:
            continue
        out.append(pom_xml[last:m.start(1)])
        out.append(new_aid)
        out.append(pom_xml[m.end(1):])
        last = len(pom_xml)
        replaced = True
        break

    if not replaced:
        raise RuntimeError("No project <artifactId> found to replace.")
    return "".join(out)


def has_packaging_pom(pom_xml: str) -> bool:
    m = re.search(r"<packaging>\s*([^<]+?)\s*</packaging>", pom_xml)
    return (m and m.group(1).strip() == "pom")


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
    gid = (RE_DEP_G.search(dep_xml).group(1).strip() if RE_DEP_G.search(dep_xml) else "")
    aid = (RE_DEP_A.search(dep_xml).group(1).strip() if RE_DEP_A.search(dep_xml) else "")
    typ = (RE_DEP_T.search(dep_xml).group(1).strip() if RE_DEP_T.search(dep_xml) else "jar")
    cls = (RE_DEP_C.search(dep_xml).group(1).strip() if RE_DEP_C.search(dep_xml) else "")
    return (gid, aid, typ, cls)


def remove_self_and_dedupe_deps(pom_xml: str) -> str:
    gid, aid = get_project_ga(pom_xml)
    if not aid:
        return pom_xml

    seen = set()
    def repl(m):
        dep = m.group(0)
        k = dep_key(dep)

        # 去掉“依赖自己”（你现在的 FATAL）
        if k[0] == (gid or ROOT_GROUP_ID) and k[1] == aid:
            return ""

        # 去重（你现在的 warning）
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

    # 没有 dependencies：尽量插在 </description> 后，否则插在 </name> 后，兜底插在 </packaging> 后
    for anchor in ["</description>", "</url>", "</name>", "</packaging>"]:
        if anchor in pom_xml:
            return pom_xml.replace(anchor, anchor + "\n\n    <dependencies>\n" + dep_xml + "    </dependencies>", 1)

    return pom_xml + "\n    <dependencies>\n" + dep_xml + "    </dependencies>\n"


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
    找到需要拆分的“base 模块目录”：artifactId=future-module-xxx（非 -api/-biz），且是 jar 模块（packaging!=pom）
    """
    targets = []
    for pom in repo_root.rglob("pom.xml"):
        if pom.resolve() == (repo_root / "pom.xml").resolve():
            continue
        xml = read_text(pom)
        gid, aid = get_project_ga(xml)
        if not aid:
            continue
        if not aid.startswith(MODULE_PREFIX):
            continue
        if aid.endswith(SKIP_SUFFIXES):
            continue
        if has_packaging_pom(xml):
            continue
        # 基本认为有 Java 代码的才拆
        if not (pom.parent / "src" / "main" / "java").exists():
            continue
        targets.append(pom.parent)
    # 去重
    uniq, seen = [], set()
    for d in targets:
        rp = str(d.resolve())
        if rp not in seen:
            uniq.append(d)
            seen.add(rp)
    return sorted(uniq)


def sibling_api_module_dir(base_dir: Path, base_aid: str) -> Path | None:
    """
    只认“同级目录”的既有 api 模块（解决 trade 这种情况）
    """
    api_dir = base_dir.parent / (base_dir.name + "-api")
    api_pom = api_dir / "pom.xml"
    if not api_pom.exists():
        return None
    api_xml = read_text(api_pom)
    _, api_aid = get_project_ga(api_xml)
    if api_aid == base_aid + "-api":
        return api_dir
    return None


def create_api_module_from_base(base_pom_xml: str, api_dir: Path, api_aid: str, remove_aids: set[str]):
    ensure_dir(api_dir)

    api_xml = set_project_artifact_id(base_pom_xml, api_aid)

    # 关键：删除“指向 api_aid 的依赖”，避免自引用（trade 就是这里炸）
    def drop_dep_block(m):
        dep = m.group(0)
        am = RE_DEP_A.search(dep)
        gm = RE_DEP_G.search(dep)
        if not am:
            return dep
        gid = (gm.group(1).strip() if gm else "")
        aid = am.group(1).strip()
        if gid == ROOT_GROUP_ID and aid in remove_aids:
            return ""
        return dep

    api_xml = RE_DEP_BLOCK.sub(drop_dep_block, api_xml)
    api_xml = remove_self_and_dedupe_deps(api_xml)

    write_text(api_dir / "pom.xml", api_xml)


def rename_to_biz(base_dir: Path, biz_dir: Path, base_aid: str, biz_aid: str, api_aid: str | None):
    if biz_dir.exists():
        raise RuntimeError(f"biz dir already exists: {biz_dir}")

    shutil.move(str(base_dir), str(biz_dir))

    biz_pom = biz_dir / "pom.xml"
    biz_xml = read_text(biz_pom)
    biz_xml = set_project_artifact_id(biz_xml, biz_aid)

    # biz 依赖 api（如果 api_aid 给了，就补；并且不重复添加）
    if api_aid:
        biz_xml = add_dep_if_missing(biz_xml, ROOT_GROUP_ID, api_aid)

    biz_xml = remove_self_and_dedupe_deps(biz_xml)
    write_text(biz_pom, biz_xml)


def patch_all_modules_and_deps(repo_root: Path, base_to_biz: dict[str, str], base_has_api: dict[str, bool]):
    """
    - <modules> 中 base -> (api + biz) 或 base->biz（若 api 已经单独存在并且 modules 里已包含）
    - <dependency> 中 base -> biz（满足你“所有模块引用都应是 -biz”）
    - 去重 modules / deps，去掉自引用 dep
    """
    for pom in repo_root.rglob("pom.xml"):
        xml = read_text(pom)
        original = xml

        # 1) patch modules：逐行处理，遇到 base 模块就替换
        lines = xml.splitlines(True)
        # 预扫描当前 pom 已有的 module 路径（用于判断是否已经包含 api）
        existing_module_paths = set()
        for m in RE_MODULE_LINE.finditer(xml):
            existing_module_paths.add(m.group(2).strip())

        out = []
        for line in lines:
            mm = RE_MODULE_LINE.match(line.rstrip("\n"))
            if not mm:
                out.append(line)
                continue

            indent, mod_path = mm.group(1), mm.group(2).strip()
            last = mod_path.split("/")[-1]

            if last in base_to_biz:
                base = last
                biz_name = base + "-biz"
                api_name = base + "-api"
                # 原路径前缀保持
                prefix = "/".join(mod_path.split("/")[:-1])
                biz_path = f"{prefix}/{biz_name}" if prefix else biz_name
                api_path = f"{prefix}/{api_name}" if prefix else api_name

                if base_has_api.get(base, False):
                    # 如果同一个 pom 已经有 api module 行，就只把 base 替换成 biz
                    if api_path in existing_module_paths:
                        out.append(f"{indent}<module>{biz_path}</module>\n")
                    else:
                        out.append(f"{indent}<module>{api_path}</module>\n")
                        out.append(f"{indent}<module>{biz_path}</module>\n")
                else:
                    # 没有 api（理论上不会发生，因为我们创建了）
                    out.append(f"{indent}<module>{biz_path}</module>\n")
                continue

            out.append(line)

        xml = "".join(out)
        xml = dedupe_modules(xml)

        # 2) patch dependencies：base -> base-biz（groupId 必须是 cn.iocoder.boot）
        def rewrite_dep(dep_xml: str) -> str:
            gm = RE_DEP_G.search(dep_xml)
            am = RE_DEP_A.search(dep_xml)
            if not gm or not am:
                return dep_xml
            gid = gm.group(1).strip()
            aid = am.group(1).strip()
            if gid != ROOT_GROUP_ID:
                return dep_xml
            if aid in base_to_biz:
                new_aid = base_to_biz[aid]
                return RE_DEP_A.sub(f"<artifactId>{new_aid}</artifactId>", dep_xml, count=1)
            return dep_xml

        xml = RE_DEP_BLOCK.sub(lambda m: rewrite_dep(m.group(0)), xml)

        # 3) 最后：清理自引用与重复依赖
        xml = remove_self_and_dedupe_deps(xml)

        if xml != original:
            write_text(pom, xml)


# ---------- 可选：mall/trade 聚合目录 ----------
def write_trade_aggregator(trade_dir: Path, relative_parent: str):
    ensure_dir(trade_dir)
    pom = trade_dir / "pom.xml"
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>{ROOT_GROUP_ID}</groupId>
        <artifactId>future</artifactId>
        <version>${{revision}}</version>
        <relativePath>{relative_parent}</relativePath>
    </parent>

    <artifactId>future-mall-trade</artifactId>
    <packaging>pom</packaging>

    <modules>
        <module>future-module-trade-api</module>
        <module>future-module-trade-biz</module>
    </modules>
</project>
"""
    write_text(pom, content)


def group_mall_trade(repo_root: Path):
    """
    在 future-module-mall 目录下，把：
      future-module-trade-api/
      future-module-trade-biz/
    归到 trade/ 目录，并把 future-module-mall/pom.xml 的 modules 改成引用 trade。
    """
    for mall_pom in repo_root.rglob("future-module-mall/pom.xml"):
        mall_dir = mall_pom.parent
        api_dir = mall_dir / "future-module-trade-api"
        biz_dir = mall_dir / "future-module-trade-biz"
        if not api_dir.exists() or not biz_dir.exists():
            continue

        trade_dir = mall_dir / "trade"
        if (trade_dir / "future-module-trade-api").exists() and (trade_dir / "future-module-trade-biz").exists():
            # 已经归过类
            continue

        ensure_dir(trade_dir)

        shutil.move(str(api_dir), str(trade_dir / "future-module-trade-api"))
        shutil.move(str(biz_dir), str(trade_dir / "future-module-trade-biz"))

        # 写 trade 聚合 pom（relativePath 指回 repo root；这里计算一次）
        rel_parent = os.path.relpath((repo_root / "pom.xml").resolve(), trade_dir.resolve()).replace("\\", "/")
        write_trade_aggregator(trade_dir, rel_parent)

        # patch mall modules：删 trade-api 与 trade-biz，加入 trade
        xml = read_text(mall_pom)
        lines = xml.splitlines(True)
        out = []
        for line in lines:
            m = RE_MODULE_LINE.match(line.rstrip("\n"))
            if not m:
                out.append(line)
                continue
            mod = m.group(2).strip()
            if mod in ("future-module-trade-api", "future-module-trade-biz"):
                continue
            out.append(line)

        xml2 = "".join(out)

        # 在 </modules> 前插入 trade（如果不存在）
        if "<module>trade</module>" not in xml2:
            xml2 = re.sub(r"</modules>", "        <module>trade</module>\n    </modules>", xml2, count=1)

        xml2 = dedupe_modules(xml2)
        write_text(mall_pom, xml2)


def main():
    repo_root = Path(".")

    base_dirs = discover_base_modules(repo_root)
    if not base_dirs:
        print("ℹ️ no base modules to split.")
        return

    base_to_biz = {}      # base_aid -> base_aid-biz
    base_has_api = {}     # base_aid -> bool（同级已存在 api 或我们创建了）

    for base_dir in base_dirs:
        base_pom = base_dir / "pom.xml"
        base_xml = read_text(base_pom)
        _, base_aid = get_project_ga(base_xml)
        if not base_aid:
            continue

        api_aid = base_aid + "-api"
        biz_aid = base_aid + "-biz"

        # 若同级已存在 api（trade 的情况），直接用它；否则我们创建一个 api 目录
        existing_api_dir = sibling_api_module_dir(base_dir, base_aid)
        api_dir = base_dir.parent / (base_dir.name + "-api")
        biz_dir = base_dir.parent / (base_dir.name + "-biz")

        if existing_api_dir is not None:
            base_has_api[base_aid] = True
            # 不创建 api，只重命名 base -> biz
            rename_to_biz(base_dir, biz_dir, base_aid, biz_aid, api_aid)
        else:
            base_has_api[base_aid] = True
            # 先创建 api（从 base pom 复制，但会删除“依赖 api_aid”的依赖，防止自引用）
            create_api_module_from_base(
                base_pom_xml=base_xml,
                api_dir=api_dir,
                api_aid=api_aid,
                remove_aids={api_aid}
            )

            # base -> biz，并依赖 api
            rename_to_biz(base_dir, biz_dir, base_aid, biz_aid, api_aid)

            # 可选搬运 api 包
            if MOVE_API_PACKAGES:
                moved = move_api_packages(biz_dir, api_dir)
                if moved:
                    print(f"✅ moved api package roots: {moved} ({biz_dir.name} -> {api_dir.name})")

        base_to_biz[base_aid] = biz_aid

    # 全局修补：modules 与 dependencies 统一指向 -biz，并去重/去自引用
    patch_all_modules_and_deps(repo_root, base_to_biz, base_has_api)

    # 可选：把 mall 的 trade-api + trade-biz 放进 trade/ 聚合目录（更符合你说的“新的 trade 下”）
    if GROUP_MALL_TRADE_FOLDER:
        group_mall_trade(repo_root)

    print("🎉 split_api_biz_v2 done.")


if __name__ == "__main__":
    main()
