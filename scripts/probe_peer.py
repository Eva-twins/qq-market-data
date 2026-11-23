"""只探測、不解析：試著下載同業配置追蹤用的月報 PDF，記錄哪些抓得到。結果寫入 data/probe_peer.json"""
import requests,json,re,subprocess,tempfile,os,datetime,urllib.parse as up
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept':'application/pdf,text/html,*/*','Accept-Language':'zh-TW,zh;q=0.9'}
today=datetime.date.today();m1=(today.replace(day=1)-datetime.timedelta(days=1));m2=(m1.replace(day=1)-datetime.timedelta(days=1))
MS=[m1.strftime('%Y-%m'),m2.strftime('%Y-%m')]
CATHAY={'U1':'ACU006','U5':'ACU007','U7':'ACU008','U16':'AIU001','U2':'ABU038','U15':'ABU036','U6':'ABU046','U14':'ABU051','U13':'AWU021','U11':'AMU051','U12':'AMU054','U4':'AMU057','U9':'BSU029','U8':'BSU039','T5':'ACT041'}
CA='https://www.cathaylife.com.tw/cathaylife/-/media/life-insurance/Files/Fund/Report/report_'
MDJ={'U3':'MFD00010','U17':'MFD00020','T1':'MDI00010'};MB='https://mlivul.moneydj.com/main.html?sUrl=%2FW%2FWFV%2FWFV01.DJHTM%3FA%3D'
FB='https://invest.fubonlife.com.tw/api/publish/assetDiaFile/'
def T8(m):y,x=m.split('-');return 'https://www.twfhclife.com.tw/wp-content/uploads/'+up.quote('月報-臺銀人壽新臺幣精選平衡型投資帳戶-野村-'+str(int(y)-1911)+x)+'.pdf'
DIR={'U19':lambda m:'https://cardif.moneydj.com/SaveFile/McpDoc/DMA072-2.pdf','T8':T8,'T4':lambda m:'https://pcaliferwd.moneydj.com/SaveFile/monthly/tfkg_'+m.replace('-','')+'.pdf',
 'T9':lambda m:FB+'ffe3df5f-bca6-4c29-8958-b8196580718f.pdf','T10':lambda m:FB+'9d8c5970-21e7-41f3-bbe8-9f746c2891be.pdf','T7':lambda m:FB+'767b931c-d51c-410c-a8a4-96f0d28a9616.pdf','T2':lambda m:FB+'2e3c4f9b-687f-491f-a9c9-f0215c7e0164.pdf',
 'U20':lambda m:'https://178.taiwanlife.com/SaveFile/tempfile/ctbclife/TA101/M014/M014.pdf','U10':lambda m:'https://kgilife.moneydj.com/SaveFile/TFSO_Monthly.pdf',
 'U18':lambda m:'https://sklife.moneydj.com/SaveFile/MonthReport/K025/'+m.replace('-','')+'-'+up.quote('台新投信鑫動能投資管理帳戶月報-含資產撥回組成表')+'.pdf'}
MONTHLY={'T8','T4','U18'}
def pats(m):
    y,x=m.split('-');r=int(y)-1911;mm=int(x);return [f'{y}/{x}',f'{y}-{x}',f'{y}.{x}',f'{y}年{mm}月',f'{y}年{x}月',f'{r}年{mm}月',f'{r}/{x}',f'{r}.{x}',f'{y}{x}',f'{r}{x}']
def probe(aid,url,month):
    o={'id':aid,'url':url,'month':month}
    try:
        r=requests.get(url,headers=UA,timeout=40,allow_redirects=True)
        o.update(status=r.status_code,final=r.url if r.url!=url else None,ctype=r.headers.get('content-type'),size=len(r.content),lastmod=r.headers.get('last-modified'),is_pdf=r.content[:5]==b'%PDF-')
        if o['is_pdf']:
            with tempfile.NamedTemporaryFile(suffix='.pdf',delete=False) as f:f.write(r.content);p=f.name
            try:
                tx=subprocess.run(['pdftotext','-layout','-l','3',p,'-'],capture_output=True,text=True,timeout=60).stdout
                o['text_len']=len(tx);o['month_hits']={mm:[k for k in pats(mm) if k in tx][:3] for mm in MS}
                o['head']=re.sub(r'\s+',' ',tx[:160])
            finally:os.unlink(p)
        else:
            o['head']=re.sub(r'\s+',' ',r.text[:200]) if 'text' in (o['ctype'] or '') else None
            o['pdf_links']=re.findall(r'["\'(]([^"\'()\s]+\.pdf[^"\'()\s]*)',r.text)[:8] if 'text' in (o['ctype'] or '') else []
    except Exception as e:o['error']=f'{type(e).__name__}: {str(e)[:160]}'
    return o
res=[]
for a,c in CATHAY.items():res.append(probe(a,CA+c+'?sc_lang=zh-TW',None))
for a,f in DIR.items():
    for m in (MS if a in MONTHLY else [None]):res.append(probe(a,f(m or MS[0]),m))
for a,c in MDJ.items():res.append(probe(a,MB+c,None))
os.makedirs('data',exist_ok=True)
json.dump({'at':datetime.datetime.utcnow().isoformat()+'Z','months':MS,'results':res},open('data/probe_peer.json','w',encoding='utf8'),ensure_ascii=False,indent=1)
for o in res:print(o['id'],o.get('month') or '-',o.get('status'),o.get('is_pdf'),o.get('size'),o.get('lastmod'),'hits',{k:bool(v) for k,v in (o.get('month_hits') or {}).items()},o.get('error') or '')
