# -*- coding: utf-8 -*-
"""Local-only document extraction. Never uploads or modifies source documents."""
import os, re, queue, threading, traceback, json, urllib.request, hashlib, zipfile, tempfile, shutil
from pathlib import Path
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

EXTS={'.pdf','.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'}
KINDS={'contract':'근로계약서','bank':'통장사본','id':'신분증사본'}
DEFAULT={'contract':'근로계약서,근로 계약서','bank':'통장,계좌','id':'신분증,주민등록증,운전면허증'}
FIELDS={'name':'이름','resident':'주민등록번호 전체','bank':'은행명','account':'계좌번호','contract':'근로계약서 제출','bank_file':'통장사본 제출','id_file':'신분증사본 제출','status':'검토 상태','sources':'원본 파일'}
BANKS=['KB국민은행','국민은행','신한은행','우리은행','하나은행','NH농협은행','농협은행','IBK기업은행','기업은행','카카오뱅크','케이뱅크','토스뱅크','부산은행','대구은행','광주은행','전북은행','경남은행','제주은행','수협은행','우체국','새마을금고','신협','저축은행','SC제일은행','산업은행']
def norm(s):return re.sub(r'\s+','',s).lower()
def detect(path,rules):
    hits=[k for k,v in rules.items() if any(norm(t) in norm(path.stem) for t in v if t.strip())]
    return hits[0] if len(hits)==1 else ''
def file_name(path,kind):
    if kind=='contract':
        m=re.search(r'_([가-힣]{2,5})_\(',path.stem)
    else:m=re.match(r'^([가-힣]{2,5})(?=[ _\-(.]|$)',path.stem)
    return m.group(1) if m else ''
def read_text(path):
    import fitz
    from PIL import Image, ImageOps
    import pytesseract
    exe=Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    if os.name=='nt' and exe.exists():pytesseract.pytesseract.tesseract_cmd=str(exe)
    def ocr(im):
        return pytesseract.image_to_string(ImageOps.exif_transpose(im).convert('RGB'),lang='kor+eng')
    if path.suffix.lower()=='.pdf':
        parts=[]
        with fitz.open(str(path)) as pdf:
            for page in pdf:
                t=page.get_text(sort=True)
                # Some PDFs contain selectable labels but the resident number is drawn as an image.
                # Retry OCR when the text layer does not contain a reliable resident-number candidate.
                if parse_resident(t):
                    parts.append(t)
                else:
                    try:
                        px=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False)
                        raster=Image.frombytes('RGB',(px.width,px.height),px.samples)
                        parts.append(t+'\n'+ocr(raster))
                    except Exception:
                        if t.strip():parts.append(t)
                        else:raise
        return '\n'.join(parts)
    with Image.open(path) as im:return ocr(im)

def parse_resident(text):
    """Extract possible RRNs only near their label; return unique 6-7 formatted values.

    Handles line breaks, unicode dashes and spaced OCR digits. Does not validate identity.
    """
    labels=re.compile(r'주\s*민\s*(?:등\s*록\s*)?(?:번\s*호|번\s*호\s*:)'
                      r'|주\s*민\s*등\s*록\s*번\s*호',re.I)
    numbers=re.compile(r'(?<!\d)(?:\d[ \t\r\n\u00a0]*){6}[-–—−‐‑﹣－]?'
                       r'[ \t\r\n\u00a0]*(?:\d[ \t\r\n\u00a0]*){7}(?!\d)')
    matches=[]
    for label in labels.finditer(text):
        area=text[label.end():label.end()+180]
        for m in numbers.finditer(area):
            # Stop at next unrelated field label; avoid concatenating multiple fields.
            context=area[:m.start()]
            if re.search(r'\b(?:전화번호|연락처|주소|계좌번호)\s*[:：]',context):break
            digits=re.sub(r'\D','',m.group())
            if len(digits)==13 and digits[6] in '12345678':
                matches.append(digits[:6]+'-'+digits[6:])
                break
    # Independently detect explicitly hyphenated RRNs when the PDF strips the label.
    for m in re.finditer(r'(?<!\d)(\d{6})\s*[-–—−‐‑﹣－]\s*([1-8]\d{6})(?!\d)',text):
        matches.append(m.group(1)+'-'+m.group(2))
    return list(dict.fromkeys(matches))

