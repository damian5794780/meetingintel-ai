import { ArrowUpRight, AudioLines } from 'lucide-react';
import { ResearchWorkspace } from '@/features/research/research-workspace';

export default function Home() {
  return (
    <>
      <header className="site-header no-print">
        <div className="header-content">
          <a className="brand" href="/">
            <span className="brand-icon"><AudioLines size={21}/></span>
            MeetingIntel
          </a>
          <a className="project-link" href="https://github.com/damian5794780/meetingintel-ai" target="_blank" rel="noreferrer">
            View project <ArrowUpRight size={15}/>
          </a>
        </div>
      </header>

      <main className="workspace">
        <section className="workspace-heading no-print">
          <h1>Meeting briefings</h1>
          <p>Review recent developments, check the sources, and prepare questions for your meeting.</p>
        </section>
        <ResearchWorkspace/>
      </main>
    </>
  );
}
