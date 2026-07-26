"""Remove UTF-8 BOM from all mod .txt files under common/ and events/."""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOM = b"\xef\xbb\xbf"

dirs_to_scan = [
    os.path.join(root, "common", "scripted_effects"),
    os.path.join(root, "common", "decisions"),
    os.path.join(root, "events"),
    os.path.join(root, "localisation", "english"),
    os.path.join(root, "localisation", "simp_chinese"),
]

fixed = 0
for d in dirs_to_scan:
    if not os.path.isdir(d):
        continue
    for fname in os.listdir(d):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(d, fname)
        with open(fpath, "rb") as f:
            data = f.read()
        if data[:3] == BOM:
            with open(fpath, "wb") as f:
                f.write(data[3:])
            print(f"Fixed: {os.path.relpath(fpath, root)}")
            fixed += 1

if fixed:
    print(f"\nTotal fixed: {fixed} file(s)")
else:
    print("No BOM found in scanned directories.")