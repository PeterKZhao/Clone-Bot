import re
from pathlib import Path

RE_MODULE = re.compile(r'^(\s*)<!--\s*(<module>[^<]+</module>)\s*-->\s*$')
RE_DEP_COMMENTED = re.compile(r'<!--\s*<dependency>(.*?)</dependency>\s*-->', re.DOTALL)
RE_ARTIFACT_ID = re.compile(r'<artifactId>\s*([^<]+?)\s*</artifactId>')


def should_enable(artifact_id: str) -> bool:
    return artifact_id.startswith("future-module-")


def process_pom(pom: Path) -> bool:
    text = pom.read_text(encoding="utf-8")
    original = text

    # 1. 解注释 module 行
    text = RE_MODULE.sub(lambda m: f"{m.group(1)}{m.group(2)}\n", text)

    # 2. 解注释符合条件的 dependency 块
    def uncomment_dep(m):
        inner = m.group(0)
        aid_m = RE_ARTIFACT_ID.search(inner)
        if aid_m and should_enable(aid_m.group(1).strip()):
            # 去掉外层 <!-- 和 -->
            return re.sub(r'<!--\s*', '', re.sub(r'\s*-->', '', inner, count=1), count=1)
        return inner

    text = RE_DEP_COMMENTED.sub(uncomment_dep, text)

    if text != original:
        pom.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    poms = list(Path(".").rglob("pom.xml"))
    changed = 0
    for pom in poms:
        try:
            if process_pom(pom):
                print(f"✅ updated: {pom}")
                changed += 1
        except Exception as e:
            print(f"❌ failed: {pom} -> {e}")
    print(f"🎉 done. changed = {changed}")


if __name__ == "__main__":
    main()
