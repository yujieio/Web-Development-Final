@echo off
cd /d "%~dp0"
echo Running Flask from: %CD%
echo.
echo Make sure you're in the yujie webdev folder!
echo Sign up page: http://127.0.0.1:5000/signup
echo.
python app.py
