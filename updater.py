# -*- coding: utf-8 -*-
"""Only checks GitHub's public Releases. Never uploads document data."""
import json, urllib.request, urllib.error, re
REPO = 'eunsolar/seoryumeong-updates'
try:
    from build_info import VERSION
except ImportError:
    VERSION = '4.3.0'

def parse_version(tag):
    m=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',tag or '')
    return tuple(map(int,m.groups())) if m else None

def check_for_update():
    req=urllib.request.Request(
        'https://api.github.com/repos/'+REPO+'/releases/latest',
        headers={'User-Agent':'Seoryumeong/'+VERSION,'Accept':'application/vnd.github+json'}
    )
    try:
        with urllib.request.urlopen(req,timeout=8) as response:data=json.load(response)
    except urllib.error.HTTPError as e:
        if e.code==404:return {'available':False}
        raise
    tag=data.get('tag_name','')
    url=data.get('html_url','')
    expected='https://github.com/'+REPO+'/releases/tag/'
    latest=parse_version(tag)
    if not latest or not url.startswith(expected):return {'available':False}
    return {'available':latest>parse_version(VERSION),'tag':tag,'url':url}
