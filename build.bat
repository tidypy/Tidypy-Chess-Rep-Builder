@echo off
pyinstaller --onedir --noconsole --hidden-import=qt_material --collect-data=qt_material --name Tidypy src/main.py
pause