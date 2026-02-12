# tools/uncomment_maven.py
import re
from pathlib import Path

def process_pom(pom_path: Path) -> bool:
    text = pom_path.read_text(encoding="utf-8")

    original = text

    # 1) 解注释单行 module：<!-- <module>xxx</module> -->
    text = re.sub(
        r"<!--\s*(<module>[^<]+</module>)\s*-->",
        r"\1",
        text,
        flags=re.MULTILINE,
    )

    # 2) 解注释 dependency 块（只放开 future-module-*，避免把普通说明注释也打开）
    text = re.sub(
        r"<!--\s*(<dependency>\s*.*?<artifactId>\s*future-module-[^<]+\s*</artifactId>.*?</dependency>)\s*-->",
        r"\1",
        text,
        flags=re.DOTALL,
    )

    if text != original:
        pom_path.write_text(text, encoding="utf-8")
        return True
    return False

def main():
    root = Path(".")
    poms = list(root.rglob("pom.xml"))

    changed = 0
    for pom in poms:
        try:
            if process_pom(pom):
                changed += 1
                print(f"✅ uncomment: {pom}")
        except Exception as e:
            print(f"❌ failed: {pom} -> {e}")

    print(f"🎉 done. changed pom count = {changed}")

if __name__ == "__main__":
    main()
