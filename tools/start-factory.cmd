@echo off
if "%~1"=="" (
  echo Indica una carpeta nueva: start-factory.cmd "D:\Videos\Fabrica"
  exit /b 2
)
py -3 "%~dp0factory_local_app.py" --root "%~1"
