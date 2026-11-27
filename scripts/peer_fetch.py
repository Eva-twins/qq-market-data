"""下載同業配置追蹤需要的月報 PDF，交給 app/peer_parser.html（與平台同一套解析規則）解析，結果存 data/peer.json。
只存解析後的配置比例，不存 PDF 本身。每天執行；抓到新月份才會更新。"""
import requests,json,re,subprocess,tempfile,os,datetime,sys,time,unicodedata,urllib.parse as up,traceback
from playwright.sync_api import sync_playwright
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36','Accept':'application/pdf,text/html,*/*','Accept-Language':'zh-TW,zh;q=0.9'}
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
today=datetime.date.today();m1=(today.replace(day=1)-datetime.timedelta(days=1));m2=(m1.replace(day=1)-datetime.timedelta(days=1))
MS=[m1.strftime('%Y-%m'),m2.strftime('%Y-%m')]
if os.environ.get('PEER_MS'):MS=os.environ['PEER_MS'].split(',')
CATHAY={'U1':'ACU006','U5':'ACU007','U7':'ACU008','U16':'AIU001','U2':'ABU038','U15':'ABU036','U6':'ABU046','U14':'ABU051','U13':'AWU021','U11':'AMU051','U12':'AMU054','U4':'AMU057','U9':'BSU029','U8':'BSU039','T5':'ACT041'}
CA='https://www.cathaylife.com.tw/cathaylife/-/media/life-insurance/Files/Fund/Report/report_'
FB='https://invest.fubonlife.com.tw/api/publish/assetDiaFile/'
def T8(m):y,x=m.split('-');return 'https://www.twfhclife.com.tw/wp-content/uploads/'+up.quote('月報-臺銀人壽新臺幣精選平衡型投資帳戶-野村-'+str(int(y)-1911)+x)+'.pdf'
SRC={}
for a,c in CATHAY.items():SRC[a]=lambda m,c=c:[CA+c+'?sc_lang=zh-TW']
SRC.update({'U19':lambda m:['https://cardif.moneydj.com/SaveFile/McpDoc/DMA072-2.pdf'],'T8':lambda m:[T8(m)],'T4':lambda m:['https://pcaliferwd.moneydj.com/SaveFile/monthly/tfkg_'+m.replace('-','')+'.pdf'],
 'T9':lambda m:[FB+'ffe3df5f-bca6-4c29-8958-b8196580718f.pdf'],'T10':lambda m:[FB+'9d8c5970-21e7-41f3-bbe8-9f746c2891be.pdf'],'T7':lambda m:[FB+'767b931c-d51c-410c-a8a4-96f0d28a9616.pdf'],'T2':lambda m:[FB+'2e3c4f9b-687f-491f-a9c9-f0215c7e0164.pdf'],
 'U20':lambda m:['https://178.taiwanlife.com/SaveFile/tempfile/ctbclife/TA101/M014/M014.pdf'],'U10':lambda m:['https://kgilife.moneydj.com/SaveFile/TFSO_Monthly.pdf'],
 'U18':lambda m:['https://sklife.moneydj.com/SaveFile/MonthReport/K025/'+m.replace('-','')+'-'+up.quote('台新投信鑫動能投資管理帳戶月報-含資產撥回組成表')+'.pdf']})
MONTHLY={'T8','T4','U18'}
# 三商美邦（MoneyDJ 外框頁）：嘗試從頁面找出 PDF 連結
MDJ={'U3':'MFD00010','U17':'MFD00020','T1':'MDI00010'};DEBUG={}
def mdj_links(aid,code):
    outs=[]
    for u in ['https://mlivul.moneydj.com/w/wfv/wfv01.djhtm?a='+code,'https://mlivul.moneydj.com/W/WFV/WFV01.DJHTM?A='+code,'https://mlivul.moneydj.com/main.html?sUrl=%2FW%2FWFV%2FWFV01.DJHTM%3FA%3D'+code]:
        try:
            r=requests.get(u,headers=UA,timeout=40);h=r.text
            ls=[up.urljoin(u,x) for x in re.findall(r'(?:href|src)=["\']([^"\']+)["\']',h) if re.search(r'\.pdf|SaveFile|savefile|download',x,re.I)]
            DEBUG.setdefault(aid,[]).append({'page':u,'status':r.status_code,'len':len(r.text),'links':ls[:10],'iframes':re.findall(r'<iframe[^>]+src=["\']([^"\']+)',h)[:5]})
            outs+=ls
        except Exception as e:DEBUG.setdefault(aid,[]).append({'page':u,'error':str(e)[:120]})
    return outs
def pats(m):
    y,x=m.split('-');r=int(y)-1911;mm=int(x);return [f'{y}/{x}',f'{y}-{x}',f'{y}.{x}',f'{y}年{mm}月',f'{y}年{x}月',f'{r}年{mm}月',f'{r}/{x}',f'{r}.{x}',f'{y}/{mm}',f'{y}.{mm}',f'{r}.{mm}']
def month_of(tx):
    t=unicodedata.normalize('NFKC',tx);t=re.sub(r'\s+','',t)[:6000]
    for m in MS:
        if any(k in t for k in pats(m)):return m
    return None
def get_pdf(url):
    r=requests.get(url,headers=UA,timeout=60)
    return r.content if r.status_code==200 and r.content[:5]==b'%PDF-' else None
def text_of(b):
    with tempfile.NamedTemporaryFile(suffix='.pdf',delete=False) as f:f.write(b);p=f.name
    try:return subprocess.run(['pdftotext','-layout','-l','3',p,'-'],capture_output=True,text=True,timeout=60).stdout
    finally:os.unlink(p)
# 富邦人壽（T2、T7、T9、T10）：月報檔的網址會隨月份換新，固定網址只會拿到舊檔。
# 每次先開基金頁，從頁面（連結或背景 API）找出「月報_…_民國年月」對應的檔案網址，找不到才退回固定網址。
FBPAGE={'T2':'https://invest.fubonlife.com.tw/funds/overview/DIA/47/ACD5','T7':'https://invest.fubonlife.com.tw/funds/overview/DIA/45/FBD12','T10':'https://invest.fubonlife.com.tw/funds/overview/DIA/45/FBD6','T9':'https://invest.fubonlife.com.tw/funds/overview/DIA/43/DSD3'}
UUID=re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',re.I)
def roc(m):y,x=m.split('-');return str((int(y)-1911)*100+int(x))
def walk(o,out):
    if isinstance(o,dict):
        vs=[v for v in o.values() if isinstance(v,str)]
        nm=[v for v in vs if re.search(r'月報',v) and re.search(r'11\d{3}',v)]
        if nm:
            ref=[v for v in vs if v not in nm and (UUID.search(v) or 'assetDiaFile' in v)]
            out.append((nm[0],ref[0] if ref else None,list(o.items())[:8]))
        for v in o.values():walk(v,out)
    elif isinstance(o,list):
        for v in o:walk(v,out)
def discover_fb():
    found={}
    try:
        with sync_playwright() as p:
            br=p.chromium.launch();ctx=br.new_context(user_agent=UA['User-Agent'],locale='zh-TW')
            for aid,url in FBPAGE.items():
                dbg={'url':url,'anchors':[],'api':[],'reqs':[]};DEBUG['fb_'+aid]=dbg
                pg=ctx.new_page();apis=[];reqs=[]
                def on_resp(r,apis=apis):
                    try:
                        if 'json' in (r.headers.get('content-type') or ''):apis.append((r.url,r.text()))
                    except Exception:pass
                pg.on('response',on_resp);pg.on('request',lambda r,reqs=reqs:reqs.append(r.url) if 'assetDiaFile' in r.url else None)
                try:
                    pg.goto(url,wait_until='networkidle',timeout=60000);pg.wait_for_timeout(2500)
                    anchors=pg.evaluate("""()=>[...document.querySelectorAll('a,button,[role=link],li,div')].filter(e=>/月報_/.test(e.innerText||'')&&(e.innerText||'').length<80).map(e=>{const a=e.closest('a')||e.querySelector('a');return {t:(e.innerText||'').trim(),h:a?a.href:(e.href||null)}})""")
                    dbg['anchors']=anchors[:12];dbg['reqs']=reqs[:5]
                    cands=[]
                    for t,h in [(x['t'],x['h']) for x in anchors]:
                        m=re.search(r'月報_.*?(11\d{3})',t)
                        if m and h and UUID.search(h):cands.append((m.group(1),h))
                    for u,txt in apis:
                        try:j=json.loads(txt)
                        except Exception:continue
                        out=[];walk(j,out)
                        for nm,ref,items in out:
                            dbg['api'].append({'u':u[:100],'nm':nm,'ref':ref,'items':str(items)[:300]})
                            m=re.search(r'(11\d{3})',nm)
                            if ref:cands.append((m.group(1),ref if ref.startswith('http') else FB+UUID.search(ref).group(0)+'.pdf'))
                    for code,h in cands:
                        if code in [roc(x) for x in MS]:found.setdefault(aid,[]).append((code,h))
                    found[aid]=[h for c,h in sorted(found.get(aid,[]),key=lambda z:-int(z[0]))]
                except Exception as e:dbg['error']=type(e).__name__+': '+str(e)[:120]
                pg.close()
            br.close()
    except Exception as e:DEBUG['fb_error']=str(e)[:150]
    return found
FBFOUND=discover_fb() if not os.environ.get('PEER_TEST_DIR') else {}

# 富邦 T7／T10：配置圖是圖片，用 OCR 讀圖上的各類別比例，並用文字段落的合計交叉驗證；驗證不過就不採用（維持沿用上月＋提示手動）
import difflib,glob,shutil
OCRL=[('全球非投資等級債券','c_hy'),('全球投資等級債券','c_ig'),('不動產證券化型','c_sec'),('不動產證券化','c_sec'),('新興市場債','c_emd'),('美國公債','c_gov'),('約當現金','c_cash'),('貨幣市場','c_mm'),('全球股票','c_gs'),('美國股票','c_us'),('歐洲股票','c_eu'),('日本股票','c_jp'),('亞洲股票','c_asia'),('台灣股票','c_tw')]
CMAP={'c_gs':'DM','c_us':'DM','c_eu':'DM','c_jp':'DM','c_asia':'EM','c_sec':'SEC','c_tw':'TW','c_ig':'IG','c_gov':'IG','c_hy':'HY','c_emd':'EMD','c_cash':'CASH','c_mm':'CASH'}
def ocr_parse(txt):
    got={};bad=[]
    for line in unicodedata.normalize('NFKC',txt).splitlines():
        nums=re.findall(r'(\d{1,3}\.\d{2})',line)
        if not nums:continue
        lab=re.sub(r'[^\u4e00-\u9fff]','',line)
        if not lab:continue
        key=None
        for l,k in sorted(OCRL,key=lambda x:-len(x[0])):
            if l in lab:key=k;break
        if not key:
            m=difflib.get_close_matches(lab,[l for l,_ in OCRL],n=1,cutoff=0.7)
            if m:key=dict(OCRL)[m[0]]
        if key and key not in got:got[key]=float(nums[-1])
        elif not key:bad.append((lab,float(nums[-1])))
    return got,bad
def ocr_chart(b,ent,aid):
    d=tempfile.mkdtemp();pdf=os.path.join(d,'a.pdf');open(pdf,'wb').write(b)
    subprocess.run(['pdfimages','-png','-l','3',pdf,os.path.join(d,'im')],capture_output=True,timeout=120)
    subprocess.run(['pdftoppm','-r','300','-png','-l','3',pdf,os.path.join(d,'pg')],capture_output=True,timeout=180)
    cands=sorted(glob.glob(d+'/im*.png'),key=os.path.getsize,reverse=True)[:6]+sorted(glob.glob(d+'/pg*.png'))
    r=ent.get('raw',{}).get('raw',{});best=None;dbg=[]
    try:
        from PIL import Image
        ups=[]
        for f in cands:
            if os.path.basename(f).startswith('im'):
                im=Image.open(f).convert('RGB')
                for z in (2,3):
                    g=f[:-4]+f'_x{z}.png';im.resize((im.width*z,im.height*z),Image.LANCZOS).save(g);ups.append(g)
        cands=cands+ups
    except Exception as e:dbg.append('PIL:'+str(e)[:60])
    for f in cands:
        for psm in ('6',):
            try:txt=subprocess.run(['tesseract',f,'-','-l','chi_tra+eng','--psm',psm],capture_output=True,text=True,timeout=120).stdout
            except Exception as e:dbg.append(str(e)[:60]);continue
            got,bad=ocr_parse(txt);tot=sum(got.values())
            stk=sum(got.get(k,0) for k in ('c_gs','c_us','c_eu','c_jp','c_asia','c_sec','c_tw'));bond=sum(got.get(k,0) for k in ('c_ig','c_gov','c_hy','c_emd'));cash=got.get('c_cash',0)+got.get('c_mm',0)
            ok=len(got)>=8 and abs(tot-100)<=1.2 and not any(v>0.3 for _,v in bad)
            if ok and isinstance(r.get('stk'),(int,float)) and abs(stk-r['stk'])>0.6:ok=False
            if ok and isinstance(r.get('bond'),(int,float)) and abs(bond-r['bond'])>0.6:ok=False
            dbg.append({'f':os.path.basename(f),'psm':psm,'n':len(got),'sum':round(tot,2),'stk':round(stk,2),'bond':round(bond,2),'bad':bad[:4],'ok':ok})
            if ok and (best is None or abs(tot-100)<abs(sum(best.values())-100)):best=got;DEBUG['ocr_text_'+aid]=txt[:900]
    DEBUG['ocr_'+aid]=dbg[:14];shutil.rmtree(d,ignore_errors=True)
    return best
tmp=tempfile.mkdtemp();jobs=[];log=[]
TESTDIR=os.environ.get('PEER_TEST_DIR')
if TESTDIR:
    import glob
    for i,f in enumerate(sorted(glob.glob(TESTDIR+'/*.pdf'))):
        b=open(f,'rb').read();m=month_of(text_of(b))
        if m:
            path=os.path.join(tmp,f'T{i}__{m}.pdf');open(path,'wb').write(b);jobs.append((None,m,path,'local:'+os.path.basename(f)))
        else:log.append('略過 '+os.path.basename(f))
for aid,fn in ([] if TESTDIR else list(SRC.items())+[(a,None) for a in MDJ]):
    cands=[]
    if fn:
        for m in (MS if aid in MONTHLY else [MS[0]]):cands+=fn(m)
        cands=FBFOUND.get(aid,[])+cands
        if aid in FBFOUND:log.append(f'{aid} 頁面找到 {len(FBFOUND[aid])} 個月報網址')
    else:cands=mdj_links(aid,MDJ[aid])
    done=False
    for u in dict.fromkeys(cands):
        try:b=get_pdf(u)
        except Exception as e:log.append(f'{aid} 下載失敗 {u[:80]} {type(e).__name__}');continue
        if not b:log.append(f'{aid} 非PDF或404 {u[:90]}');continue
        m=month_of(text_of(b))
        if not m:log.append(f'{aid} 月份不符（不是 {MS[0]}／{MS[1]}）{u[:70]}');continue
        if aid in ('T7','T10'):tx=text_of(b);DEBUG['scale_'+aid]={'len':len(tx),'hit':[re.sub(r'\s+',' ',l.strip())[:160] for l in tx.splitlines() if re.search(r'規模|百萬|NT\$|億|淨資產|資產總',l)][:10],'head':[re.sub(r'\s+',' ',l.strip())[:100] for l in tx.splitlines() if l.strip()][:12]}
        path=os.path.join(tmp,f'{aid}__{m}.pdf');open(path,'wb').write(b);jobs.append((aid,m,path,u));log.append(f'{aid} OK {m} {len(b)//1024}KB');done=True;break
    if not done:log.append(f'{aid} 沒有取得新月報')
old={'months':{}}
try:old=json.load(open(os.path.join(ROOT,'data/peer.json'),encoding='utf8'))
except Exception:pass
months=old.get('months',{});new=0
if jobs:
    with sync_playwright() as p:
        br=p.chromium.launch();pg=br.new_page()
        pg.goto('file://'+os.path.join(ROOT,'app/peer_parser.html'));pg.evaluate("localStorage.clear()");pg.reload();pg.wait_for_timeout(1500)
        pg.click('#mods [data-mod=peer]');pg.wait_for_timeout(300);pg.click('#tabs [data-t=import]');pg.wait_for_timeout(500)
        for aid,m,path,u in jobs:
            try:
                pg.fill('#month',m);pg.dispatch_event('#month','change');pg.wait_for_timeout(300)
                pg.set_input_files('#file',path)
                ent=None
                for _ in range(60):
                    pg.wait_for_timeout(500)
                    st=pg.evaluate("JSON.parse(localStorage.getItem('qq_peer_v1')||'{}').entries||{}")
                    hit=[(k,v) for k,v in (st.get(m) or {}).items() if v.get('file')==os.path.basename(path)]
                    if hit:rid,ent=hit[0];break
                if not ent:log.append(f'{aid} 解析沒有產生結果');continue
                if aid and rid!=aid:log.append(f'{aid} 下載到的是 {rid} 的月報，已略過');continue
                aid=rid
                ent['notes']=[n for n in (ent.get('notes') or []) if '月報內容未見' not in n]
                if aid in ('T7','T10'):
                    try:
                        ch=ocr_chart(open(path,'rb').read(),ent,aid)
                        if ch:
                            ent['raw']['raw'].update(ch);nb={k:0.0 for k in ('DM','EM','SEC','TW','IG','HY','EMD','CASH')}
                            for k,v in ch.items():nb[CMAP[k]]+=v
                            ent['b']={k:round(v,4) for k,v in nb.items()};ent['notes']=['依月報配置圖 OCR 讀取（圖表合計 %.2f%%，已與文字段落的股／債／現金合計交叉驗證），請與圖表核對'%sum(ch.values())];log.append(f'{aid} 配置圖 OCR 成功 {len(ch)} 類')
                        else:log.append(f'{aid} 配置圖 OCR 未通過驗證，沿用上月比例')
                    except Exception as e:log.append(f'{aid} OCR 錯誤 {type(e).__name__}: {str(e)[:80]}')
                ent.update(src='auto',fetched=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='minutes'),url=u,file=os.path.basename(u.split('?')[0]) or aid)
                prev=(months.get(m) or {}).get(aid)
                if not prev or prev.get('b')!=ent['b']:new+=1
                months.setdefault(m,{})[aid]=ent;log.append(f'{aid} 解析 {m} 合計 {round(sum(ent["b"].values()),1)}')
            except Exception as e:log.append(f'{aid} 解析錯誤 {type(e).__name__}: {str(e)[:100]}')
        br.close()
out={'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='minutes'),'months':months}
if TESTDIR:json.dump(out,open('/tmp/peer_test.json','w',encoding='utf8'),ensure_ascii=False);print('\n'.join(log));sys.exit()
json.dump(out,open(os.path.join(ROOT,'data/peer.json'),'w',encoding='utf8'),ensure_ascii=False,separators=(',',':'))
json.dump({'at':out['updated'],'log':log,'mdj':DEBUG},open(os.path.join(ROOT,'data/peer_fetch_log.json'),'w',encoding='utf8'),ensure_ascii=False,indent=1)
print('\n'.join(log));print('新增或變動',new)
