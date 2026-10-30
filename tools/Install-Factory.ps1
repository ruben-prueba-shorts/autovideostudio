# Run locally with normal user rights. No billing, uploads or deletions.
[CmdletBinding()]
param(
  [string]$Root = (Join-Path $env:LOCALAPPDATA 'YouTubeFactory'),
  [switch]$InstallDependencies,
  [switch]$WithOAuth,
  [switch]$SmokeTest
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This script targets Windows.' }
$Root = [IO.Path]::GetFullPath($Root)
# Refuse preexisting contents instead of guessing which personal files are safe.
if (Test-Path $Root) {
  if (@(Get-ChildItem -Force $Root).Count -ne 0) { throw 'Choose a NEW or EMPTY dedicated folder. Existing installs are not overwritten.' }
} else { New-Item -ItemType Directory -Path $Root | Out-Null }
if ($InstallDependencies) {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Install Microsoft App Installer from the official Microsoft Store first.' }
  # Official WinGet repository; FFmpeg is the Gyan build linked by ffmpeg.org.
  # Terms/UAC remain interactive: this script does not bypass or auto-accept them.
  $packages = @(@('py','Python.Python.3.13'),@('node','OpenJS.NodeJS.LTS'),@('ffmpeg','Gyan.FFmpeg'))
  foreach ($package in $packages) {
    if (-not (Get-Command $package[0] -ErrorAction SilentlyContinue)) {
      & winget install --exact --id $package[1] --source winget --scope user
      if ($LASTEXITCODE -ne 0) { throw ('Dependency install failed: ' + $package[1] + '. Use the official vendor installer; no administrator/billing workaround is attempted.') }
    }
  }
  $env:PATH = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}
foreach ($command in @('py','node','ffmpeg','ffprobe')) {
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw ('Missing ' + $command + '. See automation/WINDOWS-YOUTUBE.md for official sources, then rerun in an empty dedicated folder.') }
}
& py -3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }
$nodeVersion = & node -p 'process.versions.node'
if ($LASTEXITCODE -ne 0 -or ([version]$nodeVersion).Major -lt 20) { throw 'Node.js 20+ required.' }
$src = Join-Path $Root 'src'; New-Item -ItemType Directory $src | Out-Null
$versions = @()
$repos = @(@('autovideostudio','fix/flow-images-project-persistence'),@('clipfarming','feature/autovideo-package-import'))
foreach ($repo in $repos) {
  $name=$repo[0]; $branch=[uri]::EscapeDataString($repo[1])
  # Resolve a development branch ONCE, then download that immutable commit.
  $info=Invoke-RestMethod -Uri "https://api.github.com/repos/ruben-prueba-shorts/$name/commits/$branch" -Headers @{'User-Agent'='VideoFactory-local-installer'}
  $sha=[string]$info.sha
  if ($sha -notmatch '^[a-f0-9]{40}$') { throw 'GitHub did not return an immutable commit.' }
  $archive=Join-Path $Root ($name+'.zip'); $unpack=Join-Path $Root ($name+'-archive')
  Invoke-WebRequest -UseBasicParsing -Uri "https://api.github.com/repos/ruben-prueba-shorts/$name/zipball/$sha" -Headers @{'User-Agent'='VideoFactory-local-installer'} -OutFile $archive
  $hash=(Get-FileHash -Algorithm SHA256 $archive).Hash
  Expand-Archive -LiteralPath $archive -DestinationPath $unpack
  $folders=@(Get-ChildItem -Directory -LiteralPath $unpack)
  if ($folders.Count -ne 1) { throw 'Unexpected archive structure.' }
  Move-Item -LiteralPath $folders[0].FullName -Destination (Join-Path $src $name)
  # Keep the archives; no deletion is enabled by the installer.
  $versions += @{repository="ruben-prueba-shorts/$name"; branch=$repo[1]; commit=$sha; archiveSha256=$hash; kind='development source snapshot, not a git checkout'}
}
$versions | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $Root 'source-versions.json')
$auto=Join-Path $src 'autovideostudio'; $data=Join-Path $Root 'data'
& py -3 -m venv (Join-Path $Root '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
$python=Join-Path $Root '.venv\Scripts\python.exe'
if ($WithOAuth) {
  & $python -m pip install --index-url https://pypi.org/simple --disable-pip-version-check -r (Join-Path $auto 'tools\requirements-youtube.txt')
  if ($LASTEXITCODE -ne 0) { throw 'Optional official OAuth dependencies could not be installed.' }
}
& $python (Join-Path $auto 'tools\factory_orchestrator.py') init $data
if ($LASTEXITCODE -ne 0) { throw 'Factory workspace initialization failed.' }
& $python (Join-Path $auto 'tools\factory_local_app.py') --doctor
if ($LASTEXITCODE -ne 0) { throw 'Dependency diagnostics failed.' }
if ($SmokeTest) {
  & $python (Join-Path $auto 'tools\windows_smoke.py') $data
  if ($LASTEXITCODE -ne 0) { throw 'Local delivery/recovery smoke test failed. Files are retained for inspection.' }
}
# Only a loopback server. No scheduled task, autostart, OAuth or upload is activated.
$launcher=Join-Path $Root 'Start-Factory.cmd'
@'
@echo off
"%~dp0.venv\Scripts\python.exe" "%~dp0src\autovideostudio\tools\factory_local_app.py" --root "%~dp0data"
'@ | Set-Content -Encoding ASCII $launcher
Write-Host ('Prepared: ' + $Root)
Write-Host ('Start with: ' + $launcher)
Write-Host 'Open http://127.0.0.1:8765/ after starting. Keep the application running.'
Write-Host 'No YouTube upload, new generation quota or deletion is enabled.'
