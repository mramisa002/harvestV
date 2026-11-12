"""Explicit QA-filtered point extraction from a downloaded NetCDF/HDF5 grid.
Works with 1D or 2D geographic coordinate arrays. Rejects projected MODIS tiles;
these need a separate CRS-aware conversion before this script is used.
Run with --help; variable/group names must match the selected product/version.
"""
import argparse
import json
import math
from pathlib import Path


def extract(path, variable, latitude, longitude, lat, lon, qa_variable, good_values, group=None):
    import numpy as np
    import xarray as xr
    with xr.open_dataset(path, group=group, decode_cf=True) as ds:
        y=ds[latitude]; x=ds[longitude]; data=ds[variable].squeeze(drop=True)
        if y.ndim==1 and x.ndim==1:
            if y.dims[0]==x.dims[0]:
                distance=(y-lat)**2+((x-lon)*math.cos(math.radians(lat)))**2
                index={y.dims[0]:int(distance.argmin())}
            else:
                index={y.dims[0]:int(abs(y-lat).argmin()), x.dims[0]:int(abs(x-lon).argmin())}
        elif y.shape==x.shape and y.ndim==2:
            distance=(y-lat)**2+((x-lon)*math.cos(math.radians(lat)))**2
            indices=np.unravel_index(np.nanargmin(distance.values),distance.shape)
            index=dict(zip(y.dims,map(int,indices)))
        else:
            raise ValueError('Unsupported coordinates; convert product to a geographic grid first')
        if not set(index)<=set(data.dims): raise ValueError('Coordinate dimensions do not match variable dimensions')
        actual_lat=float(y.isel({k:v for k,v in index.items() if k in y.dims}))
        actual_lon=float(x.isel({k:v for k,v in index.items() if k in x.dims}))
        if abs(actual_lat-lat)>.5 or abs(actual_lon-lon)>.5:
            raise ValueError('Nearest cell exceeds 0.5 degrees; grid CRS or bounds may be incorrect')
        qa=ds[qa_variable].squeeze(drop=True).isel(index)
        if qa.size!=1: raise ValueError('Select one timestamp/granule before extraction')
        if int(qa.item()) not in good_values: raise ValueError('Pixel fails configured product QA check')
        cell=data.isel(index)
        if cell.size!=1: raise ValueError('Select one timestamp/granule before extraction')
        value=float(cell.item())
        if not math.isfinite(value): raise ValueError('Missing or invalid pixel')
        return value, str(data.attrs.get('units','unknown'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file'); p.add_argument('--variable',required=True); p.add_argument('--group')
    p.add_argument('--lat-variable',default='lat'); p.add_argument('--lon-variable',default='lon')
    p.add_argument('--lat',type=float,required=True); p.add_argument('--lon',type=float,required=True)
    p.add_argument('--qa-variable',required=True); p.add_argument('--qa-good-values',type=int,nargs='+',required=True)
    p.add_argument('--source',choices=['imerg','smap','ndvi'],required=True)
    p.add_argument('--field',choices=['rain_mm','sm_surface','sm_root','ndvi'],required=True)
    p.add_argument('--expected-units',required=True,help='Fail closed if decoded units differ; do not guess rate-to-total conversions')
    p.add_argument('--district',required=True); p.add_argument('--day',required=True)
    p.add_argument('--product',required=True); p.add_argument('--source-timestamp',required=True); p.add_argument('--out',required=True)
    a=p.parse_args()
    value,units=extract(a.file,a.variable,a.lat_variable,a.lon_variable,a.lat,a.lon,a.qa_variable,a.qa_good_values,a.group)
    if units!=a.expected_units: raise ValueError(f'Units {units!r} do not match expected {a.expected_units!r}')
    record={'source':a.source,'district_id':a.district,'day':a.day,'source_timestamp':a.source_timestamp,
            'product':a.product,'quality_checked':True,'values':{a.field:value}}
    Path(a.out).write_text(json.dumps([record],indent=2),encoding='utf-8')


if __name__=='__main__': main()
