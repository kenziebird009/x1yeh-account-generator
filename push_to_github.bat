@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==============================================
echo    Publish to GitHub
echo ==============================================
echo.

:: -- ask for GitHub username --
set /p GITHUB_USER="GitHub username: "
if "%GITHUB_USER%"=="" (
    echo Username required.
    pause & exit /b 1
)

:: -- ask for repo name --
set "REPO_NAME=x1yeh-account-generator"
set /p REPO_NAME="Repo name [%REPO_NAME%]: "

:: -- ask for token (masked) --
set /p GH_TOKEN="GitHub Personal Access Token: "
if "%GH_TOKEN%"=="" (
    echo Token required. Create one at https://github.com/settings/tokens
    pause & exit /b 1
)

echo.
echo Creating repository on GitHub...

:: -- create repo via API --
curl -s -X POST -H "Authorization: token %GH_TOKEN%" ^
    -H "Accept: application/vnd.github.v3+json" ^
    "https://api.github.com/user/repos" ^
    -d "{\"name\":\"%REPO_NAME%\",\"private\":false,\"description\":\"X1YEH Account Generator - Premium desktop account management tool\",\"has_issues\":true,\"has_projects\":false,\"has_wiki\":false}" ^
    > nul 2>&1

:: -- set remote and push --
echo Pushing code to GitHub...
git remote remove origin 2>nul
git remote add origin "https://%GITHUB_USER%:%GH_TOKEN%@github.com/%GITHUB_USER%/%REPO_NAME%.git"
git add -A
git commit -m "Initial release - X1YEH Account Generator" 2>nul
git branch -M main
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push failed. Check your token and username.
    echo         Make sure the repo doesn't already exist.
    pause & exit /b 1
)

echo.
echo ==============================================
echo    PUBLISHED SUCCESSFULLY
echo    https://github.com/%GITHUB_USER%/%REPO_NAME%
echo ==============================================
echo.
echo Next steps:
echo   1. Upload version.json as a raw file to your repo
echo   2. Create a GitHub Release with the EXE .zip
echo   3. Update config.json 'version_url' to point to
echo      your raw version.json on GitHub
echo ==============================================
pause
