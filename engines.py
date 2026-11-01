"""KRISHI360 GIS engines. Requires GDAL Python bindings and numpy.
All outputs are preliminary observations, never crop/yield classifications.
"""
import argparse, csv, hashlib, json, math, os, stat, zipfile
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions()
ogr.UseExceptions()
osr.UseExceptions()

def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str))

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1048576), b''): h.update(b)
    return h.hexdigest()

def source(path):
    p=Path(path)
    return {'path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':sha(p)}

def srs(wkt):
    s=osr.SpatialReference(); s.SetFromUserInput(wkt)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s

def grid(d):
    t=d.GetGeoTransform()
    corners=[gdal.ApplyGeoTransform(t,x,y) for x,y in [(0,0),(d.RasterXSize,0),(d.RasterXSize,d.RasterYSize),(0,d.RasterYSize)]]
    b=d.GetRasterBand(1)
    return {'width':d.RasterXSize,'height':d.RasterYSize,'bands':d.RasterCount,
      'crs_wkt':d.GetProjection(),'transform':list(t),'corners':corners,
      'pixel_vector_lengths_in_crs_units':[math.hypot(t[1],t[4]),math.hypot(t[2],t[5])],
      'dtype':gdal.GetDataTypeName(b.DataType),'nodata':b.GetNoDataValue(),
      'scale':b.GetScale(),'offset':b.GetOffset(),'metadata':d.GetMetadata()}

def same_grid(a,b):
    return (a.RasterXSize==b.RasterXSize and a.RasterYSize==b.RasterYSize
        and bool(a.GetProjection()) and bool(b.GetProjection())
        and bool(srs(a.GetProjection()).IsSame(srs(b.GetProjection())))
        and np.allclose(a.GetGeoTransform(),b.GetGeoTransform(),rtol=0,atol=1e-12))

def read_valid(d):
    b=d.GetRasterBand(1); a=b.ReadAsArray().astype('float64')
    valid=(b.GetMaskBand().ReadAsArray()!=0)&np.isfinite(a)
    n=b.GetNoDataValue()
    if n is not None: valid &= a!=n
    return a,valid

def ndvi(red,nir,valid):
    v=valid & np.isfinite(red)&np.isfinite(nir)&(np.abs(red+nir)>1e-12)
    a=np.full(red.shape,-9999,dtype='float32')
    a[v]=((nir[v]-red[v])/(nir[v]+red[v])).astype('float32')
    # Negative reflectance is not silently discarded. Range failures are explicit.
    return a,v

def engine1(red,nir,out,supplied=None,scale=1.0,offset=0.0,encoding_evidence=None):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    r=gdal.Open(str(red)); n=gdal.Open(str(nir))
    if r.RasterCount!=1 or n.RasterCount!=1: raise ValueError('Single-band inputs required')
    if not same_grid(r,n): raise ValueError('B04/B08 grid or CRS mismatch; no silent resampling')
    if not np.isfinite(scale) or not np.isfinite(offset) or scale<=0: raise ValueError('Invalid decoding')
    ra,rv=read_valid(r); na,nv=read_valid(n)
    a,v=ndvi(ra*scale+offset,na*scale+offset,rv&nv)
    dest=out/'ndvi_preliminary.tif'
    d=gdal.GetDriverByName('GTiff').Create(str(dest),r.RasterXSize,r.RasterYSize,1,gdal.GDT_Float32,options=['COMPRESS=DEFLATE','TILED=YES'])
    d.SetGeoTransform(r.GetGeoTransform()); d.SetProjection(r.GetProjection())
    d.GetRasterBand(1).SetNoDataValue(-9999); d.GetRasterBand(1).WriteArray(a)
    d.SetMetadata({'STATUS':'PRELIMINARY_NOT_CLOUD_MASKED','ENCODING_EVIDENCE':encoding_evidence or 'UNVERIFIED_IDENTITY_DECODE'})
    d=None
    qa={'started_utc':datetime.now(timezone.utc).isoformat(),'gdal':gdal.VersionInfo(),
        'code_sha256':sha(__file__),'red':source(red),'nir':source(nir),
        'red_grid':grid(r),'nir_grid':grid(n),'scale':scale,'offset':offset,
        'reflectance_encoding_verified':bool(encoding_evidence),'encoding_evidence':encoding_evidence,
        'cloud_mask_applied':False,'SCL_status':'Not supplied or consumed by this version',
        'warning':'Identity/common-scale NDVI is conditional on additive offsets already handled. No reflectance encoding can be inferred conclusively from pixel range alone. No cloud-free or crop interpretation is supported.',
        'valid_pixels':int(v.sum()),'total_pixels':int(v.size),
        'outside_minus1_plus1':int(((a[v]<-1)|(a[v]>1)).sum()),
        'negative_decoded_reflectance_pixels':int((((ra*scale+offset)<0)|((na*scale+offset)<0))[v].sum()),
        'min':float(a[v].min()) if v.any() else None,'max':float(a[v].max()) if v.any() else None}
    if supplied:
        q=gdal.Open(str(supplied)); qa['supplied']=source(supplied); qa['supplied_grid']=grid(q)
        qa['comparison_same_grid']=same_grid(r,q)
        if qa['comparison_same_grid']:
            b,bv=read_valid(q); cv=v&bv; diff=a[cv].astype('float64')-b[cv]
            qa['comparison']={'pixels':int(cv.sum()),'mae':float(np.abs(diff).mean()) if cv.any() else None,
                'rmse':float(np.sqrt(np.mean(diff**2))) if cv.any() else None,'max_abs':float(np.abs(diff).max()) if cv.any() else None}
        else: qa['comparison_status']='Grid differs; pixel comparison deliberately not performed'
    qa['output']=source(dest); dump(out/'engine1_manifest.json',qa)
    return qa

