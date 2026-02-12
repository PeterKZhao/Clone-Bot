import re
from pathlib import Path

# 命中这些 artifactId / moduleName 就不打开
IOT_BLACKLIST = re.compile(r"^future-module-iot($|-)")

MODULE_LINE = re.compile(r'^(\s*)<!--\s*(<module>([^<]+)</module>)\s*-->\s*$')

COMMENTED_XML_LINE = re.compile(r'^(\s*)<!--\s*(<[^!].*?)\s*-->\s*$')
COMMENTED_XML_OPEN = re.compile(r'^(\s*)<!--\s*(<[^!].*?)\s*$')
COMMENTED_XML_CLOSE = re.compile(r'^(.*?)(\s*)-->\s*$')

DEP_START = re.compile(r'^\s*<!--\s*<dependency>\s*-->\s*$|^\s*<!--\s*<dependency>\s*$')
DEP_END = re.compile(r'.*</dependency>.*')

ARTIFACT_ID = re.compile(r'<artifactId>\s*([^<]+)\s*</artifactId>')

def uncomment_line(line: str) -> str:
    m = COMMENTED_XML_LINE.match(line)
    if m:
        return f"{m.group(1)}{m.group(2)}\n"
    m = COMMENTED_XML_OPEN.match(line)
    if m:
        return f"{m.group(1)}{m.group(2)}\n"
    m = COMMENTED_XML_CLOSE.match(line)
    if m:
        return f"{m.group(1).rstrip()}\n"
    return line

def get_artifact_id(block_text: str) -> str | None:
    m = ARTIFACT_ID.search(block_text)
    return m.group(1).strip() if m else None

def is_iot(name: str) -> bool:
    return bool(IOT_BLACKLIST.match(name.strip()))

def should_enable_dep(block_text: str) -> bool:
    aid = get_artifact_id(block_text)
    if not aid:
        return False
    # IoT 一律不打开（包含 future-module-iot-net-component-*）
    if is_iot(aid):
        return False
    # 你原来“只打开 future-module-*”的话，这里按需保留/扩展
    return aid.startswith("future-module-")

def process_pom(pom: Path) -> bool:
    lines = pom.read_text(encoding="utf-8").splitlines(True)
    out = []
    changed = False
    dep_buf = None

    for line in lines:
        # 1) 解注释 <modules> 里的单行 module，但 IoT module 不解
        m = MODULE_LINE.match(line)
        if dep_buf is None and m:
            module_name = m.group(3)
            if is_iot(module_name):
                out.append(line)          # 保持注释
            else:
                out.append(f"{m.group(1)}{m.group(2)}\n")
                changed = True
            continue

        # 2) dependency 块：整块缓冲，结束后决定是否整块解注释
        if dep_buf is None:
            if DEP_START.match(line):
                dep_buf = [line]
                continue
            out.append(line)
        else:
            dep_buf.append(line)
            if DEP_END.match(line):
                block_text = "".join(dep_buf)
                if should_enable_dep(block_text):
                    new_block = [uncomment_line(x) for x in dep_buf]
                    out.extend(new_block)
                    if "".join(new_block) != block_text:
                        changed = True
                else:
                    out.extend(dep_buf)    # 黑名单或不匹配：原样输出
                dep_buf = None

    if dep_buf is not None:
        out.extend(dep_buf)

    if changed:
        pom.write_text("".join(out), encoding="utf-8")
    return changed
