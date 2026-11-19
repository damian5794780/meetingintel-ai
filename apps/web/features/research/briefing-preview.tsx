import { FileText } from 'lucide-react';

export function BriefingPreview() {
  return (
    <section className="preview-card no-print" aria-labelledby="preview-title">
      <header className="preview-header">
        <h2 id="preview-title"><FileText size={18}/> Example briefing</h2>
        <span className="preview-mode">Fictional demo</span>
      </header>
      <div className="preview-body">
        <div className="preview-intro">
          <p>Northstar Labs</p>
          <span>Partnership meeting</span>
        </div>
        <section className="preview-finding">
          <div className="preview-section-label"><h3>Recent development</h3><span className="citation">S1</span></div>
          <p>Northstar Labs introduced Atlas, a workspace for teams to organize and review AI research.</p>
          <small>Source · Northstar Labs product announcement</small>
        </section>
        <section className="preview-question">
          <h3>Question to ask</h3>
          <p>What would make an initial collaboration successful?</p>
        </section>
      </div>
    </section>
  );
}
