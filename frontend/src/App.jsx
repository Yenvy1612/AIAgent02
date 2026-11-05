import { useEffect, useMemo, useRef, useState } from 'react';
import { CircleAlert, Info } from 'lucide-react';
import ChatPage from './pages/ChatPage.jsx';
import HistoryPage from './pages/HistoryPage.jsx';
import InsightRail from './components/InsightRail.jsx';
import Sidebar from './components/Sidebar.jsx';
import Topbar from './components/Topbar.jsx';
import { api, INITIAL_MESSAGE } from './services/api.js';

export default function App() {
  const [health, setHealth] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [profileId, setProfileId] = useState('');
  const [activePage, setActivePage] = useState('chat');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [systemPanelOpen, setSystemPanelOpen] = useState(false);
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

  useEffect(() => {
    function closePanels(event) {
      if (event.key === 'Escape') {
        setMobileNavOpen(false);
        setSystemPanelOpen(false);
      }
    }
    window.addEventListener('keydown', closePanels);
    return () => window.removeEventListener('keydown', closePanels);
  }, []);

  // Scroll only the message list, so the safety banners above it stay in view.
  // A new answer opens at its first line: an emergency notice must never sit below the fold.
  useEffect(() => {
    const list = bottomRef.current?.parentElement;
    if (!list) return;
    const rows = list.querySelectorAll('.message-row');
    const last = rows[rows.length - 1];
    if (!busy && last?.classList.contains('assistant')) {
      list.scrollTop += last.getBoundingClientRect().top - list.getBoundingClientRect().top - 8;
    } else {
      list.scrollTop = list.scrollHeight;
    }
  }, [messages, busy, activePage]);

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
    setMobileNavOpen(false);
    setSystemPanelOpen(false);
  }

  function changeProfile(value) {
    setProfileId(value);
    setMessages([INITIAL_MESSAGE]);
    setHistory(null);
    setError('');
  }

  return <>
    <a className="skip-link" href="#main-content">Bỏ qua điều hướng</a>
    <div className="app-shell">
    <Sidebar
      activePage={activePage}
      onChangePage={changePage}
      profile={selectedProfile}
      mobileOpen={mobileNavOpen}
      onToggleMobile={() => { setMobileNavOpen((open) => !open); setSystemPanelOpen(false); }}
    />
    {mobileNavOpen && <button className="drawer-scrim nav-scrim" aria-label="Đóng điều hướng" onClick={() => setMobileNavOpen(false)} />}

    <div className="main-area">
      <Topbar
        title={activePage === 'chat' ? 'Trò chuyện' : 'Lịch sử chỉ số'}
        profiles={profiles}
        profileId={profileId}
        onChangeProfile={changeProfile}
        systemPanelOpen={systemPanelOpen}
        onToggleSystem={() => { setSystemPanelOpen((open) => !open); setMobileNavOpen(false); }}
      />

      <div className="workspace">
        <main id="main-content" className={`content-column ${activePage === 'history' ? 'history-active' : ''}`}>
          <div className="demo-warning"><Info size={24} /><span><strong>Bản demo giáo dục.</strong> Không dùng để chẩn đoán, điều trị hoặc thay thế nhân viên y tế. Việc trích dẫn WHO/NIDDK không hàm ý các cơ quan này chứng thực DiaCare AI; tài liệu CDC không hàm ý CDC, ATSDR, HHS hay Chính phủ Hoa Kỳ chứng thực DiaCare AI.</span><span className="warning-tag">SYNTHETIC ONLY</span></div>
          <div className="safety-note"><CircleAlert size={18} /><span>Nhận diện cấp cứu là thử nghiệm và có thể bỏ sót. Nếu có dấu hiệu nặng, hãy gọi 115 ngay.</span></div>
          {error && <div className="inline-error" role="alert"><CircleAlert size={16} />{error}<button onClick={() => setError('')}>Đóng</button></div>}
          {activePage === 'chat' ? <ChatPage
            messages={messages} busy={busy} draft={draft} setDraft={setDraft} onSend={sendMessage}
            textareaRef={textareaRef} bottomRef={bottomRef}
          /> : <HistoryPage profile={selectedProfile} history={history} loading={historyLoading} />}
        </main>

        <InsightRail health={health} open={systemPanelOpen} onClose={() => setSystemPanelOpen(false)} />
      </div>
    </div>
    {systemPanelOpen && <button className="drawer-scrim system-scrim" aria-label="Đóng trạng thái hệ thống" onClick={() => setSystemPanelOpen(false)} />}
    </div>
  </>;
}
