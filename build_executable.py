import PyInstaller.__main__
import os
import shutil

def build():
    print("Starting build process for Zoomies executable...")
    
    # Target script
    script_path = "main.py"
    
    # PyInstaller arguments
    args = [
        script_path,
        "--name=Zoomies",
        "--onefile",
        "--console",  # Show command prompt popup for logging/debugging (controllable via in-game settings!)
        "--icon=zoomies_icon.ico",
        "--add-data=zoomies_icon.png;.",
        "--clean",
    ]
    
    # Run PyInstaller
    PyInstaller.__main__.run(args)
    
    print("\n--------------------------------------------------")
    print("Build complete!")
    print("The standalone executable can be found in the 'dist' folder:")
    print(f"Path: {os.path.abspath('dist/Zoomies.exe')}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    build()
