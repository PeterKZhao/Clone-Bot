#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
from pathlib import Path

ROOT_GROUP_ID = "cn.iocoder.boot"
MODULE_PREFIX = "future-module-"
SKIP_SUFFIXES = ("-api", "-biz")

# 不拆分 api/biz 的模块（保持原始单模块结构）
SKIP_MODULES = {
    "future-module-infra",
    "future-module-system",
}

# 除 api/ 目录外，额外需要整体迁移到 -api 模块的顶层包名
# 这些包通常是 API 契约的一部分（接口入参枚举、常量等），-api 模块编译时需要
EXTRA_API_PACKAGES = {
    "enums",
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
    parent_m = RE_PARENT_BLOCK.search(pom_xml)
    parent_span = parent_m.span(1) if parent_m else None

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
        if k[0] == (gid or ROOT_GROUP_ID) and k[1] == aid:
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


# ---------- 代码迁移 ----------
def _migrate_files_no_impl(src_dir: Path, dst_dir: Path) -> int:
    """
    将 src_dir 下所有非 *Impl.java 文件复制到 dst_dir 对应路径并删除原文件。
    *Impl.java 留在 src_dir（依赖 service 层，必须留在 biz）。
    返回迁移文件数。
    """
    moved = 0
    for src_file in list(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        if src_file.name.endswith("Impl.java"):
            continue
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        if dst_file.exists():
            continue
        ensure_dir(dst_file.parent)
        shutil.copy2(str(src_file), str(dst_file))
        src_file.unlink()
        moved += 1
    return moved


def _cleanup_empty_dirs(root: Path):
    """从最深层向上删除空目录。"""
    for d in sorted(root.rglob("*"), key=lambda p: -len(p.parts)):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    if root.exists() and not any(root.iterdir()):
        root.rmdir()


def move_api_packages(biz_dir: Path, api_dir: Path) -> int:
    """
    将 biz 模块 src/main/java 下需要迁移到 -api 模块的包搬走：

    1. 名为 api 的包目录：
       - 非 *Impl.java 文件 → 迁移到 api 模块
       - *Impl.java          → 留在 biz（引用 service 层）

    2. EXTRA_API_PACKAGES 中的顶层包（默认含 enums）：
       - 整包迁移到 api 模块（这些包是 API 契约的一部分，
         接口定义文件会 import 它们，-api 模块编译时必须可见）
    """
    biz_java = biz_dir / "src" / "main" / "java"
    if not biz_java.exists():
        return 0

    total_moved = 0

    # 1) 迁移 api/ 包（跳过 *Impl.java）
    for api_pkg_dir in list(biz_java.rglob("api")):
        if not api_pkg_dir.is_dir():
            continue
        try:
            rel = api_pkg_dir.relative_to(biz_java)
        except ValueError:
            continue
        dst_pkg_dir = api_dir / "src" / "main" / "java" / rel
        total_moved += _migrate_files_no_impl(api_pkg_dir, dst_pkg_dir)
        _cleanup_empty_dirs(api_pkg_dir)

    # 2) 迁移 EXTRA_API_PACKAGES（enums 等），整包搬走
    for pkg_name in EXTRA_API_PACKAGES:
        for extra_pkg_dir in list(biz_java.rglob(pkg_name)):
            if not extra_pkg_dir.is_dir():
                continue
            # 只处理直接挂在模块顶层包下的 enums/（避免误迁移嵌套同名目录）
            # 判断：extra_pkg_dir 的父目录不能也叫 enums
            if extra_pkg_dir.parent.name == pkg_name:
                continue
            try:
                rel = extra_pkg_dir.relative_to(biz_java)
            except ValueError:
                continue
            dst_pkg_dir = api_dir / "src" / "main" / "java" / rel
            if dst_pkg_dir.exists():
                # 目标已存在则逐文件合并，不整体覆盖
                total_moved += _migrate_files_no_impl(extra_pkg_dir, dst_pkg_dir)
                _cleanup_empty_dirs(extra_pkg_dir)
            else:
                ensure_dir(dst_pkg_dir.parent)
                shutil.move(str(extra_pkg_dir), str(dst_pkg_dir))
                total_moved += sum(1 for _ in dst_pkg_dir.rglob("*") if _.is_file())

    return total_moved


# ---------- 拆分核心 ----------
def discover_base_modules(repo_root: Path) -> list[Path]:
    """
    找到需要拆分的 base 模块：
    - artifactId 以 future-module- 开头
    - 不以 -api / -biz 结尾
    - 不在 SKIP_MODULES 白名单中
    - packaging != pom
    - 存在 src/main/java
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
        if aid in SKIP_MODULES:
            print(f"ℹ️  skip (SKIP_MODULES): {aid}")
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


def sibling_api_module_dir(base_dir: Path, base_aid: str) -> Path | None:
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

    if api_aid:
        biz_xml = add_dep_if_missing(biz_xml, ROOT_GROUP_ID, api_aid)

    biz_xml = remove_self_and_dedupe_deps(biz_xml)
    write_text(biz_pom, biz_xml)


def patch_all_modules_and_deps(repo_root: Path, base_to_biz: dict[str, str], base_has_api: dict[str, bool]):
    for pom in repo_root.rglob("pom.xml"):
        xml = read_text(pom)
        original = xml

        lines = xml.splitlines(True)
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
                prefix = "/".join(mod_path.split("/")[:-1])
                biz_path = f"{prefix}/{biz_name}" if prefix else biz_name
                api_path = f"{prefix}/{api_name}" if prefix else api_name

                if base_has_api.get(base, False):
                    if api_path in existing_module_paths:
                        out.append(f"{indent}<module>{biz_path}</module>\n")
                    else:
                        out.append(f"{indent}<module>{api_path}</module>\n")
                        out.append(f"{indent}<module>{biz_path}</module>\n")
                else:
                    out.append(f"{indent}<module>{biz_path}</module>\n")
                continue

            out.append(line)

        xml = "".join(out)
        xml = dedupe_modules(xml)

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
        xml = remove_self_and_dedupe_deps(xml)

        if xml != original:
            write_text(pom, xml)


# ---------- mall/trade 聚合目录 ----------
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


def patch_trade_module_relative_path(trade_dir: Path, mall_dir: Path):
    """
    trade-api / trade-biz 移入 trade/ 子目录后，将 <relativePath> 修正为
    ../../pom.xml，指向 future-module-mall/pom.xml。
    """
    for mod_name in ("future-module-trade-api", "future-module-trade-biz"):
        mod_pom_path = trade_dir / mod_name / "pom.xml"
        if not mod_pom_path.exists():
            continue

        xml = read_text(mod_pom_path)
        parent_m = RE_PARENT_BLOCK.search(xml)
        if not parent_m:
            continue

        block = parent_m.group(1)

        correct_rp = os.path.relpath(
            mall_dir.resolve() / "pom.xml",
            (trade_dir / mod_name).resolve(),
        ).replace("\\", "/")

        if "<relativePath>" in block:
            new_block = re.sub(
                r"<relativePath>[^<]*</relativePath>",
                f"<relativePath>{correct_rp}</relativePath>",
                block,
            )
        else:
            indent_m = re.search(r"\n(\s*)<artifactId>", block)
            indent = indent_m.group(1) if indent_m else "        "
            new_block = block.replace(
                "</parent>",
                f"\n{indent}<relativePath>{correct_rp}</relativePath>\n{indent}</parent>",
            )

        xml = xml[: parent_m.start(1)] + new_block + xml[parent_m.end(1):]
        write_text(mod_pom_path, xml)
        print(f"✅ patched relativePath ({correct_rp}): {mod_pom_path}")


def group_mall_trade(repo_root: Path):
    for mall_pom in repo_root.rglob("future-module-mall/pom.xml"):
        mall_dir = mall_pom.parent
        api_dir = mall_dir / "future-module-trade-api"
        biz_dir = mall_dir / "future-module-trade-biz"
        if not api_dir.exists() or not biz_dir.exists():
            continue

        trade_dir = mall_dir / "trade"
        if (
            (trade_dir / "future-module-trade-api").exists()
            and (trade_dir / "future-module-trade-biz").exists()
        ):
            continue

        ensure_dir(trade_dir)

        shutil.move(str(api_dir), str(trade_dir / "future-module-trade-api"))
        shutil.move(str(biz_dir), str(trade_dir / "future-module-trade-biz"))

        rel_parent = os.path.relpath(
            (repo_root / "pom.xml").resolve(), trade_dir.resolve()
        ).replace("\\", "/")
        write_trade_aggregator(trade_dir, rel_parent)

        # 修正 api/biz 的 <relativePath>，指向 future-module-mall
        patch_trade_module_relative_path(trade_dir, mall_dir)

        # patch mall pom：移除 trade-api / trade-biz 行，加入 trade 聚合
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
        if "<module>trade</module>" not in xml2:
            xml2 = re.sub(
                r"</modules>",
                "        <module>trade</module>\n    </modules>",
                xml2,
                count=1,
            )
        xml2 = dedupe_modules(xml2)
        write_text(mall_pom, xml2)


def main():
    repo_root = Path(".")

    base_dirs = discover_base_modules(repo_root)
    if not base_dirs:
        print("ℹ️ no base modules to split.")
        return

    base_to_biz: dict[str, str] = {}
    base_has_api: dict[str, bool] = {}

    for base_dir in base_dirs:
        base_pom = base_dir / "pom.xml"
        base_xml = read_text(base_pom)
        _, base_aid = get_project_ga(base_xml)
        if not base_aid:
            continue

        api_aid = base_aid + "-api"
        biz_aid = base_aid + "-biz"

        existing_api_dir = sibling_api_module_dir(base_dir, base_aid)
        api_dir = base_dir.parent / (base_dir.name + "-api")
        biz_dir = base_dir.parent / (base_dir.name + "-biz")

        if existing_api_dir is not None:
            base_has_api[base_aid] = True
            rename_to_biz(base_dir, biz_dir, base_aid, biz_aid, api_aid)
        else:
            base_has_api[base_aid] = True
            create_api_module_from_base(
                base_pom_xml=base_xml,
                api_dir=api_dir,
                api_aid=api_aid,
                remove_aids={api_aid},
            )
            rename_to_biz(base_dir, biz_dir, base_aid, biz_aid, api_aid)

            if MOVE_API_PACKAGES:
                moved = move_api_packages(biz_dir, api_dir)
                if moved:
                    print(f"✅ moved api/enums files: {moved} ({biz_dir.name} -> {api_dir.name})")

        base_to_biz[base_aid] = biz_aid

    patch_all_modules_and_deps(repo_root, base_to_biz, base_has_api)

    if GROUP_MALL_TRADE_FOLDER:
        group_mall_trade(repo_root)

    print("🎉 split_api_biz done.")


if __name__ == "__main__":
    main()
