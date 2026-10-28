# -*- coding: utf-8 -*-
"""Check official GitHub Releases. User explicitly downloads and installs updates."""
import json, urllib.request, webbrowser, re
from tkinter import messagebox
VERSION = '4.2.0'
REPO = 'eunsolar/seoryumeong-updates'

def parse_version(tag):
    m = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', tag or '')
    return tuple(map(int,m.groups())) if m else None

def check_and_install():
    req = urllib.request.Request('https://api.github.com/repos/'+REPO+'/releases/latest',headers={
        'User-Agent':'Seoryumeong/'+VERSION,
        'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28'
    })
    try:
        with urllib.request.urlopen(req,timeout=10) as response:
            data = json.load(response)
    except urllib.error.HTTPError as e:
        if e.code == 404: return '아직 공개된 업데이트 버전(GitHub Release)이 없습니다.'
        raise
    tag=data.get('tag_name','')
    newest=parse_version(tag)
    current=parse_version(VERSION)
    if not newest or not current: return '버전 형식을 확인할 수 없습니다.'
    if newest<=current:return '최신 버전입니다 (v'+VERSION+').' 
    release_url=data.get('html_url','')
    expected='https://github.com/'+REPO+'/releases/tag/'
    if not release_url.startswith(expected):return '업데이트 주소를 검증할 수 없습니다.'
    if messagebox.askyesno('서류멍 업데이트',f'새 버전 {tag}이 있습니다. 공식 GitHub 다운로드 페이지를 열까요?'):
        webbrowser.open(release_url)
    return '새 버전 '+tag+' 확인 완료 (직접 설치 필요)'
