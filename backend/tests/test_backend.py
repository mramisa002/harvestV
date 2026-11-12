"""Synthetic offline tests. These fixtures are NOT recorded NASA observations."""
import atexit
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import date, timedelta, datetime, timezone
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix='harvestv-tests-')
atexit.register(TEMP.cleanup)
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(TEMP.name) / 'test.db')

from fastapi import HTTPException
from app.main import app, advisory, conditions, districts, crops, health
from app.schemas import Advisory
from app.seed import seed
from app.config import CONFIG
from app.scoring import advise, thermal, moisture_band, normalize_moisture, DataUnavailable, windows
from app.ingestion import parse_power, validate_normalized, store_rows
from app.db import connect, query, observations


def synthetic_history(today):
    start = date(today.year - 22, 1, 1)
    return {start + timedelta(days=i): dict(rain_mm=2., tmean=20., tmax=26., tmin=12., solar=15., rh=70.)
            for i in range((today - start).days)}


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today = date(2026, 11, 12)
        cls.history = synthetic_history(cls.today)
        cls.soil = dict(day=cls.today-timedelta(days=1), surface=.5, root=.5)

    def run_advice(self, **changes):
        args = dict(today=self.today, history=self.history, config=CONFIG, crop_id='wheat', smap=self.soil)
        args.update(changes)
        return advise(**args)

    def test_thermal_edges(self):
        self.assertEqual(thermal(5, [5, 15, 25, 35]), 0)
        self.assertEqual(thermal(20, [5, 15, 25, 35]), 1)
        self.assertEqual(thermal(10, [5, 15, 25, 35]), .5)

    def test_moisture_edges(self):
        self.assertEqual(moisture_band(1, [.3, .75]), 0)
        self.assertEqual(moisture_band(.5, [.3, .75]), 1)

    def test_no_soil_estimate_is_not_invented(self):
        self.assertIsNone(normalize_moisture(.3, None, None))
        self.assertAlmostEqual(normalize_moisture(.3, .1, .5), .5)

    def test_fresh_workable_soil(self):
        result=self.run_advice()
        self.assertEqual(result['status'], 'GO')
        self.assertNotEqual(result['confidence'], 'HIGH')

    def test_waterlogging_veto(self):
        result=self.run_advice(smap={**self.soil, 'surface':.99})
        self.assertEqual(result['status'], 'AVOID')
        self.assertIn('soil_wet', result['candidates'][0]['vetoes'])
        self.assertEqual(result['candidates'][1]['vetoes'], [])

    def test_heavy_rain_veto(self):
        h={**self.history, self.today-timedelta(days=1):{**self.history[self.today-timedelta(days=1)],'rain_mm':80}}
        self.assertEqual(self.run_advice(history=h)['status'], 'AVOID')

    def test_thermal_veto(self):
        d=self.today-timedelta(days=1)
        h={**self.history, d:{**self.history[d], 'tmax':42}}
        self.assertIn('temperature', self.run_advice(history=h)['candidates'][0]['vetoes'])

    def test_missing_soil_degrades(self):
        r=self.run_advice(smap=None)
        self.assertEqual(r['confidence'], 'LOW')
        self.assertNotEqual(r['status'], 'GO')

    def test_stale_soil_degrades(self):
        self.assertEqual(self.run_advice(smap={**self.soil, 'day':self.today-timedelta(days=15)})['confidence'], 'LOW')

    def test_stale_root_does_not_use_fresh_surface_age(self):
        r=self.run_advice(smap={**self.soil,'root_day':self.today-timedelta(days=20)})
        self.assertEqual(r['confidence'],'LOW')
        self.assertNotEqual(r['status'],'GO')

    def test_stale_rain_rejected(self):
        h={d:v for d,v in self.history.items() if d < self.today-timedelta(days=10)}
        with self.assertRaises(DataUnavailable): self.run_advice(history=h)

    def test_recent_gap_rejected(self):
        h=dict(self.history); del h[self.today-timedelta(days=3)]
        with self.assertRaises(DataUnavailable): self.run_advice(history=h)

    def test_short_history_rejected(self):
        h={d:v for d,v in self.history.items() if d.year>=2020}
        with self.assertRaises(DataUnavailable): self.run_advice(history=h)

    def test_future_observations_cannot_change_result(self):
        h={**self.history,self.today+timedelta(days=5):dict(rain_mm=1000,tmean=80,tmin=70,tmax=90)}
        self.assertEqual(self.run_advice(history=h), self.run_advice())

    def test_bangla_has_actual_bangla(self):
        r=self.run_advice(lang='bn')
        self.assertTrue(any('\u0980' <= c <= '\u09ff' for c in r['action']))

    def test_windows_cannot_cross_veto(self):
        rows=[dict(day=f'2026-11-{10+i}',score=90,smoothed_score=90,vetoes=['wet'] if i==2 else []) for i in range(5)]
        self.assertEqual(windows(rows,3), [])

    def test_supported_crops_and_scores(self):
        for crop in CONFIG['crops']:
            r=self.run_advice(crop_id=crop)
            self.assertTrue(0<=r['today_score']<=100)
            self.assertEqual(len(r['candidates']),14)