def parse_bank(text):
    compact=norm(text)
    bs=[b for b in BANKS if norm(b) in compact]
    bank=max(bs,key=len) if bs else ''
    accounts=[];lines=text.splitlines()
    for i,line in enumerate(lines):
        if re.search(r'계좌|account|acct|예금',line,re.I):
            area=' '.join(lines[max(0,i-1):min(len(lines),i+3)])
            for m in re.finditer(r'(?<!\d)\d[\d\s-]{7,25}\d(?!\d)',area):
                raw=re.sub(r'\s+','',m.group());digits=re.sub(r'\D','',raw)
                if 9<=len(digits)<=16 and not digits.startswith('010') and len(digits)!=13:accounts.append(raw)
    accounts=list(dict.fromkeys(accounts))
    return bank,accounts

def analyze(files,rules,selected,notify):
    entries=[];full=set();errors=[]
    for p in files:
        kind=detect(p,rules)
        n=file_name(p,kind) if kind else ''
        entries.append((p,kind,n))
        if kind in ('bank','id') and n:full.add(n)
    people=defaultdict(lambda:defaultdict(list)); unmatched=[]
    for p,k,n in entries:
        if not k:unmatched.append((str(p),'문서 종류 키워드 미일치 또는 중복'));continue
        if not n:unmatched.append((str(p),'파일명에서 이름 확인 불가'));continue
        if k=='contract':
            candidates=sorted(x for x in full if x.startswith(n))
            if len(candidates)>1:
                unmatched.append((str(p),f'계약서 이름 {n}: 전체 이름 후보 여러 명, 자동 연결 제외'));continue
            # Keep unmatched partial-name contracts as standalone review rows, rather than
            # silently skipping their resident-number extraction.
            n=candidates[0] if candidates else n
        people[n][k].append(p)
    rows=[];total=sum(len(x.get('contract',[]))*(('resident' in selected)) + len(x.get('bank',[]))*(('bank' in selected or 'account' in selected)) for x in people.values());done=0
    for name,kinds in sorted(people.items()):
        values={'name':name,'resident':'','bank':'','account':'','contract':'있음' if kinds['contract'] else '미제출','bank_file':'있음' if kinds['bank'] else '미제출','id_file':'있음' if kinds['id'] else '미제출','status':'','sources':'\n'.join(str(p) for ps in kinds.values() for p in ps)}
        notes=[]
        if 'resident' in selected:
            candidates=[]
            for p in kinds['contract']:
                notify('status',f'주민번호 분석: {p.name}')
                try:candidates.extend(parse_resident(read_text(p)))
                except Exception as e:notes.append(f'계약서 판독 실패 ({p.name}): {e}')
                done+=1;notify('progress',(done,max(1,total)))
            candidates=list(dict.fromkeys(candidates))
            if len(candidates)==1:values['resident']=candidates[0]
            elif len(candidates)>1:notes.append('주민번호 후보 여러 개: 직접 확인')
            elif kinds['contract']:notes.append('주민번호 추출 실패: 직접 확인')
        if 'bank' in selected or 'account' in selected:
            banks=[];accounts=[]
            for p in kinds['bank']:
                notify('status',f'통장 분석: {p.name}')
                try:
                    b,a=parse_bank(read_text(p))
                    if b:banks.append(b)
                    accounts.extend(a)
                except Exception as e:notes.append(f'통장 판독 실패 ({p.name}): {e}')
                done+=1;notify('progress',(done,max(1,total)))
            banks=list(dict.fromkeys(banks));accounts=list(dict.fromkeys(accounts))
            if len(banks)==1:values['bank']=banks[0]
            if len(accounts)==1:values['account']=accounts[0]
            if len(banks)>1 or len(accounts)>1:notes.append('은행/계좌 후보 여러 개: 직접 확인')
            if kinds['bank'] and ('bank' in selected and not values['bank'] or 'account' in selected and not values['account']):notes.append('통장 정보 일부 미확정')
        values['status']='; '.join(notes) if notes else '원본 대조 필요'
        rows.append(values)
    return rows,unmatched

