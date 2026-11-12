"use client";
import { useEffect, useRef, useState, type ReactNode, type MouseEvent } from 'react';
import { useRouter } from 'next/navigation';
import { createPortal } from 'react-dom';
import { useLanguage } from '@/lib/language';
import { districts, getFarm, saveFarm, getFeedback, sendFeedback, request, type District, type FeedbackRecord } from '@/lib/backend';

export default function PageInteractions({ page, children }: { page: string; children: ReactNode }) {
 const { language, setLanguage, t } = useLanguage(); const router = useRouter();
 const root = useRef<HTMLDivElement>(null); const pendingRef = useRef(false);
 const submission = useRef<{message:string;id:string}|null>(null);
 const [message, setMessage] = useState(''); const [reports, setReports] = useState<FeedbackRecord[]>([]);
 const [districtList, setDistrictList] = useState<District[]>([]); const [district, setDistrict] = useState('');
 const [pending, setPending] = useState(false);
 const [districtMount, setDistrictMount] = useState<HTMLElement|null>(null);
 const say = (en: string, bn: string) => language === 'bn' ? bn : en;

 useEffect(() => {
  const controller = new AbortController();
  setDistrictMount(root.current?.querySelector<HTMLElement>('#server-farm-district') ?? null);
  if (page === 'my-farm') {
   districts(controller.signal).then(ds => { if (!controller.signal.aborted) setDistrictList(ds); }).catch(e => { if (!controller.signal.aborted) setMessage(e.message); });
   getFarm(controller.signal).then(({farm}) => {
    if (controller.signal.aborted || !farm) return;
    setDistrict(farm.district_id);
    root.current?.querySelectorAll<HTMLInputElement>('input[name]').forEach(input => {
     const value = farm.fields[input.name]; if (value === undefined) return;
     if (input.type === 'radio' || input.type === 'checkbox') input.checked = input.value === value;
     else input.value = value;
    });
    root.current?.querySelectorAll<HTMLButtonElement>('button[data-action]').forEach(button => {
     if (['Silt Loam','Clay Loam','Sandy Loam'].includes(button.dataset.action ?? '')) button.setAttribute('aria-pressed', String(button.dataset.action === farm.fields.soil));
    });
   }).catch(e => { if (!controller.signal.aborted) setMessage(e.message); });
  }
  if (page === 'feedback') getFeedback(controller.signal).then(x => { if (!controller.signal.aborted) setReports(x); }).catch(e => { if (!controller.signal.aborted) setMessage(e.message); });
  return () => controller.abort();
 }, [page]);

 function localSave(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Server is authoritative; local storage is optional except the device token. */ } }

 async function click(event: MouseEvent<HTMLDivElement>) {
  const target = (event.target as HTMLElement).closest<HTMLElement>('button,[data-sources]'); if (!target) return;
  const label = (target.dataset.action ?? target.textContent ?? '').replace(/\s+/g, ' ').trim();
  if (label === 'EN' || target.lang === 'bn' || label === 'বাংলা') { setLanguage(label === 'EN' ? 'en' : 'bn'); setMessage(''); return; }
  if (/^(Change field|\+ Add new farm|\+ Add your farm|Change Plot Context|Register New Field)$/.test(label)) { router.push('/my-farm'); return; }
  if (/Plan next crop|View full plan/.test(label)) { router.push('/crop-rotation'); return; }
  if (label === 'HarvestV') { router.push('/'); return; }
  if (['Silt Loam','Clay Loam','Sandy Loam','Yes, helpful','Needs adjustment'].includes(label)) {
   target.parentElement?.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', 'false'));
   target.setAttribute('aria-pressed', 'true'); return;
  }
  if (pendingRef.current) return;
  if (/Save Farm/.test(label)) {
   if (!district) { setMessage(say('Choose the district above before saving your farm.', 'খামার সংরক্ষণের আগে উপরের জেলা বেছে নিন।')); return; }
   const fields: Record<string,string> = {};
   root.current?.querySelectorAll<HTMLInputElement>('input[name]').forEach(input => { if (!['radio','checkbox'].includes(input.type) || input.checked) fields[input.name] = input.value; });
   const soil = root.current?.querySelector<HTMLElement>('button[aria-pressed="true"][data-action$="Loam"]');
   if (soil?.dataset.action) fields.soil = soil.dataset.action;
   pendingRef.current = true; setPending(true);
   try {
    await saveFarm({ district_id: district, fields });
    localSave('harvestv-field-profile', fields);
    localSave('harvestv-farm', { name: fields.plot || 'My farm', location: districtList.find(d => d.id === district)?.name || district, area: '1.5', soil: 0, crop: 0, water: 0 });
    setMessage(say('Farm saved to the server.', 'খামার সার্ভারে সংরক্ষিত হয়েছে।'));
   } catch (e) { setMessage((e as Error).message); } finally { pendingRef.current = false; setPending(false); }
   return;
  }
  if (label === 'Discard changes') {
   pendingRef.current = true; setPending(true);
   try {
    const {farm} = await getFarm(); setDistrict(farm?.district_id ?? '');
    root.current?.querySelectorAll<HTMLInputElement>('input[name]').forEach(input => {
     const value=farm?.fields[input.name];
     if (input.type==='radio'||input.type==='checkbox') input.checked=value===undefined?input.defaultChecked:input.value===value;
     else input.value=value??input.defaultValue;
    });
    root.current?.querySelectorAll<HTMLButtonElement>('button[data-action]').forEach(button => {
     if (['Silt Loam','Clay Loam','Sandy Loam'].includes(button.dataset.action??'')) button.setAttribute('aria-pressed',String(button.dataset.action===farm?.fields.soil));
    });
    setMessage(say('Restored the last server-saved farm.', 'সার্ভারে সংরক্ষিত খামার ফিরিয়ে আনা হয়েছে।'));
   } catch(e) { setMessage((e as Error).message); } finally { pendingRef.current=false;setPending(false); }
   return;
  }
  if (/Save This Plan|Select This Plan/.test(label)) { setMessage(say('These cards are examples. Use “Save this advisory” in the connected panel above to save real API output.', 'এই কার্ডগুলো নমুনা। উপরের প্যানেল থেকে সার্ভারের পরামর্শ সংরক্ষণ করুন।')); return; }
  if (label === 'Check information') {
   const advice = root.current?.querySelector<HTMLTextAreaElement>('textarea[name="advice"]');
   if (!advice?.value.trim()) { advice?.focus(); setMessage(say('Enter the advice to check.', 'যাচাই করার পরামর্শটি লিখুন।')); return; }
   pendingRef.current = true; setPending(true);
   try { const result = await request<{message:string}>('/api/v1/information-check', { method:'POST', body:{ advice:advice.value, lang:language }, lang:language }); setMessage(result.message); }
   catch (e) { setMessage((e as Error).message); } finally { pendingRef.current = false; setPending(false); } return;
  }
  if (label.includes('Submit Feedback') || label === 'Submit Note') {
   const input = root.current?.querySelector<HTMLTextAreaElement>('textarea'); const text = input?.value.trim();
   if (!text || !input) { input?.focus(); setMessage(say('Write your observation first.', 'আগে আপনার পর্যবেক্ষণ লিখুন।')); return; }
   if (!submission.current || submission.current.message !== text) submission.current = {message:text,id:crypto.randomUUID()};
   pendingRef.current = true; setPending(true);
   try {
    await sendFeedback(text, submission.current.id); input.value = ''; submission.current = null;
    setMessage(say('Feedback saved to the server. Expert replies and photo uploads are not connected.', 'মতামত সার্ভারে সংরক্ষিত হয়েছে। বিশেষজ্ঞের উত্তর ও ছবি আপলোডের সেবা সংযুক্ত নেই।'));
    getFeedback().then(setReports).catch(() => {});
   } catch (e) { setMessage((e as Error).message); } finally { pendingRef.current = false; setPending(false); } return;
  }
  if (label === 'Use my current location') {
   if (!navigator.geolocation) { setMessage(t('Location is unavailable. Please use manual entry.')); return; }
   navigator.geolocation.getCurrentPosition(p => setMessage(t(`Device location: ${p.coords.latitude.toFixed(4)}, ${p.coords.longitude.toFixed(4)}. Confirm your farm location separately.`)), () => setMessage(t('Could not find your device location. Your manual entries are unchanged.'))); return;
  }
  if (/Manual entry/.test(label)) { root.current?.querySelector<HTMLInputElement>('input[name="division"]')?.focus(); return; }
  if (label === 'Confirm farm location') { setMessage(say('Choose the district above and save the farm. The map remains a sample preview.', 'উপরে জেলা বেছে নিয়ে খামার সংরক্ষণ করুন। মানচিত্রটি নমুনা।')); return; }
  if (/Submit for Fast/.test(label)) { router.push('/feedback'); return; }
  if (label === 'Cadastral Export') {
   const values = Array.from(root.current?.querySelectorAll<HTMLInputElement>('input[name]') || []).filter(i => i.type !== 'radio' || i.checked).map(i => `${i.name}: ${i.value}`).join('\n');
   const url = URL.createObjectURL(new Blob([values], {type:'text/plain'})); const a = document.createElement('a'); a.href = url; a.download = 'harvestv-field-profile.txt'; a.click(); URL.revokeObjectURL(url); return;
  }
  if (target.dataset.sources) { setMessage(say('Sample research dossier. Live evidence retrieval is not connected.', 'গবেষণার নমুনা। সরাসরি প্রমাণ খোঁজার সেবা সংযুক্ত নেই।')); return; }
  setMessage(say('This design example is not connected to a backend service.', 'নকশার এই নমুনার জন্য সার্ভিস সংযুক্ত নেই।'));
 }

 return <div ref={root} className={`figma-page page-${page}`} onClick={click} aria-busy={pending}>
  <div className="mobile-page-nav"><a href="/">HarvestV</a><select aria-label={t('Go to page')} value={'/'+page} onChange={e => router.push(e.target.value)}>{[['/','Home'],['/dashboard','Dashboard'],['/my-farm','My Farm'],['/crop-rotation','Crop Rotation'],['/information-check','Information Check'],['/feedback','Feedback']].map(([url,label]) => <option key={url} value={url}>{t(label)}</option>)}</select><div className="page-language-switch"><button data-action="EN" aria-pressed={language==='en'} lang="en">EN</button><button data-action="বাংলা" aria-pressed={language==='bn'} lang="bn">বাংলা</button></div></div>
  {page==='my-farm' && districtMount && createPortal(<section className="connected-panel server-district" onClick={e => e.stopPropagation()}><label>{say('Farm district','খামারের জেলা')}<select value={district} onChange={e => setDistrict(e.target.value)} aria-label={say('Farm district','খামারের জেলা')}><option value="">{say('Choose a district','জেলা বেছে নিন')}</option>{districtList.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label><p>{say('Choose the district used for server advisories, then use Save Farm below.','সার্ভারের পরামর্শের জন্য জেলা বেছে নিন। এরপর নিচের Save Farm বাটন ব্যবহার করুন।')}</p></section>,districtMount)}
  {children}
  {page==='feedback' && reports.length>0 && <section className="server-reports"><h2>{say('Feedback saved to the server','সার্ভারে সংরক্ষিত মতামত')}</h2>{reports.map(report => <article key={report.id}><p>{report.message}</p><small>{report.created_at.slice(0,10)}</small></article>)}</section>}
  <div className="prototype-label">{say('Backend connected · marked design examples remain illustrative','ব্যাকএন্ড সংযুক্ত · চিহ্নিত নকশার তথ্যগুলো নমুনা')}</div>
  {pending && <div className="page-status" role="status">{say('Saving or checking…','সংরক্ষণ বা যাচাই হচ্ছে…')}</div>}
  {message && <div className="page-status" role="status"><p>{message}</p><button aria-label={t('Dismiss message')} onClick={e => {e.stopPropagation();setMessage('');}}>×</button></div>}
 </div>;
}