class ProviderTests(unittest.TestCase):
    def test_power_fill_values(self):
        payload=json.loads((Path(__file__).parent/'fixtures/power-schema-synthetic.json').read_text())
        rows=parse_power(payload)
        self.assertEqual(rows[0][1]['rain_mm'],12)
        self.assertIsNone(rows[1][1]['rain_mm'])

    def test_normalized_earthdata_fixtures(self):
        for source in ['imerg','smap','ndvi']:
            v=json.loads((Path(__file__).parent/f'fixtures/{source}-synthetic.json').read_text())
            validate_normalized(source,v)

    def test_invalid_units_rejected(self):
        for source,values in [('imerg',{'rain_mm':-1}),('smap',{'sm_surface':25}),('ndvi',{'ndvi':3200})]:
            with self.assertRaises(ValueError): validate_normalized(source, values)

    def test_root_only_measurement_is_valid(self):
        validate_normalized('smap',{'sm_root':.3})


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()

    def test_catalogs(self):
        self.assertEqual(len(districts()),64)
        self.assertEqual(len(crops()),4)

    def test_validation(self):
        schema=app.openapi()['paths']['/api/v1/advisory']['get']
        params={p['name']:p['schema'] for p in schema['parameters']}
        self.assertEqual(set(params['crop']['enum']), {'wheat','mustard','lentil','potato'})
        self.assertEqual(set(params['lang']['enum']), {'en','bn'})
        with self.assertRaises(HTTPException) as raised: advisory('unknown','wheat','en',14)
        self.assertEqual(raised.exception.status_code,404)

    def test_missing_data(self):
        with self.assertRaises(HTTPException) as raised: advisory('bandarban','wheat','en',14)
        self.assertEqual(raised.exception.status_code,503)

    def test_idempotency_and_advisory_contract(self):
        today=date.today(); history=synthetic_history(today)
        rows=list(history.items())
        with connect() as db:
            store_rows(db,'dhaka','power',rows)
            store_rows(db,'dhaka','power',rows[-14:])
            count=query(db,"SELECT COUNT(*) AS n FROM observations WHERE district_id='dhaka'").fetchone()['n']
        self.assertEqual(count,len(rows))
        with patch('httpx.AsyncClient.get',side_effect=AssertionError('NASA must not be called from API')):
            result=advisory('dhaka','wheat','en',14)
        Advisory.model_validate(result)
        self.assertEqual(result['district'],'Dhaka')
        self.assertEqual(result['confidence'],'LOW')
        self.assertIsNone(result['data_freshness']['smap'])
        self.assertGreater(len(conditions('dhaka',30)['series']),0)

    def test_cors(self):
        self.assertIn('http://localhost:3000',app.user_middleware[0].kwargs['allow_origins'])

    def test_health_and_docs(self):
        self.assertEqual(health()['status'],'ok')
        self.assertIn('/api/v1/advisory',app.openapi()['paths'])


class UserDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.user_data import initialize_user_data
        seed(); initialize_user_data()
        cls.token='a'*64; cls.other='b'*64

    def test_farm_isolation_and_update(self):
        from app.user_data import FarmInput,put_farm,get_farm
        put_farm(FarmInput(district_id='dhaka',fields={'water':'Rainfed','plot':'My plot'}),self.token)
        self.assertEqual(get_farm(self.token)['farm']['fields']['water'],'Rainfed')
        self.assertIsNone(get_farm(self.other)['farm'])
        put_farm(FarmInput(district_id='chattogram',fields={'water':'Canal / Pond'}),self.token)
        self.assertEqual(get_farm(self.token)['farm']['district_id'],'chattogram')

    def test_farm_unknown_district(self):
        from app.user_data import FarmInput,put_farm
        with self.assertRaises(HTTPException): put_farm(FarmInput(district_id='unknown'),self.token)

    def test_feedback_idempotency_and_isolation(self):
        from app.user_data import FeedbackInput,post_feedback,get_feedback
        from uuid import uuid4
        body=FeedbackInput(id=uuid4(),message='  My field is wet  ')
        result=post_feedback(body,self.token); post_feedback(body,self.token)
        self.assertEqual(len(get_feedback(self.token)),1)
        self.assertEqual(get_feedback(self.token)[0]['message'],'My field is wet')
        self.assertEqual(get_feedback(self.other),[])
        self.assertEqual(result['expert_review'],'not_connected')

    def test_empty_feedback_rejected(self):
        from app.user_data import FeedbackInput
        from pydantic import ValidationError
        from uuid import uuid4
        with self.assertRaises(ValidationError): FeedbackInput(id=uuid4(),message='   ')

    def test_invalid_token_rejected(self):
        from app.user_data import owner
        with self.assertRaises(HTTPException): owner('guessable')

    def test_field_length_rejected(self):
        from app.user_data import FarmInput
        from pydantic import ValidationError
        with self.assertRaises(ValidationError): FarmInput(district_id='dhaka',fields={'x':'a'*1001})

    def test_information_check_does_not_fabricate_sources(self):
        from app.user_data import CheckInput,information_check
        result=information_check(CheckInput(advice='Can I sow now?',lang='bn'))
        self.assertEqual(result['status'],'UNVERIFIED'); self.assertEqual(result['sources'],[])

    def test_saved_advisory_does_not_accept_forged_scores(self):
        from app.user_data import SaveInput,save_advisory,get_saved
        from uuid import uuid4
        # APITests have seeded Dhaka history; server computes the response itself.
        body=SaveInput(id=uuid4(),district_id='dhaka',crop='wheat')
        save_advisory(body,self.token); save_advisory(body,self.token)
        rows=get_saved(self.token)
        self.assertEqual(len(rows),1); self.assertEqual(rows[0]['confidence'],'LOW')
        self.assertEqual(get_saved(self.other),[])

    def test_new_openapi_contracts(self):
        paths=app.openapi()['paths']
        self.assertIn('put',paths['/api/v1/farm'])
        self.assertIn('post',paths['/api/v1/feedback'])
        p=paths['/api/v1/farm']['get']['parameters'][0]
        self.assertEqual(p['name'],'X-Device-Token'); self.assertTrue(p['required'])


if __name__=='__main__': unittest.main()
