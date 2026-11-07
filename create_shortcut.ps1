# create_shortcut.ps1 (v1.0)
# Creates a FireTrack shortcut on the desktop. Run once:
#   powershell -ExecutionPolicy Bypass -File create_shortcut.ps1
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $desktop 'FireTrack.lnk'))
$link.TargetPath = Join-Path $project 'FireTrack.bat'
$link.WorkingDirectory = $project
$link.IconLocation = Join-Path $project 'static\favicon.ico'
$link.Description = 'FireTrack'
$link.Save()
Write-Output "Shortcut created: $(Join-Path $desktop 'FireTrack.lnk')"
