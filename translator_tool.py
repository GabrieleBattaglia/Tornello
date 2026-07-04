import os
import time

f_path = "untranslated_es.txt"
if os.path.exists(f_path):
    mtime = os.path.getmtime(f_path)
    print(f"File: {f_path}")
    print(f"Size: {os.path.getsize(f_path)} bytes")
    print(f"Modification time: {time.ctime(mtime)}")
else:
    print(f"File not found: {f_path}")
