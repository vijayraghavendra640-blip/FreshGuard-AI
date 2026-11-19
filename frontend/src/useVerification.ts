import { useCallback, useReducer, useRef } from 'react';
import { ApiError, streamVerification } from './api';
import type { ClaimResult, PendingClaim, Report, Stage, StreamEvent, TraceStep } from './types';

export interface RunState {
  stage: Stage;
  input: string;
  pending: PendingClaim[];
  lastStep: Record<string, TraceStep>;
  results: Record<string, ClaimResult>;
  report: Report | null;
  error: string | null;
  startedAt: number | null;
}

const initial: RunState = { stage: 'idle', input: '', pending: [], lastStep: {}, results: {}, report: null, error: null, startedAt: null };

type Action =
  | { type: 'start'; input: string }
  | { type: 'event'; evt: StreamEvent }
  | { type: 'error'; message: string }
  | { type: 'reset' };

function reducer(state: RunState, action: Action): RunState {
  switch (action.type) {
    case 'start':
      return { ...initial, input: action.input, stage: 'extracting', startedAt: Date.now() };
    case 'reset':
      return { ...initial, input: state.input };
    case 'error':
      return { ...state, stage: 'error', error: action.message };
    case 'event': {
      const e = action.evt;
      switch (e.type) {
        case 'stage':
          return e.stage === 'extracting' || e.stage === 'verifying' ? { ...state, stage: e.stage } : state;
        case 'claims':
          return { ...state, pending: e.claims };
        case 'claim_step':
          return { ...state, lastStep: { ...state.lastStep, [e.claim_id]: e.step } };
        case 'claim_result':
          return { ...state, results: { ...state.results, [e.claim.id]: e.claim } };
        case 'report':
          return { ...state, report: e.report, stage: 'done' };
        case 'error':
          return { ...state, stage: 'error', error: e.detail };
        case 'done':
          return state.report || state.stage === 'error' ? state : { ...state, stage: 'error', error: 'The analysis ended without a report. Please try again.' };
      }
    }
  }
  return state;
}

export function useVerification() {
  const [state, dispatch] = useReducer(reducer, initial);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(async (text: string) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const timeout = window.setTimeout(() => ctrl.abort('timeout'), 6 * 60 * 1000);
    dispatch({ type: 'start', input: text });
    try {
      await streamVerification(text, (evt) => dispatch({ type: 'event', evt }), ctrl.signal);
    } catch (err) {
      if (abortRef.current !== ctrl) return; // superseded by a newer run or a reset
      if ((err as Error).name === 'AbortError' || ctrl.signal.aborted) {
        dispatch({ type: 'error', message: ctrl.signal.reason === 'timeout' ? 'The analysis took too long and was stopped.' : 'Analysis cancelled.' });
      } else {
        dispatch({ type: 'error', message: err instanceof ApiError ? err.message : 'Something went wrong. Please try again.' });
      }
    } finally {
      window.clearTimeout(timeout);
    }
  }, []);

  const cancel = useCallback(() => abortRef.current?.abort(), []);
  const reset = useCallback(() => {
    const ctrl = abortRef.current;
    abortRef.current = null;
    ctrl?.abort();
    dispatch({ type: 'reset' });
  }, []);

  return { state, run, cancel, reset };
}
