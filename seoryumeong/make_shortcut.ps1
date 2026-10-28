$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root 'dist\Seoryumeong.exe'
if (-not (Test-Path $target)) { Write-Host 'Please run build_exe.bat first.'; Read-Host 'Press Enter'; exit 1 }
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop '서류멍.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = (Split-Path $target)
$shortcut.IconLocation = (Join-Path $root 'dog.ico')
$shortcut.Description = '서류멍 - 로컬 서류 정보 추출기'
$shortcut.Save()
Write-Host ('Shortcut created: ' + $lnk)
Read-Host 'Press Enter'
