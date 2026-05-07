@echo off
echo ============================================
echo  SR Manager v2 — Production Ready
echo ============================================
echo.

REM Optional: set Twilio env vars here if not set system-wide
REM set TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
REM set TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
REM set TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

echo Starting application...
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Application failed to start.
    echo Run: pip install -r requirements.txt
    echo For WhatsApp QR mode also run: pip install PyQt6-WebEngine
    pause
)
