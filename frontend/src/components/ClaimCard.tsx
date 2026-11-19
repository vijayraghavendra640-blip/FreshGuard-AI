import { isSafeUrl } from '../api';
import type { ClaimResult } from '../types';
import { verdictTone, VerdictBadge } from './common';
import { ExternalLink, Globe } from './icons';

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
}

export const NEEDS_REVIEW_TEXT = 'Not enough trustworthy live evidence to judge this claim.';

export function ClaimCard({ claim, index }: { claim: ClaimResult; index: number }) {
  const tone = verdictTone(claim.verdict);
  const source = claim.cited_source;
  const computed = claim.vetting_method === 'computed';
  const latest = claim.current_fact || claim.explanation;

  return (
    <article className={`claim claim-${tone}`}>
      <header className="claim-top">
        <span className="claim-index">Claim {index + 1}</span>
        <div className="claim-meta">
          <VerdictBadge verdict={claim.verdict} />
          <span className="claim-score" title="Freshness score">
            <strong className={`tone-${tone}`}>{claim.freshness_score}</strong>/100
          </span>
        </div>
      </header>

      <p className="claim-text">“{claim.claim}”</p>

      {claim.verdict === 'Needs Review' ? (
        <div className="claim-note">{NEEDS_REVIEW_TEXT}</div>
      ) : (
        <dl className="claim-details">
          <div className="detail">
            <dt>Current latest information</dt>
            <dd className="detail-text">{latest}</dd>
          </div>
          <div className="detail">
            <dt>Comparison web URL</dt>
            <dd>
              {source && isSafeUrl(source.url) ? (
                <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-card">
                  <span className="source-icon"><Globe size={16} /></span>
                  <span className="source-body">
                    <span className="source-title">{source.title}</span>
                    <span className="source-meta">
                      {source.domain}
                      {source.published_date ? ` · Published ${formatDate(source.published_date)}` : ''}
                    </span>
                  </span>
                  <ExternalLink size={16} className="source-arrow" />
                </a>
              ) : computed ? (
                <span className="muted">Checked against today's date</span>
              ) : (
                <span className="muted">No source available</span>
              )}
            </dd>
          </div>
        </dl>
      )}
    </article>
  );
}
