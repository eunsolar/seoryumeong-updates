# -*- coding: utf-8 -*-
"""Preview-first, local-only organizer. Copies documents; never moves sources."""
import re, shutil, hashlib, os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

EXTS={'.pdf','.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'}
def get_name(path):
    stem=path.stem
    m=re.search(r'_([가-힣]{2,5})_\(',stem)
    if m:return m.group(1)
    m=re.search(r'^([가-힣]{2,5}|[가-힣]{2}0)(?=[ _.(-]|$)',stem)
    if m:return m.group(1)
    return ''
def classify(paths):
    """Use full names as anchors; ambiguous prefixes are NEVER assigned silently."""
    anchors=set()
    names={p:get_name(p) for p in paths}
    for p,n in names.items():
        if len(n)>=3 and not n.endswith('0'):
            anchors.add(n)
    mapping={};unmatched=[]
    for p,n in names.items():
        if not n:
            unmatched.append((p,'파일명에서 이름 확인 불가'));continue
        if n in anchors:
            mapping[p]=n;continue
        prefix=n[:2]
        matches=[a for a in anchors if a.startswith(prefix) and (a.startswith(n) or n.endswith('0'))]
        if len(matches)==1:
            mapping[p]=matches[0]
        elif len(matches)>1:
            unmatched.append((p,'같은 이름 앞부분을 가진 사람이 여러 명'))
        else:
            unmatched.append((p,'전체 이름을 확인할 수 없음'))
    return mapping,unmatched

class SorterWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent)
        self.title('서류멍 | 사람별 폴더 자동 정리')
        self.geometry('970x690')
        self.folders=[]
        self.assignments={}
        self.unmatched=[]
        self.copying=False
        self.recurse=tk.BooleanVar(value=False)
        wrap=ttk.Frame(self,padding=14);wrap.pack(fill='both',expand=True)
        ttk.Label(wrap,text='🐶 사람별 폴더 정리',font=('Malgun Gothic',17,'bold')).pack(anchor='w')
        ttk.Label(wrap,text='원본은 그대로 보관하고, 확인된 서류만 새 폴더에 복사합니다. 이름 앞 두 글자만으로는 확정하지 않습니다.').pack(anchor='w',pady=5)
        top=ttk.Frame(wrap);top.pack(fill='x',pady=6)
        ttk.Button(top,text='원본 폴더 추가',command=self.add).pack(side='left')
        ttk.Button(top,text='선택 제거',command=self.remove).pack(side='left',padx=5)
        ttk.Button(top,text='목록 비우기',command=self.clear).pack(side='left')
        ttk.Checkbutton(top,text='하위 폴더도 포함',variable=self.recurse).pack(side='right')
        self.folder_list=tk.Listbox(wrap,height=4,selectmode='extended')
        self.folder_list.pack(fill='x')
        dest=ttk.Frame(wrap);dest.pack(fill='x',pady=9)
        self.dest=tk.StringVar()
        ttk.Label(dest,text='결과 위치:').pack(side='left')
        ttk.Entry(dest,textvariable=self.dest).pack(side='left',fill='x',expand=True,padx=6)
        ttk.Button(dest,text='선택',command=self.pick_dest).pack(side='right')
        buttons=ttk.Frame(wrap);buttons.pack(fill='x',pady=5)
        ttk.Button(buttons,text='1. 분류 미리보기',command=self.preview).pack(side='left')
        self.copy_btn=ttk.Button(buttons,text='2. 확인 후 폴더 생성 및 복사',command=self.copy,state='disabled')
        self.copy_btn.pack(side='left',padx=10)
        ttk.Button(buttons,text='결과 폴더 열기',command=self.open_dest).pack(side='left')
        self.status=tk.StringVar(value='먼저 원본 폴더와 결과 저장 위치를 선택하세요.')
        ttk.Label(wrap,textvariable=self.status).pack(anchor='w',pady=5)
        cols=('file','person','result')
        self.table=ttk.Treeview(wrap,columns=cols,show='headings',height=16)
        for c,title,width in [('file','원본 파일',480),('person','분류할 사람',130),('result','상태',270)]:
            self.table.heading(c,text=title);self.table.column(c,width=width)
        self.table.pack(fill='both',expand=True)
        ttk.Label(wrap,text='미분류 파일도 미분류 폴더에 복사합니다. 원본 파일은 절대 이동하거나 삭제하지 않습니다.').pack(anchor='w',pady=7)
    def add(self):
        folder=filedialog.askdirectory(parent=self,title='서류가 있는 폴더 선택')
        if folder and Path(folder) not in self.folders:
            self.folders.append(Path(folder));self.folder_list.insert('end',folder);self.invalidate()
    def remove(self):
        for i in reversed(self.folder_list.curselection()):
            self.folder_list.delete(i);self.folders.pop(i)
        self.invalidate()
    def clear(self):
        self.folders=[];self.folder_list.delete(0,'end');self.invalidate()
    def invalidate(self):
        self.assignments={};self.unmatched=[];self.copy_btn.configure(state='disabled')
    def pick_dest(self):
        dest=filedialog.askdirectory(parent=self,title='사람별 폴더를 저장할 위치')
        if dest:self.dest.set(dest);self.invalidate()
    def open_dest(self):
        folder=Path(self.dest.get().strip())
        if folder.is_dir():
            os.startfile(str(folder))
        else:messagebox.showwarning('결과 위치 없음','저장 위치를 먼저 선택하세요.',parent=self)
    def preview(self):
        self.invalidate()
        for row in self.table.get_children():self.table.delete(row)
        paths=[];seen=set()
        dest=Path(self.dest.get().strip()).resolve() if self.dest.get().strip() else None
        for root in self.folders:
            if not root.is_dir():continue
            for p in (root.rglob('*') if self.recurse.get() else root.iterdir()):
                if p.is_file() and p.suffix.lower() in EXTS:
                    if dest and (p.resolve()==dest or dest in p.resolve().parents):continue
                    key=str(p.resolve()).casefold()
                    if key not in seen:seen.add(key);paths.append(p)
        if not paths:
            messagebox.showwarning('파일 없음','선택한 폴더에서 PDF·이미지 파일을 찾지 못했어요.',parent=self);return
        self.assignments,self.unmatched=classify(paths)
        for p,n in sorted(self.assignments.items(),key=lambda kv:(kv[1],kv[0].name)):
            self.table.insert('','end',values=(p.name,n,'복사 예정'))
        for p,why in self.unmatched:self.table.insert('','end',values=(p.name,'미분류',why))
        self.status.set(f'총 {len(paths)}개 중 자동 분류 {len(self.assignments)}개 / 확인 필요 {len(self.unmatched)}개')
        self.copy_btn.configure(state='normal' if (self.assignments or self.unmatched) else 'disabled')
    @staticmethod
    def same_content(a,b):
        if a.stat().st_size != b.stat().st_size:return False
        def digest(p):
            h=hashlib.sha256()
            with p.open('rb') as fp:
                for block in iter(lambda:fp.read(1024*1024),b''):h.update(block)
            return h.digest()
        return digest(a)==digest(b)

    def copy(self):
        if self.copying or not (self.assignments or self.unmatched):return
        dest_str=self.dest.get().strip()
        if not dest_str:
            messagebox.showwarning('저장 위치','결과 폴더를 먼저 선택하세요.',parent=self);return
        dest=Path(dest_str)
        if not dest.is_dir():
            messagebox.showwarning('저장 위치','존재하는 결과 저장 폴더를 선택하세요.',parent=self);return
        if any(dest.resolve()==root.resolve() for root in self.folders):
            messagebox.showwarning('저장 위치','원본 폴더와 결과 폴더는 서로 다르게 지정하세요.',parent=self);return
        jobs=[(src,name) for src,name in self.assignments.items()]
        jobs += [(src,'미분류') for src,_ in self.unmatched]
        if not messagebox.askyesno('복사 확인',f'총 {len(jobs)}개 파일을 아래 위치로 복사합니다.\\n{dest}\\n\\n미분류 파일은 미분류 폴더에 모읍니다.\\n원본은 삭제하거나 이동하지 않습니다.',parent=self):return
        self.copying=True;self.copy_btn.configure(state='disabled')
        done=0;skipped=0;errors=[]
        try:
            for src,name in jobs:
                try:
                    target_dir=dest/name
                    target_dir.mkdir(parents=True,exist_ok=True)
                    target=target_dir/src.name
                    if src.resolve()==target.resolve():
                        skipped+=1;continue
                    if target.exists():
                        if self.same_content(src,target):
                            skipped+=1;continue
                        # Different contents but same filename: preserve both.
                        n=2
                        while target.exists():
                            if self.same_content(src,target):break
                            target=target_dir/(src.stem+f' ({n})'+src.suffix);n+=1
                        if target.exists():
                            skipped+=1;continue
                    shutil.copy2(src,target);done+=1
                except OSError as e:errors.append(f'{src.name}: {e}')
        finally:
            self.copying=False
            self.copy_btn.configure(state='normal')
        self.status.set(f'결과 위치: {dest} | 새로 복사 {done}개 / 동일 파일 건너뜀 {skipped}개 / 오류 {len(errors)}개')
        messagebox.showinfo('서류 정리 완료',self.status.get()+'\\n\\n결과 폴더를 열어 확인하세요.'+(('\\n'+'\\n'.join(errors[:3])) if errors else ''),parent=self)
        self.open_dest()
