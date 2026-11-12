export interface District { id: string; name: string; division: string }
export interface Crop { id: string; name_bn: string; calendar: [string, string] }
export interface AdvisoryWindow { start: string; end: string; mean_score: number }
export interface Advisory {
  district: string; district_id: string; crop: string; status: 'GO' | 'WAIT' | 'AVOID'; today_score: number;
  best_window: AdvisoryWindow | null; next_best_window: AdvisoryWindow | null;
  reasons: string[]; action: string; confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  confidence_reason: string; data_freshness: Record<string, string | null>;
  model_version: string; limitations: string[];
}
export interface FarmProfile { district_id: string; fields: Record<string, string> }
export interface FarmResponse { farm: FarmProfile | null; updated_at: string | null }
export interface FeedbackRecord { id: string; message: string; created_at: string }
export interface SavedAdvisory extends Advisory { id: string; created_at: string }
export interface Conditions { series: { day: string; source: string; values: Record<string, number | null>; data_age_days: number }[] }

export function deviceToken(): string {
  let token = localStorage.getItem('harvestv-device-token');
  if (!token || !/^[a-f0-9]{64}$/.test(token)) {
    token = Array.from(crypto.getRandomValues(new Uint8Array(32)), x => x.toString(16).padStart(2, '0')).join('');
    localStorage.setItem('harvestv-device-token', token);
  }
  return token;
}

export async function request<T>(path: string, options: { method?: 'GET' | 'POST' | 'PUT'; body?: unknown; private?: boolean; signal?: AbortSignal; lang?: 'en' | 'bn' } = {}): Promise<T> {
  const base = (process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.private) headers['X-Device-Token'] = deviceToken();
  let response: Response;
  const timeout = AbortSignal.timeout(20000);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  try {
    response = await fetch(`${base}${path}`, { method: options.method ?? 'GET', headers, body: options.body === undefined ? undefined : JSON.stringify(options.body), signal, cache: 'no-store' });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new Error(options.lang === 'bn' ? 'সার্ভারে সংযোগ করা যাচ্ছে না। ব্যাকএন্ড চালু আছে কি না দেখুন।' : 'Cannot reach the server. Check that the backend is running on port 8000.');
  }
  const body = await response.json();
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(options.lang === 'bn' && detail?.message_bn ? detail.message_bn : typeof detail === 'string' ? detail : detail?.message ?? `Request failed (${response.status})`);
  }
  return body as T;
}

export const districts = (signal?: AbortSignal) => request<District[]>('/api/v1/districts', { signal });
export const crops = (signal?: AbortSignal) => request<Crop[]>('/api/v1/crops', { signal });
export const advisory = (district: string, crop: string, lang: 'en' | 'bn', signal?: AbortSignal) =>
  request<Advisory>('/api/v1/advisory?' + new URLSearchParams({ district, crop, lang }), { signal, lang });
export const getFarm = (signal?: AbortSignal) => request<FarmResponse>('/api/v1/farm', { private: true, signal });
export const saveFarm = (farm: FarmProfile) => request<FarmResponse>('/api/v1/farm', { private: true, method: 'PUT', body: farm });
export const getFeedback = (signal?: AbortSignal) => request<FeedbackRecord[]>('/api/v1/feedback', { private: true, signal });
export const sendFeedback = (message: string, id: string) => request('/api/v1/feedback', { private: true, method: 'POST', body: { id, message } });
export const getSaved = (signal?: AbortSignal) => request<SavedAdvisory[]>('/api/v1/saved-advisories', { private: true, signal });
