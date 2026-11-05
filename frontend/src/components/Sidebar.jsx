import { ChartColumn, HeartPulse, MessageCircle } from 'lucide-react';

const PAGES = [
  { id: 'chat', label: 'Trò chuyện', icon: MessageCircle },
  { id: 'history', label: 'Lịch sử chỉ số', icon: ChartColumn },
];

function SidebarDecoration() {
  return <svg className="sidebar-deco" viewBox="0 0 272 360" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
    <path d="M0 150C70 90 150 120 272 200V360H0Z" fill="#1565c4" opacity=".45" />
    <path d="M0 230C80 170 170 215 272 275V360H0Z" fill="#1e80e6" opacity=".55" />
    <path d="M0 300C90 262 170 292 272 335V360H0Z" fill="#6fb8ff" opacity=".5" />
    <rect x="146" y="118" width="26" height="82" rx="7" fill="#5da6f2" opacity=".7" />
    <rect x="118" y="146" width="82" height="26" rx="7" fill="#5da6f2" opacity=".7" />
    <path d="M204 112C204 88 222 74 240 72C242 96 228 112 204 112Z" fill="#7cc1ff" opacity=".55" />
    <path d="M192 104C180 90 182 74 192 62C204 76 204 92 192 104Z" fill="#7cc1ff" opacity=".4" />
  </svg>;
}

export default function Sidebar({ activePage, onChangePage }) {
  return <aside className="sidebar">
    <SidebarDecoration />
    <div className="brand-lockup">
      <div className="brand-mark"><HeartPulse size={28} strokeWidth={2} /></div>
      <div><div className="brand-name">DiaCare <span>AI</span></div><div className="brand-caption">Health Companion · Diabetes</div></div>
    </div>
    <nav className="main-nav" aria-label="Điều hướng chính">
      {PAGES.map(({ id, label, icon: Icon }) => {
        const active = activePage === id;
        return <button key={id} className={`nav-item ${active ? 'active' : ''}`} aria-label={label} aria-current={active ? 'page' : undefined} title={label} onClick={() => onChangePage(id)}>
          <Icon size={22} strokeWidth={1.8} /><span>{label}</span>{active && <span className="nav-dot" />}
        </button>;
      })}
    </nav>
  </aside>;
}
