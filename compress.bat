@echo off
setlocal EnableDelayedExpansion

if "%~1"=="" (
    echo Drag a video file onto this batch file to compress it
    pause
    exit /b
)

set "input=%~1"
set "output=%~dpn1_compressed%~x1"
set "audio_bitrate=128"

set /p "start_time=Enter start time in seconds (or blank for start): "
set /p "duration=Enter duration in seconds (or blank for full): "

:: Add -ss and -t parameters if values are provided
if not "%start_time%"=="" (
    set "start_param=-ss %start_time%"
) else (
    set "start_param="
)

if not "%duration%"=="" (
    set "duration_param=-t %duration%"
) else (
    set "duration_param="
)

:: Check if NVIDIA GPU is available
ffmpeg -encoders 2>&1 | findstr /C:"h264_nvenc" >nul
if %errorlevel% equ 0 (
    set "video_codec=h264_nvenc"
    set "preset=p4"
) else (
    set "video_codec=libx264"
    set "preset=medium"
)

:: Calculate optimal bitrate using Python script
for /f "tokens=1,2" %%i in ('python "%~dp0compress.py" "%input%" "%start_time%" "%duration%"') do (
    set "video_bitrate=%%i"
    set "reduce_fps=%%j"
)

if not defined video_bitrate (
    echo Error: Failed to calculate video bitrate
    pause
    exit /b 1
)

:: Compress video with calculated bitrate
if "%reduce_fps%"=="1" (
    ffmpeg -i "%input%" -y %start_param% %duration_param% ^
        -c:v %video_codec% ^
        -b:v %video_bitrate%k ^
        -maxrate %video_bitrate%k ^
        -bufsize %video_bitrate%k ^
        -preset %preset% ^
        -rc:v vbr ^
        -cq:v 23 ^
        -r 30 ^
        -c:a aac ^
        -b:a %audio_bitrate%k ^
        -map 0:v:0 ^
        -map 0:a:0? ^
        "%output%"
) else (
    ffmpeg -i "%input%" -y %start_param% %duration_param% ^
        -c:v %video_codec% ^
        -b:v %video_bitrate%k ^
        -maxrate %video_bitrate%k ^
        -bufsize %video_bitrate%k ^
        -preset %preset% ^
        -rc:v vbr ^
        -cq:v 23 ^
        -c:a aac ^
        -b:a %audio_bitrate%k ^
        -map 0:v:0 ^
        -map 0:a:0? ^
        "%output%"
)

:: Check if output file exists and has size
if not exist "%output%" (
    echo Error: Compression failed
    pause
    exit /b 1
)

:: Check output file size
for %%A in ("%output%") do set "size=%%~zA"
set /a "size_mb=%size%/1048576"

echo.
if %size_mb% LEQ 10 (
    echo Compression successful! Output size: %size_mb% MB
) else (
    echo Warning: Could not compress below 10 MB. Output size: %size_mb% MB
)

pause