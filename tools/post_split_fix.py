#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from pathlib import Path

ROOT_GROUP_ID = "cn.iocoder.boot"
MODULE_PREFIX = "future-module-"

SKIP_SUFFIXES = ("-api", "-biz")

RE_MODULE_LINE = re.compile(r"^(\s*)<module>\s*([^<]+?)\s*</module>\s*$")
RE_DEP_BLOCK = re.compile(r"<dependency>\s*.*?</dependency>", re.DOTALL)
RE_GROUP_ID = re.compile(r"<groupId>\s*([^<]+?)\s*</groupId>")
RE_ARTIFACT_ID = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>")


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_text(p: Path, s: str):
    p.write_text(s, encoding="utf-8")


def collect_existing_artifact_ids(repo_root: Path) -> set[str]:
    """
    收集仓库里所有 pom.xml 的 project artifactId（用于判断 *-api/*-biz 是否真实存在）
    """
    artifact_ids = set()
    # 简化：取第一个非 parent 的 artifactId
    parent_block = re.compile(r"(<parent>\s*.*?</parent>)", re.DOTALL)

    for pom in repo_root.rglob("pom.xml"):
        xml = read_text(pom)
        pm = parent_block.search(xml)
        ps = pm.span(1) if pm else None
        for m in RE_ARTIFACT_ID.finditer(xml):
            if ps and ps[0] <= m.start(0) <= ps[1]:
                continue
            artifact_ids.add(m.group(1).strip())
            break
    return artifact_ids


def dedupe_modules_lines(xml: str) -> str:
    """
    删除同一个 pom.xml 中重复的 <module>xxx</module> 行（保留第一次出现）。
    只处理“完全相同的 module 路径字符串”的重复。
    """
    lines = xml.splitlines(True)
    seen = set()
    out = []
    for line in lines:
        m = RE_MODULE_LINE.match(line.strip("\n"))
        if not m:
            out.append(line)
            continue
        mod = m.group(2).strip()
        if mod in seen:
            # 跳过重复 module 行
            continue
        seen.add(mod)
        out.append(line)
    return "".join(out)


def rewrite_modules_to_api_biz(xml: str, existing_aids: set[str]) -> str:
    """
    若 <module> 的最后一段目录名是 future-module-xxx，且仓库存在对应 future-module-xxx-api/-biz，
    则把该 module 行替换为两行 api + biz。
    """
    lines = xml.splitlines(True)
    out = []

    for line in lines:
        m = RE_MODULE_LINE.match(line.strip("\n"))
        if not m:
            out.append(line)
            continue

        indent = m.group(1)
        mod_path = m.group(2).strip()

        last = mod_path.split("/")[-1]
        if not last.startswith(MODULE_PREFIX) or last.endswith(SKIP_SUFFIXES):
            out.append(line)
            continue

        api_aid = last + "-api"
        biz_aid = last + "-biz"
        if api_aid not in existing_aids or biz_aid not in existing_aids:
            out.append(line)
            continue

        prefix = "/".join(mod_path.split("/")[:-1])
        if prefix:
            api_path = f"{prefix}/{last}-api"
            biz_path = f"{prefix}/{last}-biz"
        else:
            api_path = f"{last}-api"
            biz_path = f"{last}-biz"

        out.append(f"{indent}<module>{api_path}</module>\n")
        out.append(f"{indent}<module>{biz_path}</module>\n")

    return "".join(out)


def rewrite_deps_to_biz(xml: str, existing_aids: set[str]) -> str:
    """
    把依赖里 groupId=cn.iocoder.boot 且 artifactId=future-module-xxx 的，改成 future-module-xxx-biz，
    前提是仓库确实存在该 *-biz 模块。
    """
    def rewrite_one_dep(dep_xml: str) -> str:
        gm = RE_GROUP_ID.search(dep_xml)
        am = RE_ARTIFACT_ID.search(dep_xml)
        if not gm or not am:
            return dep_xml

        gid = gm.group(1).strip()
        aid = am.group(1).strip()

        if gid != ROOT_GROUP_ID:
            return dep_xml
        if not aid.startswith(MODULE_PREFIX):
            return dep_xml
        if aid.endswith(SKIP_SUFFIXES):
            return dep_xml

        biz_aid = aid + "-biz"
        if biz_aid not in existing_aids:
            return dep_xml

        return RE_ARTIFACT_ID.sub(f"<artifactId>{biz_aid}</artifactId>", dep_xml, count=1)

    def repl(m):
        return rewrite_one_dep(m.group(0))

    return RE_DEP_BLOCK.sub(repl, xml)


def main():
    repo_root = Path(".")
    existing_aids = collect_existing_artifact_ids(repo_root)

    changed = 0
    for pom in repo_root.rglob("pom.xml"):
        xml = read_text(pom)
        new_xml = xml

        # 1) modules 去重（解决你现在的 duplicate child module）
        new_xml = dedupe_modules_lines(new_xml)

        # 2) modules: base -> api + biz（仅当 api/biz 模块真实存在）
        new_xml = rewrite_modules_to_api_biz(new_xml, existing_aids)

        # 3) dependencies: base -> base-biz（future-server/其他模块统一依赖 biz）
        new_xml = rewrite_deps_to_biz(new_xml, existing_aids)

        # 再去重一次（防止替换后出现重复）
        new_xml = dedupe_modules_lines(new_xml)

        if new_xml != xml:
            write_text(pom, new_xml)
            changed += 1

    print(f"🎉 post split fix done. changed_pom_count={changed}")


if __name__ == "__main__":
    main()
