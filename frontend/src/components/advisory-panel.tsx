"use client";
import { useEffect, useState } from 'react';
import { useLanguage } from '@/lib/language';
import { advisory, crops, districts, getFarm, getSaved, request, type Advisory, type Crop, type District, type Conditions, type SavedAdvisory } from '@/lib/backend';

export default function AdvisoryPanel({ dashboard = false }: { dashboard?: boolean }) {
  const { language } = useLanguage(); const bn = language === 'bn';
  const [districtList, setDistrictList] = useState<District[]>([]);
  const [cropList, setCropList] = useState<Crop[]>([]);
  const [district, setDistrict] = useState(''); const [crop, setCrop] = useState('wheat');
  const [result, setResult] = useState<Advisory | null>(null);
  const [condition, setCondition] = useState<Conditions | null>(null);
  const [saved, setSaved] = useState<SavedAdvisory[]>([]);
  const [error, setError] = useState(''); const [catalogError, setCatalogError] = useState('');
  const [busy, setBusy] = useState(false); const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(''); const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController(); setCatalogError('');
    Promise.all([districts(controller.signal), crops(controller.signal)]).then(([ds, cs]) => {
      if (!controller.signal.aborted) { setDistrictList(ds); setCropList(cs); }
    }).catch(e => { if (!controller.signal.aborted) setCatalogError(e.message); });
    getFarm(controller.signal).then(({ farm }) => { if (farm && !controller.signal.aborted) setDistrict(d => d || farm.district_id); })
      .catch(() => { if (!controller.signal.aborted) setMessage(bn ? 'সংরক্ষিত খামার পড়া যায়নি। জেলা বেছে নিন।' : 'Could not load your saved farm. Choose a district.'); });
    if (dashboard) getSaved(controller.signal).then(x => { if (!controller.signal.aborted) setSaved(x); }).catch(() => { if (!controller.signal.aborted) setMessage(bn ? 'সংরক্ষিত পরামর্শ পড়া যায়নি।' : 'Could not load saved advisories.'); });
    return () => controller.abort();
  }, [dashboard, refresh, bn]);

  useEffect(() => {
    setResult(null); setCondition(null); setError(''); setMessage('');
    if (!district) { setBusy(false); return; }
    const controller = new AbortController(); setBusy(true);
    advisory(district, crop, language, controller.signal)
      .then(value => { if (!controller.signal.aborted) setResult(value); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    request<Conditions>('/api/v1/conditions?' + new URLSearchParams({ district, days: '14' }), { signal: controller.signal, lang: language })
      .then(value => { if (!controller.signal.aborted) setCondition(value); })
      .catch(() => { /* Missing observations stay explicitly unavailable. */ });
    return () => controller.abort();
  }, [district, crop, language, refresh]);

  async function save() {
    if (!result || saving) return;
    setSaving(true); setMessage('');
    try {
      await request('/api/v1/saved-advisories', { private: true, method: 'POST', body: { id: crypto.randomUUID(), district_id: district, crop, lang: language }, lang: language });
      setMessage(bn ? 'পরামর্শ সার্ভারে সংরক্ষিত হয়েছে।' : 'Advisory saved to the server.');
      if (dashboard) setSaved(await getSaved());
    } catch (e) { setMessage((e as Error).message); } finally { setSaving(false); }
  }

  function windowView(label: string, w: Advisory['best_window']) {
    return <div><strong>{label}</strong><p>{w ? `${w.start} — ${w.end} · ${w.mean_score}/100` : bn ? 'উপযুক্ত সময় পাওয়া যায়নি' : 'No suitable window found'}</p></div>;
  }
  return <section className="connected-panel" data-connected="advisory" onClick={e => e.stopPropagation()}>
    <span className="connected-eyebrow">{bn ? 'খামারের পরামর্শ' : 'FARM ADVISORY'}</span>
    <h2>{bn ? 'কখন বপন করবেন?' : 'When should you sow?'}</h2>
    <p>{bn ? 'জেলা ও ফসল বেছে নিন। পরামর্শ সাম্প্রতিক পর্যবেক্ষণ ও পুরোনো বছরের তথ্য থেকে তৈরি হয়।' : 'Choose your district and crop. Advice uses cached observations and historical climate patterns.'}</p>
    <div className="connected-fields">
      <label>{bn ? 'জেলা' : 'District'}<select aria-label={bn ? 'জেলা' : 'District'} value={district} onChange={e => setDistrict(e.target.value)}><option value="">{bn ? 'জেলা বেছে নিন' : 'Choose a district'}</option>{districtList.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
      <label>{bn ? 'ফসল' : 'Crop'}<select aria-label={bn ? 'ফসল' : 'Crop'} value={crop} onChange={e => setCrop(e.target.value)}>{cropList.map(c => <option key={c.id} value={c.id}>{bn ? c.name_bn : c.id.charAt(0).toUpperCase() + c.id.slice(1)}</option>)}</select></label>
      <button type="button" onClick={() => setRefresh(x => x + 1)} disabled={busy}>{bn ? 'আবার দেখুন' : 'Refresh'}</button>
    </div>
    {catalogError && <p role="alert" className="connected-error">{catalogError}</p>}
    {busy && <p role="status">{bn ? 'তথ্য পড়া হচ্ছে…' : 'Reading cached observations…'}</p>}
    {error && <p role="alert" className="connected-error">{error}</p>}
    {!district && <p>{bn ? 'আপনার খামারের জেলা নির্বাচন করুন।' : 'Select your farm’s district to begin.'}</p>}
    {result && !busy && <article aria-live="polite">
      <div className="connected-result"><strong className={'advisory-status status-' + result.status.toLowerCase()}>{bn ? ({ GO: 'বপনের উপযুক্ত', WAIT: 'অপেক্ষা করুন', AVOID: 'এখন বপন এড়ান' })[result.status] : result.status}</strong><span>{bn ? 'স্কোর' : 'Score'}: {result.today_score}/100 · {bn ? 'আস্থা' : 'Confidence'}: {result.confidence}</span></div>
      <ul>{result.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
      <p>{result.action}</p><p>{result.confidence_reason}</p>
      <div className="connected-windows">{windowView(bn ? 'সম্ভাব্য ভালো সময়' : 'Best provisional window', result.best_window)}{windowView(bn ? 'বিকল্প সময়' : 'Alternative window', result.next_best_window)}</div>
      <p className="connected-freshness">{Object.entries(result.data_freshness).map(([key, value]) => `${key.toUpperCase()}: ${value ?? (bn ? 'তথ্য নেই' : 'unavailable')}`).join(' · ')}</p>
      <button type="button" onClick={save} disabled={saving}>{saving ? (bn ? 'সংরক্ষণ হচ্ছে…' : 'Saving…') : (bn ? 'এই পরামর্শ সংরক্ষণ করুন' : 'Save this advisory')}</button>
    </article>}
    <details><summary>{bn ? 'সাম্প্রতিক পরিবেশের তথ্য' : 'Recent observed conditions'}</summary>{condition ? <div className="connected-table"><table><thead><tr>{['Date', 'Source', 'Rain (mm)', 'Mean °C'].map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{condition.series.slice(-20).map(r => <tr key={r.day + r.source}><td>{r.day}</td><td>{r.source}</td><td>{r.values.rain_mm ?? '—'}</td><td>{r.values.tmean ?? '—'}</td></tr>)}</tbody></table></div> : <p>{bn ? 'পর্যবেক্ষণের তথ্য নেই।' : 'No observations available.'}</p>}</details>
    {dashboard && <details><summary>{bn ? 'সংরক্ষিত পরামর্শ' : 'Saved advisories'} ({saved.length})</summary>{saved.map(s => <p key={s.id}>{s.district} · {s.crop} · {s.status} · {s.created_at.slice(0, 10)}</p>)}</details>}
    {message && <p role="status">{message}</p>}
    <small>{bn ? 'পুরোনো বছরের তথ্য আবহাওয়ার পূর্বাভাস নয়। বপনের আগে স্থানীয় কৃষি কর্মকর্তার সঙ্গে আলোচনা করুন।' : 'Historical climate patterns are not a forecast. Check current field conditions with a local agricultural officer before sowing.'}</small>
  </section>;
}
