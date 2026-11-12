import json
from .db import initialize,connect,query
from .settings import BASE
def seed():
    initialize()
    with connect() as db:
        for r in json.loads((BASE/'config/districts.json').read_text(encoding='utf-8')):
            query(db,'INSERT INTO districts(id,name,division,lat,lon,aez,estimate_method) VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
                  (r['id'],r['name'],r['division'],r['lat'],r['lon'],r['aez'],r['estimate_method']))
if __name__=='__main__': seed()
