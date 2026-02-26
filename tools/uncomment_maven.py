import re
from pathlib import Path

# <!-- <module>xxx</module> -->
MODULE_LINE = re.compile(r'^(\s*)<!--\s*(<module>([^<]+)</module>)\s*-->\s*$')

# 识别 “<!-- <tag>...</tag> -->” 这种单行注释
COMMENTED_XML_LINE = re.compile(r'^(\s*)<!--\s*(<[^!].*?)\s*-->\s*$')
COMMENTED_XML_OPEN = re.compile(r'^(\s*)<!--\s*(<[^!].*?)\s*$')   # 只有开头 <!--
COMMENTED_XML_CLOSE = re.compile(r'^(.*?)(\s*)-->\s*$')           # 只有结尾 -->

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

def get_artifact_id(block_text: str):
    m = ARTIFACT_ID.search(block_text)
    return m.group(1).strip() if m else None

def should_enable_dep(block_text: str) -> bool:
    aid = get_artifact_id(block_text)
    if not aid:
        return False
    # 只解注释 future-module-*（你要更激进的话，可以改成 return True）
    return aid.startswith("future-module-")

def process_pom(pom: Path) -> bool:
    lines = pom.read_text(encoding="utf-8").splitlines(True)
    out = []
    changed = False
    dep_buf = None

    for line in lines:
        # modules 单行
        m = MODULE_LINE.match(line)
        if dep_buf is None and m:
            module_name = m.group(3)
            out.append(f"{m.group(1)}{m.group(2)}\n")
            changed = True
            continue

        # dependency 块缓冲
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
                    out.extend(dep_buf)  # 黑名单/不匹配：原样输出
                dep_buf = None

    # 异常情况：dependency 注释块没闭合，原样写回，避免越修越坏
    if dep_buf is not None:
        out.extend(dep_buf)

    if changed:
        pom.write_text("".join(out), encoding="utf-8")
    return changed

def main():
    root = Path(".")
    poms = list(root.rglob("pom.xml"))
    changed_cnt = 0

    for pom in poms:
        try:
            if process_pom(pom):
                print(f"✅ updated: {pom}")
                changed_cnt += 1
        except Exception as e:
            print(f"❌ failed: {pom} -> {e}")

    print(f"🎉 done. changed pom count = {changed_cnt}")

if __name__ == "__main__":
    main()
