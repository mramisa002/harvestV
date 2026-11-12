"""Apply reviewed district soil estimates; nothing is inferred from district names.
Input JSON: [{"district_id":"dhaka","wilting_point":...,"field_capacity":...,
             "estimate_method":"survey citation / lab method", "aez":null}]
"""
import argparse
import json
import math
from pathlib import Path
from .seed import seed
from .db import connect, query, get_district


def apply(path):
    seed()
    records=json.loads(Path(path).read_text(encoding='utf-8'))
    with connect() as db:
        for r in records:
            wp,fc=r['wilting_point'],r['field_capacity']
            if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (wp,fc)) or not 0<=wp<fc<=1:
                raise ValueError('Soil estimates must satisfy 0 <= wilting point < field capacity <= 1')
            if not r.get('estimate_method','').strip(): raise ValueError('Survey citation/method required')
            if not get_district(db,r['district_id']): raise ValueError('Unknown district')
            query(db,'UPDATE districts SET wilting_point=?,field_capacity=?,estimate_method=?,aez=? WHERE id=?',
                  (wp,fc,r['estimate_method'],r.get('aez'),r['district_id']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('path'); a=p.parse_args(); apply(a.path)
