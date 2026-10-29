# -*- coding: utf-8 -*-
"""Opt-in one-click Windows EXE updates. Document content never leaves this PC."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
try:
    from build_info import VERSION
except ImportError:
    VERSION = '4.3.0'

REPO = 'eunsolar/seoryumeong-updates'
USER_AGENT = 'Seoryumeong/' + VERSION

def parse_version(tag):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', tag or '')
    return tuple(map(int, match.groups())) if match else None

def check_for_update():
    request = urllib.request.Request(
        'https://api.github.com/repos/' + REPO + '/releases/latest',
        headers={'User-Agent': USER_AGENT, 'Accept': 'application/vnd.github+json'}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            release = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {'available': False}
        raise
    tag = release.get('tag_name', '')
    current = parse_version(VERSION)
    newest = parse_version(tag)
    if not current or not newest or newest <= current:
        return {'available': False}
    url = release.get('html_url', '')
    if not url.startswith('https://github.com/' + REPO + '/releases/tag/'):
        raise ValueError('Unexpected release URL')
    asset = next((item for item in release.get('assets', [])
                  if item.get('name') == 'Seoryumeong-Windows.zip'), None)
    if asset is None:
        raise ValueError('Release does not contain Seoryumeong-Windows.zip')
    asset_url = asset.get('browser_download_url', '')
    if not asset_url.startswith('https://github.com/' + REPO + '/releases/download/'):
        raise ValueError('Unexpected download URL')
    return {'available': True, 'tag': tag, 'url': url,
            'asset_url': asset_url, 'digest': asset.get('digest', '')}

def download_update(info, progress=None):
    """Download only to a disposable temp directory; no documents, logs, or backups."""
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        raise RuntimeError('자동 교체는 설치된 Windows EXE에서만 사용할 수 있어요.')
    current = Path(sys.executable).resolve()
    if current.name.lower() != 'seoryumeong.exe':
        raise RuntimeError('예상한 프로그램 실행 파일이 아니에요.')
    temp = Path(tempfile.mkdtemp(prefix='seoryumeong-update-'))
    archive = temp / 'release.zip'
    replacement = temp / 'Seoryumeong.exe'
    try:
        request = urllib.request.Request(info['asset_url'], headers={'User-Agent': USER_AGENT})
        digest = hashlib.sha256()
        with urllib.request.urlopen(request, timeout=40) as source, archive.open('wb') as dest:
            total = int(source.headers.get('Content-Length', 0))
            received = 0
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                dest.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress:
                    progress(min(95, int(received * 95 / total)) if total else 0, '다운로드 중')
        expected = info.get('digest', '')
        if expected:
            if not expected.startswith('sha256:') or digest.hexdigest().lower() != expected[7:].lower():
                raise ValueError('다운로드 파일 무결성 확인 실패')
        if progress: progress(96, '다운로드 검증 완료')
        with zipfile.ZipFile(archive) as package:
            names = [n for n in package.namelist() if Path(n).name.lower() == 'seoryumeong.exe']
            if len(names) != 1:
                raise ValueError('업데이트 ZIP에 EXE가 없거나 중복되어 있어요.')
            with package.open(names[0]) as source, replacement.open('wb') as dest:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    dest.write(chunk)
        if replacement.stat().st_size < 100000 or replacement.open('rb').read(2) != b'MZ':
            raise ValueError('다운로드한 EXE의 형식이 올바르지 않아요.')
        archive.unlink(missing_ok=True)
        if progress: progress(100, '설치 준비 완료')
        return current, replacement, temp
    except Exception:
        import shutil
        shutil.rmtree(temp, ignore_errors=True)
        raise

def launch_installer(current, replacement, temp):
    """Run detached PowerShell to wait for current process, replace, relaunch and cleanup."""
    if os.name != 'nt':
        raise RuntimeError('Windows 전용 업데이트 기능이에요.')
    import base64
    # Quoted paths are passed as environment variables to avoid PowerShell interpolation.
    script = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$old = $env:SEORYUMEONG_TARGET
$new = $env:SEORYUMEONG_REPLACEMENT
$work = $env:SEORYUMEONG_TEMP
$pidToWait = [int]$env:SEORYUMEONG_PID
$form = New-Object System.Windows.Forms.Form
$form.Text = '서류멍 업데이트'
$form.Width = 410
$form.Height = 170
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$label = New-Object System.Windows.Forms.Label
$label.Text = '서류멍을 설치하고 있어요...'
$label.AutoSize = $true
$label.Location = New-Object System.Drawing.Point(22,22)
$form.Controls.Add($label)
$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Minimum = 0
$bar.Maximum = 100
$bar.Value = 20
$bar.Style = 'Marquee'
$bar.MarqueeAnimationSpeed = 25
$bar.Width = 345
$bar.Location = New-Object System.Drawing.Point(22,60)
$form.Controls.Add($bar)
$form.Show()
[System.Windows.Forms.Application]::DoEvents()
try {
  Wait-Process -Id $pidToWait -Timeout 90 -ErrorAction SilentlyContinue
  $completed = $false
  for ($i = 0; $i -lt 40; $i++) {
    try {
      Copy-Item -LiteralPath $new -Destination $old -Force -ErrorAction Stop
      $completed = $true
      break
    } catch { Start-Sleep -Milliseconds 750 }
    [System.Windows.Forms.Application]::DoEvents()
  }
  $bar.Style = 'Continuous'
  $bar.Value = 100
  if (-not $completed) { throw '파일 교체에 실패했어요. 앱 설치 위치의 쓰기 권한을 확인하세요.' }
  $label.Text = '업데이트 완료! 서류멍을 다시 실행할게요.'
  [System.Windows.Forms.Application]::DoEvents()
  Start-Process -FilePath $old
  [System.Windows.Forms.MessageBox]::Show('서류멍 업데이트가 완료됐어요!','서류멍', 'OK','Information') | Out-Null
} catch {
  [System.Windows.Forms.MessageBox]::Show('업데이트에 실패했어요: ' + $_.Exception.Message,'서류멍', 'OK','Error') | Out-Null
} finally {
  $form.Close()
  Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
"""
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    env = os.environ.copy()
    env.update({'SEORYUMEONG_TARGET': str(current),
                'SEORYUMEONG_REPLACEMENT': str(replacement),
                'SEORYUMEONG_TEMP': str(temp),
                'SEORYUMEONG_PID': str(os.getpid())})
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)
    subprocess.Popen(['powershell.exe', '-STA', '-NoProfile', '-NonInteractive',
                      '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded],
                     env=env, creationflags=flags, close_fds=True)
