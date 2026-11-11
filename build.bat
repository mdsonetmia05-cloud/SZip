@echo off
REM ============================================================
REM  SZip — build.bat (Windows PC-র জন্য)
REM  একটাই .exe বানায়: SZip.exe (পোর্টেবল, ইনস্টল লাগে না)
REM
REM  ব্যবহার: এই ফাইলটায় ডাবল-ক্লিক করুন।
REM  দরকার: Windows 10/11 + Python 3.10+ (python.org থেকে) + ইন্টারনেট
REM          (প্রথমবার pip দিয়ে প্যাকেজ নামাতে ইন্টারনেট লাগবে;
REM           exe হয়ে গেলে আর ইন্টারনেট লাগবে না — সম্পূর্ণ অফলাইন)
REM
REM  মনে রাখবেন: Linux-এ PyInstaller দিয়ে Windows-এর exe বানানো যায় না।
REM  তাই exe বানাতে এই .bat Windows PC-তেই চালাতে হবে।
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ===== SZip — exe বানানো হচ্ছে =====
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo  [ভুল] Python পাওয়া যায়নি!
    echo  python.org থেকে Python 3.10+ ইনস্টল করুন,
    echo  ইনস্টল করার সময় "Add Python to PATH"-এ টিক দিন।
    pause
    exit /b 1
)

echo  [1/4] Python সংস্করণ:
python --version

echo.
echo  [2/4] ভার্চুয়াল পরিবেশ (venv) বানানো হচ্ছে...
if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat

echo.
echo  [3/4] প্রয়োজনীয় প্যাকেজ ইনস্টল হচ্ছে...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install PyInstaller

echo.
echo  [4/4] exe বানানো হচ্ছে (PyInstaller --onefile --windowed)...
PyInstaller --onefile --windowed --name SZip --version-file version.txt --clean main.py

echo.
if exist "dist\SZip.exe" (
    echo  ===== হয়ে গেছে! =====
    echo  exe ফাইল: %CD%\dist\SZip.exe
    echo  এটা যেকোনো ফোল্ডারে নিয়ে ডাবল-ক্লিক করলেই চলবে — ইনস্টল লাগবে না।
) else (
    echo  [ভুল] exe বানানো যায়নি — উপরের লাল লেখাগুলো দেখুন।
)
echo.
pause