def safe_extract(archive,destination,max_bytes=5_000_000_000):
    root=Path(destination).resolve()
    if root.exists(): raise ValueError('Extraction destination must be new')
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist()
        if sum(i.file_size for i in infos)>max_bytes: raise ValueError('Archive expanded-size limit')
        seen=set()
        for i in infos:
            if '\\' in i.filename or stat.S_ISLNK(i.external_attr>>16): raise ValueError('Unsafe archive member')
            p=(root/i.filename).resolve()
            if not p.is_relative_to(root) or p==root: raise ValueError('Archive traversal')
            if str(p).casefold() in seen: raise ValueError('Duplicate archive destination')
            seen.add(str(p).casefold())
        if z.testzip(): raise ValueError('Archive CRC failure')
        root.mkdir(parents=True)
        z.extractall(root)
    return [{'name':i.filename,'bytes':i.file_size,'crc':i.CRC} for i in infos]

def inspect_vector(path,out,keys=None):
    d=ogr.Open(str(path),0)
    if d is None: raise ValueError('Unreadable vector dataset')
    results=[]
    for l in d:
        sr=l.GetSpatialRef(); fields=[{'name':f.GetName(),'type':f.GetTypeName(),'width':f.GetWidth(),'precision':f.GetPrecision()} for f in l.schema]
        matches={f['name']:set() for f in fields} if keys else {}
        nulls=0; types={}
        for f in l:
            g=f.GetGeometryRef()
            if g is None: nulls+=1
            else: types[g.GetGeometryName()]=types.get(g.GetGeometryName(),0)+1
            for k in matches:
                value=str(f.GetField(k))
                if value in keys: matches[k].add(value)
        results.append({'layer':l.GetName(),'count':l.GetFeatureCount(),'crs_wkt':sr.ExportToWkt() if sr else None,
            'extent':list(l.GetExtent()) if l.GetFeatureCount() else None,'fields':fields,'geometry_types':types,'null_geometries':nulls,
            'exact_key_match_counts':{k:len(v) for k,v in matches.items()}})
    dump(out,{'dataset':str(Path(path).resolve()),'layers':results,'note':'Candidate matches do not establish cadastral identity. Select a layer and key explicitly.'})
    return results

def plot_areas(path,layer,key,keys,out,target='EPSG:32644'):
    d=ogr.Open(str(path),0); l=d.GetLayerByName(layer)
    if l is None: raise ValueError('Layer not found')
    if l.GetSpatialRef() is None: raise ValueError('Missing source CRS')
    if l.GetLayerDefn().GetFieldIndex(key)<0: raise ValueError('Missing join field')
    src=srs(l.GetSpatialRef().ExportToWkt()); dst=srs(target)
    if not dst.IsProjected() or abs(dst.GetLinearUnits()-1)>1e-12: raise ValueError('Area CRS must use metres')
    transform=osr.CoordinateTransformation(src,dst)
    rows=[]; counts={}
    for f in l:
        k=str(f.GetField(key)); counts[k]=counts.get(k,0)+1
        g=f.GetGeometryRef(); area=None; reason=None
        if g is None or g.IsEmpty(): reason='Missing/empty geometry'
        elif g.GetGeometryName() not in ('POLYGON','MULTIPOLYGON'): reason='Not a polygon'
        elif not g.IsValid(): reason='Invalid geometry; not silently repaired'
        else:
            g=g.Clone(); g.Transform(transform)
            area=g.GetArea()
            if not math.isfinite(area) or area<=0: area=None; reason='Nonpositive/nonfinite area'
        rows.append({'key':k,'fid':f.GetFID(),'matched_client':k in keys,'area_m2':area,'area_acres':area/4046.8564224 if area is not None else None,'exception':reason})
    for r in rows:
        if counts[r['key']]>1: r.update(area_m2=None,area_acres=None,exception='Duplicate key; area withheld')
    result={'source':str(path),'layer':layer,'key':key,'target_crs':target,'rows':rows,
        'missing_client_keys':sorted(set(keys)-set(counts)),
        'warning':'Geometry area is not agricultural/crop area. Precision reflects source coordinates and boundary quality; no survey accuracy is established.'}
    dump(out,result); return result

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('ndvi'); a.add_argument('--red',required=True); a.add_argument('--nir',required=True); a.add_argument('--out',required=True); a.add_argument('--supplied'); a.add_argument('--scale',type=float,default=1); a.add_argument('--offset',type=float,default=0); a.add_argument('--encoding-evidence')
    a=sub.add_parser('extract'); a.add_argument('archive'); a.add_argument('destination')
    a=sub.add_parser('inspect'); a.add_argument('dataset'); a.add_argument('out'); a.add_argument('--keys-json')
    a=sub.add_parser('areas'); a.add_argument('dataset'); a.add_argument('layer'); a.add_argument('key'); a.add_argument('keys_json'); a.add_argument('out'); a.add_argument('--target',default='EPSG:32644')
    a=p.parse_args(); v=vars(a); c=v.pop('command')
    if c=='ndvi': engine1(**v)
    elif c=='extract': dump(str(a.destination)+'_archive_inventory.json',safe_extract(a.archive,a.destination))
    elif c=='inspect': inspect_vector(a.dataset,a.out,set(json.loads(Path(a.keys_json).read_text())) if a.keys_json else None)
    else: plot_areas(a.dataset,a.layer,a.key,set(json.loads(Path(a.keys_json).read_text())),a.out,a.target)

if __name__=='__main__': main()
