@echo off
echo ============================================
echo  SR Manager v2 — Build Standalone EXE
echo ============================================
echo.

pip install pyinstaller --quiet

echo Building... This takes 2-4 minutes.
echo.

pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "SR_Manager_v2" ^
    --add-data "ui;ui" ^
    --add-data "utils;utils" ^
    --add-data "services;services" ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtWidgets ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import PyQt6.QtWebEngineWidgets ^
    --hidden-import PyQt6.QtWebEngineCore ^
    --hidden-import PyQt6.QtWebChannel ^
    --hidden-import requests ^
    --hidden-import smtplib ^
    --hidden-import csv ^
    main.py

echo.
if exist dist\SR_Manager_v2.exe (
    echo Build successful!
    echo    Executable: dist\SR_Manager_v2.exe
    echo.
    echo    Before distributing, set these environment variables on
    echo    the target machine if using Meta WhatsApp API:
    echo      TWILIO_ACCOUNT_SID  ^(legacy^)
    echo      TWILIO_AUTH_TOKEN   ^(legacy^)
    echo    Meta API credentials are stored in Firestore via Admin Settings.
) else (
    echo Build FAILED. Check errors above.
)
pause
