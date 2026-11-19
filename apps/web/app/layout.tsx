import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'MeetingIntel AI — Arrive informed', description: 'Turn recent web research into a concise, source-backed meeting briefing.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
