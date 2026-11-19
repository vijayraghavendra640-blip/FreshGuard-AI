import { useEffect, useState } from 'react';
import type { RunState } from '../useVerification';
import { VerdictBadge } from './common';
import { Check } from './icons';

const FRIENDLY: Record<string, string> = {
  'Evidence Agent': 'Searching live sources',
  'Verifier Agent': 'Comparing with evidence',
  'Hallucination Auditor': 'Double-checking the result',
  'Temporal Check': 'Checking the date',
};

function Elapsed({ since }: { since: number | null }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, []);
  return since ? <span className="elapsed">{Math.max(0, Math.round((now - since) / 1000))}s</span> : null;
}

export function LiveProgress({ state, onCancel }: { state: RunState; onCancel: () => void }) {
  const total = state.pending.length;
  const done = Object.keys(state.results).length;
  const steps = [
    { label: 'Identify claims', state: state.stage === 'extracting' ? 'active' : 'done' },
    { label: 'Verify against live sources', state: state.stage === 'verifying' ? 'active' : state.stage === 'extracting' ? '' : 'done' },
    { label: 'Score freshness', state: '' },
  ];

  return (
    <section className="container page" aria-live="polite" aria-busy="true">
      <div className="panel progress">
        <div className="progress-head">
          <div>
            <h2>Analyzing your answer</h2>
            <p className="muted">{total ? `${done} of ${total} claims checked` : 'Reading the answer and identifying claims…'}</p>
          </div>
          <div className="progress-actions">
            <Elapsed since={state.startedAt} />
            <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          </div>
        </div>

        <div className="bar" aria-hidden="true">
          <span style={{ width: `${total ? Math.max(6, (done / total) * 100) : 6}%` }} />
        </div>

        <ol className="steps">
          {steps.map((s) => (
            <li key={s.label} className={s.state}>
              <span className="step-dot">{s.state === 'done' ? <Check size={12} /> : null}</span>
              {s.label}
            </li>
          ))}
        </ol>

        {total > 0 && (
          <ul className="live-list">
            {state.pending.map((c) => {
              const result = state.results[c.id];
              const step = state.lastStep[c.id];
              return (
                <li key={c.id}>
                  <div className="live-text">
                    <span>{c.claim}</span>
                    {!result && <small className="muted">{step ? FRIENDLY[step.agent] ?? 'Working' : 'Queued'}…</small>}
                  </div>
                  {result ? <VerdictBadge verdict={result.verdict} /> : <span className="spinner" aria-label="in progress" />}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
