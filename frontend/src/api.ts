import type { Preset, StreamEvent } from './types';

const API = '/api';

export class ApiError extends Error {
  constructor(message: string, public status = 0) {
    super(message);
  }
}

async function readError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const body = JSON.parse(text);
    const detail = body.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg ?? String(d)).join('; ');
  } catch {
    /* not JSON (e.g. a proxy error page) */
  }
  if (res.status === 429) return 'Too many requests. Please wait a minute and try again.';
  if (res.status >= 500) return `The server is unavailable (HTTP ${res.status}). Check that the backend and Bifrost are running.`;
  return `Request failed (HTTP ${res.status}).`;
}

export async function fetchPresets(): Promise<Preset[]> {
  const res = await fetch(`${API}/presets`);
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  const body = await res.json();
  return Object.values(body.presets ?? {}) as Preset[];
}

/** POST the answer to the streaming endpoint and invoke `onEvent` for each Server-Sent Event. */
export async function streamVerification(
  text: string,
  onEvent: (evt: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API}/verify/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ text }),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    throw new ApiError('Cannot reach the FreshGuard backend. Is it running on port 8005?');
  }
  if (!res.ok || !res.body) throw new ApiError(await readError(res), res.status);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const data = chunk
        .split('\n')
        .filter((l) => l.startsWith('data: '))
        .map((l) => l.slice(6))
        .join('\n');
      if (!data) continue; // keep-alive comment
      try {
        onEvent(JSON.parse(data) as StreamEvent);
      } catch {
        /* ignore malformed event */
      }
    }
  }
}

export function isSafeUrl(url: string | undefined | null): url is string {
  if (!url) return false;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:';
  } catch {
    return false;
  }
}
