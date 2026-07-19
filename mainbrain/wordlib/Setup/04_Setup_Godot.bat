@echo off
:: ================================================================
:: WORDLIB Setup Step 4 -- Godot 4.7 Portable (Self-Contained)
::
:: Downloads Godot 4.7 stable Windows 64-bit.
:: Creates _sc_ file so ALL settings stay on USB (not the host PC).
:: Installs addons: Dialogic, Phantom Camera.
:: Sets up a template project with both addons enabled.
:: ================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0.."
title WORDLIB Setup -- Godot 4.7

echo.
echo  =====================================================
echo    WORDLIB Setup [4/4] -- Godot 4.7 Portable
echo  =====================================================
echo.

set GODOT_DIR=%~dp0..\Godot
set GODOT_EXE=%GODOT_DIR%\Godot_v4.7-stable_win64.exe
set PROJECT_DIR=%~dp0..\GodotProjects\Template

if not exist "%GODOT_DIR%" mkdir "%GODOT_DIR%"
if not exist "%PROJECT_DIR%" mkdir "%PROJECT_DIR%"

:: ── Download Godot 4.7 ───────────────────────────────────────
if exist "%GODOT_EXE%" (
    echo  [OK] Godot 4.7 already present.
    goto :SELF_CONTAINED
)

echo  Downloading Godot 4.7 stable (Windows 64-bit, ~85 MB)...
set GODOT_URL=https://github.com/godotengine/godot/releases/download/4.7-stable/Godot_v4.7-stable_win64.exe.zip
set GODOT_ZIP=%GODOT_DIR%\godot_temp.zip

powershell -Command "& {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri '%GODOT_URL%' -OutFile '%GODOT_ZIP%' -UseBasicParsing
}"
if not exist "%GODOT_ZIP%" (
    echo  [ERR] Godot download failed.
    echo        Download manually from: https://godotengine.org/download/windows/
    echo        Extract Godot_v4.7-stable_win64.exe to: %GODOT_DIR%\
    pause & exit /b 1
)

powershell -Command "Expand-Archive '%GODOT_ZIP%' '%GODOT_DIR%' -Force"
del "%GODOT_ZIP%" 2>nul
echo  [OK] Godot 4.7 extracted.

:SELF_CONTAINED
:: ── Create _sc_ file for self-contained mode ─────────────────
:: This single empty file forces Godot to store ALL settings in
:: the same folder as the .exe, not in %APPDATA%. 
:: Without it, every new PC gets fresh settings and loses your theme.
if not exist "%GODOT_DIR%\_sc_" (
    type nul > "%GODOT_DIR%\_sc_"
    echo  [OK] Self-contained mode enabled (_sc_ file created).
    echo       Godot will store all settings in: %GODOT_DIR%\
) else (
    echo  [OK] Self-contained mode already set.
)

:: ── Create template project.godot ────────────────────────────
if not exist "%PROJECT_DIR%\project.godot" (
    echo  Creating template project...
    mkdir "%PROJECT_DIR%\addons" 2>nul
    mkdir "%PROJECT_DIR%\scenes" 2>nul
    mkdir "%PROJECT_DIR%\scripts" 2>nul

    (
        echo ; Engine configuration file.
        echo ; It's best edited using the editor UI and not directly,
        echo ; since the parameters that go here are not all obvious.
        echo ;
        echo ; Format:
        echo ;   [section] ; section goes between []
        echo ;   param=value ; assign values to parameters
        echo.
        echo config_version=5
        echo.
        echo [application]
        echo.
        echo config/name="WORDLIB Template"
        echo config/features=PackedStringArray^("4.7"^)
        echo.
        echo [editor_plugins]
        echo.
        echo enabled=PackedStringArray^(^)
    ) > "%PROJECT_DIR%\project.godot"
    echo  [OK] Template project created.
)

