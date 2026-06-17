@echo off
setlocal

if "%~1"=="" (
  echo Usage: run.bat "C:\path\to\input_songs" "C:\path\to\output_videos"
  exit /b 1
)

if "%~2"=="" (
  echo Usage: run.bat "C:\path\to\input_songs" "C:\path\to\output_videos"
  exit /b 1
)

set "INPUT_DIR=%~1"
set "OUTPUT_DIR=%~2"
shift
shift

set "EXTRA_ARGS="
:collect_args
if "%~1"=="" goto run_tool
set EXTRA_ARGS=%EXTRA_ARGS% "%~1"
shift
goto collect_args

:run_tool
python -m lyric_video_batcher --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" %EXTRA_ARGS%
