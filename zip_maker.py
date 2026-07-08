import os
import zipfile

dist_dir = r"dist\tornello"
zip_path = "Tornello.zip"

print("Creating zip archive...")
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(dist_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, dist_dir)
            zipf.write(file_path, arcname)
print("Tornello.zip created successfully!")