:: ── Download Dialogic ─────────────────────────────────────────
set DIALOGIC_DIR=%PROJECT_DIR%\addons\dialogic
if exist "%DIALOGIC_DIR%\plugin.cfg" (
    echo  [OK] Dialogic already installed.
) else (
    echo  Downloading Dialogic (dialogue/VN system)...
    set DLG_URL=https://github.com/dialogic-godot/dialogic/releases/latest/download/dialogic.zip
    set DLG_ZIP=%GODOT_DIR%\dialogic_temp.zip
    powershell -Command "& {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri '!DLG_URL!' -OutFile '!DLG_ZIP!' -UseBasicParsing
    }"
    if exist "!DLG_ZIP!" (
        powershell -Command "Expand-Archive '!DLG_ZIP!' '%PROJECT_DIR%\_dialogic_tmp' -Force"
        :: The ZIP contains an addons/ folder -- copy its contents
        if exist "%PROJECT_DIR%\_dialogic_tmp\addons\dialogic" (
            xcopy "%PROJECT_DIR%\_dialogic_tmp\addons\dialogic" "%DIALOGIC_DIR%" /E /I /Q
        ) else if exist "%PROJECT_DIR%\_dialogic_tmp\dialogic" (
            xcopy "%PROJECT_DIR%\_dialogic_tmp\dialogic" "%DIALOGIC_DIR%" /E /I /Q
        )
        rd /s /q "%PROJECT_DIR%\_dialogic_tmp" 2>nul
        del "!DLG_ZIP!" 2>nul
        if exist "%DIALOGIC_DIR%\plugin.cfg" (
            echo  [OK] Dialogic installed.
        ) else (
            echo  [WARN] Dialogic folder structure unexpected -- check addons\dialogic\
        )
    ) else (
        echo  [WARN] Dialogic download failed. Install manually from:
        echo         https://github.com/dialogic-godot/dialogic/releases/latest
        echo         Copy the addons\dialogic folder into: %PROJECT_DIR%\addons\
    )
)

:: ── Download Phantom Camera ───────────────────────────────────
set PHANTOM_DIR=%PROJECT_DIR%\addons\phantom_camera
if exist "%PHANTOM_DIR%\plugin.cfg" (
    echo  [OK] Phantom Camera already installed.
) else (
    echo  Downloading Phantom Camera (cinematic camera system)...
    set PC_URL=https://github.com/ramokz/phantom-camera/releases/latest/download/phantom-camera.zip
    set PC_ZIP=%GODOT_DIR%\phantom_camera_temp.zip
    powershell -Command "& {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri '!PC_URL!' -OutFile '!PC_ZIP!' -UseBasicParsing
    }"
    if exist "!PC_ZIP!" (
        powershell -Command "Expand-Archive '!PC_ZIP!' '%PROJECT_DIR%\_phantom_tmp' -Force"
        :: Find phantom_camera plugin.cfg recursively
        for /r "%PROJECT_DIR%\_phantom_tmp" %%D in (plugin.cfg) do (
            set PC_FOUND_DIR=%%~dpD
        )
        if defined PC_FOUND_DIR (
            xcopy "!PC_FOUND_DIR!" "%PHANTOM_DIR%" /E /I /Q
        )
        rd /s /q "%PROJECT_DIR%\_phantom_tmp" 2>nul
        del "!PC_ZIP!" 2>nul
        if exist "%PHANTOM_DIR%\plugin.cfg" (
            echo  [OK] Phantom Camera installed.
        ) else (
            echo  [WARN] Phantom Camera structure unexpected -- check addons\phantom_camera\
        )
    ) else (
        echo  [WARN] Phantom Camera download failed. Install manually from:
        echo         https://github.com/ramokz/phantom-camera/releases/latest
        echo         Copy addons\phantom_camera into: %PROJECT_DIR%\addons\
    )
)

:: ── Enable plugins in project.godot ──────────────────────────
:: Update the plugins list in project.godot
set PLUGINS=
if exist "%DIALOGIC_DIR%\plugin.cfg"  set PLUGINS=!PLUGINS!"dialogic",
if exist "%PHANTOM_DIR%\plugin.cfg"   set PLUGINS=!PLUGINS!"phantom_camera",
:: Remove trailing comma
set PLUGINS=!PLUGINS:~0,-1!

if defined PLUGINS (
    powershell -Command "
        \$f = '%PROJECT_DIR%\project.godot'
        \$c = Get-Content \$f -Raw
        \$c = \$c -replace 'enabled=PackedStringArray\(.*?\)', 'enabled=PackedStringArray(!PLUGINS!)'
        Set-Content \$f \$c
    "
    echo  [OK] Plugins enabled in project.godot: !PLUGINS!
)

echo.
echo  =====================================================
echo   Godot 4.7 portable setup complete.
echo.
echo   Executable:  Godot\Godot_v4.7-stable_win64.exe
echo   Project:     GodotProjects\Template\
echo   Addons:      Dialogic + Phantom Camera
echo   Mode:        Self-contained (_sc_ file present)
echo.
echo   Open Godot and import the Template project to start.
echo   All settings stay on the USB stick.
echo  =====================================================
echo.
pause
