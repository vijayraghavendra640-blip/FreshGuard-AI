import { Logo } from './Logo';

export function Header({ onHome }: { onHome: () => void }) {
  return (
    <header className="nav">
      <div className="container nav-inner">
        <button type="button" className="brand" onClick={onHome} aria-label="FreshGuard AI home">
          <Logo size={32} />
          <span className="brand-name">FreshGuard <span>AI</span></span>
        </button>
      </div>
    </header>
  );
}
