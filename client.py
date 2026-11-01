"""Source-preserving Engine 3 preparation. No model values are invented.
Uses Python standard library only. Invoke exporter.mjs on prepared JSON.
"""
import argparse, csv, hashlib, json, posixpath, re, uuid, zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read_xlsx(path,sheet,header_row=1):
    with zipfile.ZipFile(path) as z:
        ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            ss=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        sh=next((s for s in wb.findall('s:sheets/s:sheet',NS) if s.attrib['name']==sheet),None)
        if sh is None: raise ValueError('Select an existing source sheet explicitly')
        relid=sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rel=next(r for r in rels if r.attrib['Id']==relid)
        target=rel.attrib['Target']; target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        rows=[]; formula_cells=[]
        for row in ET.fromstring(z.read(target)).findall('s:sheetData/s:row',NS):
            rn=int(row.attrib['r'])
            if rn<header_row: continue
            vals={}
            for cell in row.findall('s:c',NS):
                ref=cell.attrib['r']; col=re.match('[A-Z]+',ref)[0]; ix=0
                for ch in col: ix=ix*26+ord(ch)-64
                typ=cell.get('t'); v=cell.find('s:v',NS); text=v.text if v is not None else None
                if typ=='s': value=ss[int(text)] if text is not None else None
                elif typ=='inlineStr': value=''.join(cell.find('s:is',NS).itertext())
                elif typ in ('str','e','d'): value=text
                elif typ=='b': value=text=='1'
                else:
                    value=float(text) if text is not None else None
                    if value is not None and value.is_integer(): value=int(value)
                if cell.find('s:f',NS) is not None:
                    formula_cells.append(ref)
                    if value is None: raise ValueError('Source formula without cached value: '+ref)
                vals[ix-1]=value
            if rn==header_row or any(v is not None for v in vals.values()):
                rows.append([vals.get(i) for i in range(max(vals,default=-1)+1)])
        if formula_cells: raise ValueError('Source formulas need an explicit acceptance policy; cells: '+','.join(formula_cells[:20]))
    return rows

def read_table(path,sheet=None,header_row=1):
    if str(path).lower().endswith('.xlsx'): return read_xlsx(path,sheet,header_row)
    with open(path,encoding='utf-8-sig',newline='') as f: return list(csv.reader(f))

def canonical_uuid(v):
    if v is None: raise ValueError('Blank UUID')
    return str(uuid.UUID(str(v).strip().strip('{}')))

def equivalent(a,b):
    if (a is None or a=='') and (b is None or b==''): return True
    if str(a)==str(b): return True
    try: return Decimal(str(a))==Decimal(str(b))
    except InvalidOperation: return False

def prepare(original,new,key,out,sheet=None,header_row=1,expected=87,areas_json=None):
    old=read_table(original,sheet,header_row); extra=read_table(new)
    h=old[0]; nh=extra[0]
    if len(h)!=37 or any(not isinstance(x,str) or x=='' for x in h): raise ValueError('Exactly 37 literal nonblank source headings required')
    if len(set(h))!=37: raise ValueError('Duplicate source headings require explicit mapping')
    if len(nh)!=38 or nh.count('UID')!=1 or [x for x in nh if x!='UID']!=h: raise ValueError('New CSV must equal original 37 headings/order plus UID')
    if key not in h: raise ValueError('UUID key heading missing')
    ki=h.index(key); ni=nh.index(key)
    rows=[r+[None]*(37-len(r)) for r in old[1:]]
    if any(len(r)!=37 for r in rows): raise ValueError('Source row width mismatch')
    if any(len(r)!=38 for r in extra[1:]): raise ValueError('New CSV row width mismatch')
    if len(rows)!=expected or len(extra)-1!=expected: raise ValueError('Expected record count failed')
    keys=[canonical_uuid(r[ki]) for r in rows]; nkeys=[canonical_uuid(r[ni]) for r in extra[1:]]
    if len(set(keys))!=expected or len(set(nkeys))!=expected: raise ValueError('Duplicate UUID keys')
    if set(keys)!=set(nkeys): raise ValueError('UUID sets differ')
    other=dict(zip(nkeys,extra[1:])); exceptions=[]; mapping=[]
    for k,r in zip(keys,rows):
        nr=other[k]; mapping.append([k,nr[nh.index('UID')]])
        for i,col in enumerate(h):
            b=nr[nh.index(col)]
            if not equivalent(r[i],b): exceptions.append([k,col,r[i],b,'Original preserved; discrepancy unresolved'])
    manifest={'original':str(Path(original).resolve()),'original_sha256':digest(original),
        'new_csv':str(Path(new).resolve()),'new_csv_sha256':digest(new),
        'source_rows':len(rows),'new_rows':len(nkeys),'unique_matched_UUIDs':len(set(keys)),
        'header_count':len(h),'headers_sha256':hashlib.sha256(json.dumps(h,ensure_ascii=False).encode()).hexdigest(),
        'substantive_differences':len(exceptions),'old_86_count':'Not reconciled without original 86-record evidence',
        'model_output_status':'No independent crop, yield, weather, water or other model outputs inserted'}
    payload={'sheets':{
        'Client Output':[h]+rows,
        'Quality and Provenance':[['Field','Status','Evidence']]+[[col,'Imported source value; not independently validated KRISHI360 output',manifest['original_sha256']] for col in h],
        'Exceptions':[['UUID','Field','Original value','New CSV value','Decision']]+exceptions,
        'UID Mapping':[['UUID','UID']]+mapping,
        'Run Manifest':[['Item','Value']]+[[k,json.dumps(v) if not isinstance(v,str) else v] for k,v in manifest.items()]},'manifest':manifest}
    if areas_json:
        areas=json.loads(Path(areas_json).read_text())
        matched={}
        for r in areas['rows']:
            try: k=canonical_uuid(r['key'])
            except (ValueError,AttributeError): continue
            if k in matched: raise ValueError('Duplicate polygon UUID in area results')
            matched[k]=r
        payload['sheets']['Geometry Calculations']=[['UUID','Polygon area (m2)','Polygon area (acres)','Status','Area source SHA256']]
        for k in keys:
            r=matched.get(k)
            payload['sheets']['Geometry Calculations'].append([k,r.get('area_m2') if r else None,r.get('area_acres') if r else None,(r.get('exception') or 'Calculated geometry area; not crop/agricultural area') if r else 'Missing polygon',digest(areas_json)])
        payload['manifest']['geometry_area_source_sha256']=digest(areas_json)
        payload['sheets']['Run Manifest'].append(['geometry_area_source_sha256',digest(areas_json)])
    Path(out).write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False))
    return payload

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('original'); p.add_argument('new_csv'); p.add_argument('key'); p.add_argument('out'); p.add_argument('--sheet'); p.add_argument('--header-row',type=int,default=1); p.add_argument('--areas-json')
    a=p.parse_args(); prepare(a.original,a.new_csv,a.key,a.out,a.sheet,a.header_row,areas_json=a.areas_json)