class App(tk.Tk):
    def __init__(self):
        super().__init__();self.title('서류멍 - 문서 정보 추출기');self.geometry('1040x820');self.minsize(850,650)
        self.files=[];self.folders=[];self.scan_subdirs=tk.BooleanVar(value=False);self.rows=[];self.unmatched=[];self.q=queue.Queue();self.out=tk.StringVar(value=str(Path.home()/'Documents'))
        self.rules={k:tk.StringVar(value=v) for k,v in DEFAULT.items()}
        self.fields={k:tk.BooleanVar(value=k in ('name','resident','bank','account','status')) for k in FIELDS}
        self.status=tk.StringVar(value='분석할 폴더를 추가하세요. 원본 파일은 변경하지 않습니다.')
        self.build();self.after(120,self.poll);self.after(1600,self.check_update)
        try:self.iconbitmap(str((Path(getattr(__import__('sys'), '_MEIPASS', Path(__file__).resolve().parent)) / 'dog.ico')))
        except Exception:pass
    def build(self):
        wrap=ttk.Frame(self,padding=12);wrap.pack(fill='both',expand=True)
        bar=ttk.Frame(wrap);bar.pack(fill='x')
        ttk.Button(bar,text='폴더 추가',command=self.add_folder).pack(side='left')
        ttk.Button(bar,text='선택 폴더 제거',command=self.remove_folder).pack(side='left',padx=6)
        ttk.Button(bar,text='폴더 목록 비우기',command=self.clear_folders).pack(side='left')
        ttk.Button(bar,text='업데이트 확인',command=self.check_update).pack(side='right')
        frm=ttk.LabelFrame(wrap,text='분석할 폴더 (여러 개 추가 가능)');frm.pack(fill='both',expand=True,pady=6)
        self.folderlist=tk.Listbox(frm,selectmode='extended',height=5);self.folderlist.pack(side='left',fill='both',expand=True)
        ttk.Scrollbar(frm,orient='vertical',command=self.folderlist.yview).pack(side='right',fill='y')
        ttk.Checkbutton(wrap,text='하위 폴더도 검색 (기본값: 꺼짐)',variable=self.scan_subdirs).pack(anchor='w')
        ttk.Label(wrap,text='선택한 폴더의 PDF·이미지만 검색하며, 키워드에 해당하지 않는 파일은 분석하지 않습니다.').pack(anchor='w')
        rules=ttk.LabelFrame(wrap,text='문서 종류 판별: 파일명 포함 단어 (쉼표 구분)');rules.pack(fill='x',pady=5)
        for k in KINDS:
            line=ttk.Frame(rules);line.pack(fill='x',padx=8,pady=2);ttk.Label(line,text=KINDS[k],width=14).pack(side='left');ttk.Entry(line,textvariable=self.rules[k]).pack(side='left',fill='x',expand=True)
        fields=ttk.LabelFrame(wrap,text='엑셀로 추출할 항목');fields.pack(fill='x',pady=6)
        for i,(k,label) in enumerate(FIELDS.items()):ttk.Checkbutton(fields,text=label,variable=self.fields[k]).grid(row=i//3,column=i%3,sticky='w',padx=12,pady=4)
        ttk.Label(wrap,text='주의: 주민번호 13자리 전체가 엑셀에 표시됩니다. 업무상 권한 확인 및 접근 제한 필수. 추출값은 반드시 원본과 대조하세요.',foreground='#9A3500').pack(anchor='w',pady=3)
        actions=ttk.Frame(wrap);actions.pack(fill='x',pady=7);self.go=ttk.Button(actions,text='선택 폴더 분석',command=self.start);self.go.pack(side='left');self.save=ttk.Button(actions,text='검토 결과 엑셀 저장',command=self.export,state='disabled');self.save.pack(side='left',padx=9)
        self.progress=ttk.Progressbar(wrap,mode='determinate');self.progress.pack(fill='x');ttk.Label(wrap,textvariable=self.status).pack(anchor='w',pady=4)
        ttk.Label(wrap,text='분석 결과 미리보기 (셀 더블클릭 시 값 수정 가능)').pack(anchor='w')
        table=ttk.Frame(wrap);table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,show='headings',height=8);self.tree.pack(side='left',fill='both',expand=True)
        ys=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);ys.pack(side='right',fill='y');self.tree.configure(yscrollcommand=ys.set)
        self.tree.bind('<Double-1>',self.edit)
    def add_folder(self):
        path=filedialog.askdirectory(title='분석할 폴더 추가')
        if path and Path(path) not in self.folders:
            self.folders.append(Path(path));self.folderlist.insert('end',path)
            self.status.set(f'{len(self.folders)}개 폴더 선택됨. 폴더 추가를 반복하면 됩니다.')
    def remove_folder(self):
        for i in reversed(self.folderlist.curselection()):
            self.folderlist.delete(i);self.folders.pop(i)
    def clear_folders(self):
        self.folders=[];self.folderlist.delete(0,'end')
    def check_update(self):
        def work():
            try:
                import updater
                self.q.put(('update_info',updater.check_for_update()))
            except Exception as ex:self.q.put(('update_error',str(ex)))
        threading.Thread(target=work,daemon=True).start()
    def discover(self,roots,recurse,rules):
        found=[];seen=set()
        for root in roots:
            if not root.is_dir():continue
            iterator=root.rglob('*') if recurse else root.iterdir()
            for p in iterator:
                try:
                    if not p.is_file() or p.suffix.lower() not in EXTS or not detect(p,rules):continue
                    canonical=str(p.resolve()).casefold()
                    if canonical not in seen:seen.add(canonical);found.append(p)
                except (OSError,PermissionError):continue
        return found
    def start(self):
        if not self.folders:messagebox.showwarning('폴더 없음','분석할 폴더를 추가하세요.');return
        selected=[k for k,v in self.fields.items() if v.get()]
        if not selected:messagebox.showwarning('항목 없음','추출할 항목을 하나 이상 체크하세요.');return
        rules={k:[x.strip() for x in v.get().split(',') if x.strip()] for k,v in self.rules.items()};roots=list(self.folders);recurse=self.scan_subdirs.get()
        self.selected=selected;self.go.configure(state='disabled');self.save.configure(state='disabled');self.progress['value']=0
        self.status.set('분석 중...')
        def work():
            try:
                paths=self.discover(roots,recurse,rules)
                self.q.put(('count',len(paths)))
                if not paths:
                    self.q.put(('done',([],[])));return
                self.q.put(('done',analyze(paths,rules,selected,lambda k,v:self.q.put((k,v)))))
            except Exception:self.q.put(('error',traceback.format_exc()))
        threading.Thread(target=work,daemon=True).start()
    def draw(self):
        keys=self.selected;self.tree['columns']=keys
        for k in keys:self.tree.heading(k,text=FIELDS[k]);self.tree.column(k,width=155 if k!='sources' else 300,anchor='w')
        for i in self.tree.get_children():self.tree.delete(i)
        for i,row in enumerate(self.rows):self.tree.insert('','end',iid=str(i),values=[row.get(k,'') for k in keys])
    def edit(self,event):
        row=self.tree.identify_row(event.y);col=self.tree.identify_column(event.x)
        if not row or not col:return
        j=int(col[1:])-1;key=self.selected[j];rect=self.tree.bbox(row,col)
        if not rect:return
        e=ttk.Entry(self.tree);e.insert(0,self.rows[int(row)].get(key,''));e.place(x=rect[0],y=rect[1],width=max(120,rect[2]),height=rect[3]);e.focus_set()
        def finish(_=None):
            if not e.winfo_exists():return
            self.rows[int(row)][key]=e.get();e.destroy();self.draw()
        e.bind('<Return>',finish);e.bind('<FocusOut>',finish)
    def export(self):
        dest=filedialog.asksaveasfilename(title='엑셀 저장',defaultextension='.xlsx',filetypes=[('Excel 통합문서','*.xlsx')],initialfile='서류추출_검토용.xlsx')
        if not dest:return
        try:
            import xlsxwriter
            wb=xlsxwriter.Workbook(dest,{'strings_to_formulas':False,'strings_to_urls':False})
            ws=wb.add_worksheet('서류 추출 결과');header=wb.add_format({'bold':True,'bg_color':'#DCEAF5','border':1});txt=wb.add_format({'num_format':'@','text_wrap':True,'valign':'top'})
            for j,k in enumerate(self.selected):ws.write_string(0,j,FIELDS[k],header);ws.set_column(j,j,45 if k in ('sources','status') else 22,txt)
            for i,row in enumerate(self.rows,1):
                for j,k in enumerate(self.selected):ws.write_string(i,j,str(row.get(k,'')),txt)
            ws.freeze_panes(1,0);ws.autofilter(0,0,max(len(self.rows),1),len(self.selected)-1)
            review=wb.add_worksheet('미분류');review.write_row(0,0,['원본 파일','확인 이유'],header)
            for i,(p,why) in enumerate(self.unmatched,1):review.write_string(i,0,p,txt);review.write_string(i,1,why,txt)
            review.set_column('A:A',100);review.set_column('B:B',60)
            info=wb.add_worksheet('안내');info.set_column('A:A',110)
            for i,s in enumerate(['이 엑셀에는 주민등록번호 13자리 전체 등 민감한 개인정보가 포함될 수 있습니다.','회사에서 보관·처리할 권한이 있는지 확인하고 파일 접근권한을 제한하세요.','OCR 인식 결과는 원본 서류와 반드시 대조하세요. 추출 성공은 진위 확인을 의미하지 않습니다.','추출한 주민등록번호와 계좌번호는 텍스트로 저장됩니다.','원본 파일을 변경·삭제·업로드하지 않습니다.']):info.write_string(i,0,s)
            wb.close();self.status.set(f'저장 완료: {dest}');messagebox.showinfo('저장 완료',f'엑셀을 저장했습니다.\n{dest}')
        except Exception as e:messagebox.showerror('엑셀 오류',str(e))
    def poll(self):
        try:
            while True:
                k,v=self.q.get_nowait()
                if k=='status':self.status.set(v)
                elif k=='count':self.status.set(f'키워드에 맞는 파일 {v}개 검색됨. 분석 중...')
                elif k=='update_info':
                    if v.get('available'):
                        if messagebox.askyesno('서류멍 새 버전',f"새 버전 {v['tag']}이 공개됐어요.\nGitHub 공식 다운로드 페이지를 열까요?"):
                            import webbrowser
                            webbrowser.open(v['url'])
                    else:self.status.set('서류멍 최신 버전 사용 중')
                elif k=='update_error':
                    self.status.set('업데이트 확인 불가 (인터넷 연결 확인)')
                elif k=='progress':self.progress['value']=v[0]*100/max(1,v[1])
                elif k=='done':
                    self.rows,self.unmatched=v;self.draw();self.go.configure(state='normal');self.save.configure(state='normal');self.progress['value']=100
                    self.status.set(f'분석 완료: {len(self.rows)}명 / 미분류 {len(self.unmatched)}개. 미분류 상세는 저장된 엑셀에서 확인하세요.')
                elif k=='error':self.go.configure(state='normal');self.status.set('오류 발생');messagebox.showerror('분석 오류',v[-1800:])
        except queue.Empty:pass
        self.after(120,self.poll)
if __name__=='__main__':App().mainloop()
