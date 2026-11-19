import { useEffect, useState } from 'react';
import { fetchPresets } from '../api';
import type { Preset } from '../types';
import { ArrowRight, Clock, Gauge, Globe, ListChecks } from './icons';

const LIMIT = 8000;

const FEATURES = [
  { icon: ListChecks, title: 'Claim identification', text: 'The answer is split into individual factual statements.' },
  { icon: Clock, title: 'Freshness detection', text: 'Claims about pricing, APIs, laws and leadership are flagged as time-sensitive.' },
  { icon: Globe, title: 'Live verification', text: 'Each claim is re-checked against current web sources.' },
  { icon: Gauge, title: 'Freshness scoring', text: 'Every claim and the full answer get a score based on the evidence.' },
];

export function Home({ initialText, error, onRun }: { initialText: string; error: string | null; onRun: (text: string) => void }) {
  const [text, setText] = useState(initialText);
  const [presets, setPresets] = useState<Preset[]>([]);
  const trimmed = text.trim();
  const tooLong = text.length > LIMIT;

  useEffect(() => {
    fetchPresets().then(setPresets).catch(() => setPresets([]));
  }, []);

  const submit = () => {
    if (trimmed && !tooLong) onRun(trimmed);
  };

  return (
    <>
      <section className="hero">
        <div className="hero-glow" aria-hidden="true" />
        <div className="container hero-inner">
          <h1>Catch outdated facts<br />in AI answers</h1>
          <p className="hero-sub">Paste a response from any LLM. FreshGuard checks every time-sensitive claim against live sources and tells you what is still true.</p>
        </div>
      </section>

      <section className="container composer-wrap">
        <div className="composer">
          {error && (
            <div className="alert" role="alert">
              <strong>The analysis did not complete.</strong> {error}
            </div>
          )}
          <label htmlFor="fg-input" className="composer-label">AI-generated answer</label>
          <textarea
            id="fg-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') submit();
            }}
            rows={7}
            placeholder="Paste the answer you want to check, e.g. “ChatGPT Plus is OpenAI's highest paid tier at $20 per month.”"
            aria-invalid={tooLong}
          />
          <div className="composer-footer">
            <div className="examples">
              {presets.length > 0 && <span className="examples-label">Examples</span>}
              {presets.map((p) => (
                <button key={p.id} type="button" className="example" title={p.description} onClick={() => setText(p.text)}>
                  {p.title}
                </button>
              ))}
            </div>
            <div className="composer-actions">
              <span className={tooLong ? 'counter over' : 'counter'}>{text.length.toLocaleString()} / {LIMIT.toLocaleString()}</span>
              <button type="button" className="btn btn-primary" onClick={submit} disabled={!trimmed || tooLong}>
                Check freshness <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="container features" aria-label="How FreshGuard works">
        {FEATURES.map(({ icon: Icon, title, text: body }, i) => (
          <div key={title} className="feature">
            <span className="feature-icon"><Icon size={18} /></span>
            <span className="feature-step">0{i + 1}</span>
            <h3>{title}</h3>
            <p>{body}</p>
          </div>
        ))}
      </section>
    </>
  );
}
