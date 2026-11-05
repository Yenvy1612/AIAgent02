import { ChartColumn, HeartPulse, Menu, MessageCircle, X } from 'lucide-react';

const PAGES = [
  { id: 'chat', label: 'Trò chuyện', icon: MessageCircle },
  { id: 'history', label: 'Lịch sử chỉ số', icon: ChartColumn },
];

export default function Sidebar({ activePage, onChangePage, profile, mobileOpen, onToggleMobile }) {
  return <aside className={`sidebar ${mobileOpen ? 'is-open' : ''}`}>
    <div className="brand-lockup">
      <div className="brand-mark"><HeartPulse size={28} strokeWidth={2} /></div>
      <div><div className="brand-name">DiaCare <span>AI</span></div><div className="brand-caption">Health Companion · Diabetes</div></div>
      <button className="mobile-menu-toggle" type="button" onClick={onToggleMobile} aria-label={mobileOpen ? 'Đóng điều hướng' : 'Mở điều hướng'} aria-expanded={mobileOpen} aria-controls="primary-navigation">
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>
    </div>
    <nav id="primary-navigation" className="main-nav" aria-label="Điều hướng chính">
      {PAGES.map(({ id, label, icon: Icon }) => {
        const active = activePage === id;
        return <button key={id} className={`nav-item ${active ? 'active' : ''}`} aria-label={label} aria-current={active ? 'page' : undefined} title={label} onClick={() => onChangePage(id)}>
          <Icon size={22} strokeWidth={1.8} /><span>{label}</span>{active && <span className="nav-dot" />}
        </button>;
      })}
    </nav>
    <div className="sidebar-meta">
      <div className="local-status"><i />Chạy cục bộ</div>
      <div className="sidebar-profile"><span>Hồ sơ mô phỏng</span><strong>{profile ? `${profile.id} · ${profile.age} tuổi` : 'Đang tải hồ sơ…'}</strong></div>
      <small>Phiên demo không lưu hội thoại</small>
    </div>
  </aside>;
}
