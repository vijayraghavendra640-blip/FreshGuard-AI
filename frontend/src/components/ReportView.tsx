import { useMemo, useState } from 'react';
import type { Report, Verdict } from '../types';
import { ClaimCard } from './ClaimCard';
import { ScoreGauge, VerdictBadge } from './common';
import { ArrowLeft } from './icons';

type Filter = 'All' | Verdict;
const FILTERS: Filter[] = ['All', 'Stale / Outdated', 'Needs Review', 'Verified'];

export function ReportView({ report, onReset }: { report: Report; onReset: () => void }) {
  const [filter, setFilter] = useState<Filter>('All');
  const counts: Record<Filter, number> = useMemo(
    () => ({ All: report.claims.length, 'Stale / Outdated': report.stale_count, 'Needs Review': report.needs_review_count, Verified: report.verified_count }),
    [report],
  );
  const shown = report.claims
    .map((c, i) => ({ c, i }))
    .filter(({ c }) => filter === 'All' || c.verdict === filter);

  const stats = [
    { label: 'Claims identified', value: report.total_claims, tone: '' },
    { label: 'Time-sensitive', value: report.time_sensitive_count, tone: '' },
    { label: 'Stale / outdated', value: report.stale_count, tone: 'bad' },
    { label: 'Needs review', value: report.needs_review_count, tone: 'warn' },
    { label: 'Verified', value: report.verified_count, tone: 'good' },
  ];

  return (
    <section className="container page">
      <div className="page-head">
        <div>
          <h1>Freshness report</h1>
          <p className="muted">Each claim was checked against current web sources.</p>
        </div>
      </div>

      <div className="panel summary">
        <div className="summary-score">
          <ScoreGauge score={report.overall_score} verdict={report.overall_verdict} />
          <VerdictBadge verdict={report.overall_verdict} size="lg" />
          <span className="muted small">Overall freshness score</span>
        </div>
        <div className="stats">
          {stats.map((s) => (
            <div key={s.label} className={`stat${s.tone ? ` stat-${s.tone}` : ''}`}>
              <span className="stat-value">{s.value}</span>
              <span className="stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {report.warnings.length > 0 && (
        <div className="alert alert-soft" role="status">
          {report.warnings.map((w, i) => <p key={i}>{w}</p>)}
        </div>
      )}

      <div className="section-head">
        <h2>Claim-by-claim verification</h2>
        <div className="segmented" role="tablist" aria-label="Filter claims">
          {FILTERS.map((f) => (
            <button key={f} role="tab" aria-selected={filter === f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
              {f}<span className="seg-count">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      {report.claims.length === 0 && (
        <div className="panel empty">No verifiable factual claims were found. Try an answer with concrete facts such as prices, versions or names.</div>
      )}
      {report.claims.length > 0 && shown.length === 0 && <div className="panel empty">No claims in this category.</div>}
      <div className="claims">
        {shown.map(({ c, i }) => <ClaimCard key={c.id} claim={c} index={i} />)}
      </div>

      <div className="page-foot">
        <button type="button" className="btn btn-primary btn-lg" onClick={() => { onReset(); window.scrollTo({ top: 0 }); }}>
          <ArrowLeft size={16} /> Check another answer
        </button>
      </div>
    </section>
  );
}
