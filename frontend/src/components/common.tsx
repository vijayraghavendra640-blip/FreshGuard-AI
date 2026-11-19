import type { OverallVerdict } from '../types';
import { AlertTriangle, Check, HelpCircle } from './icons';

export type Tone = 'good' | 'warn' | 'bad' | 'muted';

export function verdictTone(v: string): Tone {
  if (v === 'Verified') return 'good';
  if (v === 'Needs Review') return 'warn';
  if (v === 'Stale / Outdated') return 'bad';
  return 'muted';
}

const VERDICT_ICON = { good: Check, warn: HelpCircle, bad: AlertTriangle, muted: HelpCircle };

export function VerdictBadge({ verdict, size = 'md' }: { verdict: string; size?: 'md' | 'lg' }) {
  const tone = verdictTone(verdict);
  const Icon = VERDICT_ICON[tone];
  return (
    <span className={`badge badge-${tone} badge-${size}`}>
      <Icon size={size === 'lg' ? 15 : 13} />
      {verdict}
    </span>
  );
}

/** Semi-circular gauge. Bands match the backend: 0-49 stale, 50-74 needs review, 75-100 verified. */
export function ScoreGauge({ score, verdict }: { score: number | null; verdict: OverallVerdict }) {
  const r = 84;
  const cx = 100;
  const cy = 100;
  const point = (v: number) => {
    const a = Math.PI * (1 - v / 100);
    return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  };
  const arc = (from: number, to: number) => {
    const [x1, y1] = point(from);
    const [x2, y2] = point(to);
    return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  };
  const tone = verdictTone(verdict);
  const value = Math.max(0, Math.min(100, score ?? 0));
  return (
    <div className="gauge" role="img" aria-label={score === null ? 'No score' : `Overall freshness score ${score} out of 100`}>
      <svg viewBox="0 0 200 112">
        <path d={arc(0, 100)} className="gauge-track" />
        {score !== null && value > 0 && <path d={arc(0, value)} className={`gauge-fill fill-${tone}`} />}
      </svg>
      <div className="gauge-center">
        <span className={`gauge-number tone-${tone}`}>{score === null ? '—' : score}</span>
        <span className="gauge-max">out of 100</span>
      </div>
    </div>
  );
}
