import { Header } from './components/Header';
import { Home } from './components/Home';
import { LiveProgress } from './components/LiveProgress';
import { ReportView } from './components/ReportView';
import { useVerification } from './useVerification';

export function App() {
  const { state, run, cancel, reset } = useVerification();
  const running = state.stage === 'extracting' || state.stage === 'verifying';

  return (
    <>
      <Header onHome={reset} />
      <main className="main">
        {(state.stage === 'idle' || state.stage === 'error') && <Home initialText={state.input} error={state.error} onRun={run} />}
        {running && <LiveProgress state={state} onCancel={cancel} />}
        {state.stage === 'done' && state.report && <ReportView report={state.report} onReset={reset} />}
      </main>
      <footer className="footer">
        <div className="container">
          Powered by <strong>Tavily</strong> and <strong>Bifrost by Maxim AI</strong>
        </div>
      </footer>
    </>
  );
}
