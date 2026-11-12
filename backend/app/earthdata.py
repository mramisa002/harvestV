"""Authenticated granule acquisition; extraction is an explicit, product-specific stage.
This does not pretend that downloading a file is the same as ingesting validated observations.
"""
import argparse, json
from pathlib import Path
from . import settings  # Load backend/.env before earthaccess authenticates.

PRODUCTS={'imerg-final':'GPM_3IMERGDF','imerg-late':'GPM_3IMERGDL','smap-surface':'SPL3SMP_E',
          'smap-root':'SPL4SMGP','modis':'MOD13Q1','viirs':'VNP13A1'}
def download(product, start, end, bbox, destination):
    import earthaccess
    auth=earthaccess.login(strategy='environment',persist=False)
    if not auth.authenticated: raise RuntimeError('Earthdata authentication failed')
    granules=earthaccess.search_data(short_name=PRODUCTS[product],temporal=(start,end),bounding_box=tuple(bbox))
    if not granules: raise RuntimeError('No granules found')
    dest=Path(destination); dest.mkdir(parents=True,exist_ok=True)
    files=earthaccess.download(granules,local_path=str(dest))
    (dest/'manifest.json').write_text(json.dumps({'product':PRODUCTS[product],'start':start,'end':end,'bbox':bbox,'files':[str(f) for f in files],'status':'downloaded; QA and extraction still required'},indent=2))
    return files
def main():
    p=argparse.ArgumentParser(); p.add_argument('product',choices=PRODUCTS); p.add_argument('--start',required=True); p.add_argument('--end',required=True)
    p.add_argument('--bbox',nargs=4,type=float,required=True,metavar=('WEST','SOUTH','EAST','NORTH')); p.add_argument('--out',required=True)
    a=p.parse_args(); download(a.product,a.start,a.end,a.bbox,a.out)
if __name__=='__main__': main()
