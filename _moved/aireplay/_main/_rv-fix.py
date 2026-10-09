import glob, os
n = 0
for p in glob.glob(os.path.join(r"H:\sotto\_moved\aireplay\receipts", "review-*.md")):
    s = open(p, encoding="utf-8").read()
    if "CH K-REV-2" in s:
        open(p, "w", encoding="utf-8", newline="\n").write(s.replace("`CH K-REV-2`", "`CHK-REV-2`"))
        n += 1
print("fixed files:", n)
