import re
from pathlib import Path

MODULE_LINE = re.compile(r'^(\s*)<!--\s*(<module>[^<]+</module>)\s*-->\s*$')

# 识别“这一行是被注释的 xml tag 行”，例如 <!-- <groupId>...</groupId> -->
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
        # 去掉开头 <!--
        return f"{m.group(1)}{m.group(2)}\n"
    m = COMMENTED_XML_CLOSE.match(line)
    if m:
        # 去掉结尾 -->
        return f"{m.group(1).rstrip()}\n"
    return line

def should_enable_dep(block_text: str) -> bool:
    m = ARTIFACT_ID.search(block_text)
    if not m:
        return False
    return m.group(1).strip().startswith("future-module-")

def process_pom(pom: Path) -> bool:
    lines = pom.read_text(encoding="utf-8").splitlines(True)
    out = []
    changed = False

    dep_buf = None  # list[str] or None

    for line in lines:
        # 1) 先处理 modules 的单行注释：<!-- <module>xxx</module> -->
        m = MODULE_LINE.match(line)
        if dep_buf is None and m:
            out.append(f"{m.group(1)}{m.group(2)}\n")
            changed = True
            continue

        # 2) dependency 块：缓冲整块，结束后决定是否整块解注释
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
                    out.extend(dep_buf)
                dep_buf = None

    # 如果文件末尾还有没闭合的缓冲块，原样输出（避免越改越坏）
    if dep_buf is not None:
        out.extend(dep_buf)

    if changed:
        pom.write_text("".join(out), encoding="utf-8")
    return changed

def main():
    root = Path(".")
    poms = list(root.rglob("pom.xml"))
    count = 0
    for pom in poms:
        try:
            if process_pom(pom):
                print(f"✅ updated: {pom}")
                count += 1
        except Exception as e:
            print(f"❌ failed: {pom} -> {e}")
    print(f"done, changed={count}")

if __name__ == "__main__":
    main()
