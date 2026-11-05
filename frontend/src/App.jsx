import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, BookOpen, Bot, Check, ChevronDown, CircleAlert, Clock3,
  FileCheck2, HeartPulse, History, MessageCircle, Shield, ShieldAlert,
  Sparkles, UserRound, Waves,
} from 'lucide-react';
import ChatPage from './pages/ChatPage.jsx';
import HistoryPage from './pages/HistoryPage.jsx';
import EmergencyButton from './components/EmergencyButton.jsx';
import { api, INITIAL_MESSAGE } from './services/api.js';

function Capability({ icon, text }) {
  return <div className="capability"><span className="capability-icon">{icon}</span><span>{text}</span><Check size={13} className="capability-check" /></div>;
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [profileId, setProfileId] = useState('');
  const [activePage, setActivePage] = useState('chat');
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    Promise.all([api('/health'), api('/demo/profiles')]).then(([status, list]) => {
      setHealth(status);
      setProfiles(list.items || []);
      setProfileId(list.items?.[0]?.id || '');
    }).catch((exception) => setError(exception.message));
  }, []);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, busy]);

  useEffect(() => {
    if (activePage !== 'history' || !profileId) return;
    setHistoryLoading(true);
    api(`/demo/profiles/${encodeURIComponent(profileId)}/history`)
      .then(setHistory).catch((exception) => setError(exception.message)).finally(() => setHistoryLoading(false));
  }, [activePage, profileId]);

  const selectedProfile = useMemo(() => profiles.find((profile) => profile.id === profileId), [profiles, profileId]);

  async function sendMessage(text = draft) {
    const clean = text.trim();
    if (!clean || busy) return;
    setError('');
    setDraft('');
    setMessages((items) => [...items, { role: 'user', content: clean }]);
    setBusy(true);
    try {
      const result = await api('/chat', {
        method: 'POST',
        body: JSON.stringify({ message: clean, demo_profile_id: profileId || null, session_id: crypto.randomUUID() }),
      });
      setMessages((items) => [...items, { role: 'assistant', ...result }]);
    } catch (exception) {
      setMessages((items) => [...items, {
        role: 'assistant', status: 'ERROR',
        answer: `Mình chưa kết nối được với backend: ${exception.message}`,
        trace: [{ step: 'api_request', status: 'FAILED' }],
      }]);
    } finally {
      setBusy(false);
      textareaRef.current?.focus();
    }
  }

  function changePage(page) {
    setActivePage(page);
    setError('');
  }

  function changeProfile(value) {
    setProfileId(value);
    setMessages([INITIAL_MESSAGE]);
    setHistory(null);
    setError('');
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-lockup">
        <div className="brand-mark"><HeartPulse size={21} strokeWidth={2.2} /></div>
        <div><div className="brand-name">DiaCare<span> AI</span></div><div className="brand-caption">HEALTH COMPANION · DEMO</div></div>
      </div>
      <div className="side-label">KHÔNG GIAN</div>
      <nav className="main-nav" aria-label="Điều hướng chính">
        <button className={`nav-item ${activePage === 'chat' ? 'active' : ''}`} onClick={() => changePage('chat')}><MessageCircle size={18} /><span>Trò chuyện</span><span className="nav-dot" /></button>
        <button className={`nav-item ${activePage === 'history' ? 'active' : ''}`} onClick={() => changePage('history')}><History size={18} /><span>Lịch sử chỉ số</span></button>
      </nav>
      <div className="sidebar-bottom">
        <div className="local-card"><div className="local-icon"><Shield size={17} /></div><div><strong>Chạy cục bộ</strong><span>Chỉ hồ sơ tổng hợp</span></div><span className="online-dot" /></div>
        <div className="sidebar-note">Không nhập dữ liệu sức khỏe hoặc thông tin định danh thật.</div>
        <div className="profile-mini"><div className="mini-avatar"><UserRound size={16} /></div><div className="mini-copy"><strong>{selectedProfile?.display_name || 'Đang tải hồ sơ'}</strong><span>{selectedProfile ? `${selectedProfile.age} tuổi · tổng hợp` : 'Chưa chọn hồ sơ'}</span></div><span className="mini-check"><Check size={14} /></span></div>
      </div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <div className="breadcrumbs"><span>DiaCare AI</span><span className="crumb-slash">/</span><strong>{activePage === 'chat' ? 'Trò chuyện' : 'Lịch sử chỉ số'}</strong></div>
        <div className="topbar-actions">
          <div className="profile-select-wrap">
            <span className="profile-select-label">HỒ SƠ MÔ PHỎNG</span>
            <select aria-label="Chọn hồ sơ mô phỏng" value={profileId} onChange={(event) => changeProfile(event.target.value)}>
              {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.id} · {profile.age} tuổi</option>)}
            </select>
            <ChevronDown className="select-chevron" size={14} />
          </div>
          <EmergencyButton />
        </div>
      </header>

      <div className="workspace">
        <section className="content-column">
          <div className="demo-warning"><ShieldAlert size={17} /><span><strong>Bản demo giáo dục.</strong> Không dùng để chẩn đoán, điều trị hoặc thay thế nhân viên y tế. Việc trích dẫn WHO/NIDDK không hàm ý các cơ quan này chứng thực DiaCare AI; tài liệu CDC không hàm ý CDC, ATSDR, HHS hay Chính phủ Hoa Kỳ chứng thực DiaCare AI.</span><span className="warning-tag">SYNTHETIC ONLY</span></div>
          <div className="safety-note"><CircleAlert size={13} /><span>Nhận diện cấp cứu là thử nghiệm và có thể bỏ sót. Nếu có dấu hiệu nặng, hãy gọi 115 ngay.</span></div>
          {error && <div className="inline-error"><CircleAlert size={16} />{error}<button onClick={() => setError('')}>Đóng</button></div>}
          {activePage === 'chat' ? <ChatPage
            messages={messages} busy={busy} draft={draft} setDraft={setDraft} onSend={sendMessage}
            textareaRef={textareaRef} bottomRef={bottomRef} profile={selectedProfile}
          /> : <HistoryPage profile={selectedProfile} history={history} loading={historyLoading} />}
        </section>

        <aside className="insight-rail">
          <div className="rail-heading"><span>TRẠNG THÁI HỆ THỐNG</span><span className="rail-live"><i /> LOCAL</span></div>
          <div className="status-card"><div className="status-icon green"><Bot size={18} /></div><div className="status-main"><strong>Agent điều phối</strong><span>LangGraph · local</span></div><span className="status-check"><Check size={13} /></span></div>
          <div className="status-card"><div className="status-icon amber"><Activity size={18} /></div><div className="status-main"><strong>Mô hình nghiên cứu</strong><span>{health?.model?.available ? 'Nạp mô hình' : 'Chưa có artifact'}</span></div><span className={`state-pill ${health?.model?.available ? 'ready' : 'pending'}`}>{health?.model?.available ? 'SẴN SÀNG' : 'CHỜ DỮ LIỆU'}</span></div>
          <div className="status-card"><div className="status-icon blue"><BookOpen size={18} /></div><div className="status-main"><strong>Knowledge Base</strong><span>{health?.knowledge_base?.approved_document_count ?? '—'} nguồn đã duyệt</span></div><span className={`state-pill ${(health?.knowledge_base?.approved_document_count || 0) ? 'ready' : 'pending'}`}>{(health?.knowledge_base?.approved_document_count || 0) ? 'SẴN SÀNG' : 'ĐANG RÀ SOÁT'}</span></div>
          <div className="rail-divider" />
          <div className="rail-heading rail-subhead"><span>TRỢ LÝ CÓ THỂ</span></div>
          <div className="capability-list">
            <Capability icon={<Activity size={15} />} text="Tính BMI" />
            <Capability icon={<Waves size={15} />} text="Diễn giải ngưỡng xét nghiệm" />
            <Capability icon={<History size={15} />} text="Xem lịch sử mô phỏng" />
            <Capability icon={<FileCheck2 size={15} />} text="Tìm nguồn đã được duyệt" />
          </div>
          <div className="model-notice"><Sparkles size={15} /><div><strong>Không tạo số liệu giả</strong><p>Model score và citation chỉ xuất hiện khi có artifact hoặc nguồn đã duyệt.</p></div></div>
          <div className="rail-footer"><Clock3 size={13} /> Phiên demo không lưu hội thoại</div>
        </aside>
      </div>
    </main>
  </div>;
}
