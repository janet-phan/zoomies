import PyInstaller.__main__
import os
import sys

def build():
    print(f"Starting build process for Zoomies executable on {sys.platform}...")
    
    script_path = "main.py"
    sep = ";" if sys.platform == "win32" else ":"
    
    args = [
        script_path,
        "--name=Zoomies",
        "--clean",
        f"--add-data=zoomies_icon.png{sep}.",
    ]
    
    if sys.platform == "darwin":
        # macOS application bundle (.app)
        args.append("--windowed")
        if os.path.exists("zoomies_icon.icns"):
            args.append("--icon=zoomies_icon.icns")
        # Include data folders if they exist
        for folder in ["characters", "songs", "themes"]:
            if os.path.exists(folder):
                args.append(f"--add-data={folder}{sep}{folder}")
    else:
        # Windows / Linux single binary
        args.append("--onefile")
        args.append("--console")
        if os.path.exists("zoomies_icon.ico"):
            args.append("--icon=zoomies_icon.ico")
    
    PyInstaller.__main__.run(args)
    
    print("\n--------------------------------------------------")
    print("Build complete!")
    if sys.platform == "darwin":
        print(f"macOS App Bundle: {os.path.abspath('dist/Zoomies.app')}")
    else:
        print(f"Binary: {os.path.abspath('dist/Zoomies.exe')}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    build()
