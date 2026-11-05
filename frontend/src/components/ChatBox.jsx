import { Activity, ArrowUpRight, History, Send, Waves } from 'lucide-react';

const PROMPTS = [
  { icon: <Waves size={18} />, text: 'Đường huyết của tôi là 7' },
  { icon: <Activity size={18} />, text: 'Tính BMI của hồ sơ này' },
  { icon: <History size={18} />, text: 'Xem lịch sử đo gần đây' },
];

export default function ChatBox({ draft, setDraft, onSend, textareaRef, busy, showSuggestions, note }) {
  return <>
    {showSuggestions && <div className="suggestion-area"><div className="suggestion-label">Thử hỏi</div><div className="suggestions">{PROMPTS.map((prompt) => <button key={prompt.text} onClick={() => onSend(prompt.text)}>{prompt.icon}{prompt.text}<ArrowUpRight size={16} className="prompt-arrow" /></button>)}</div></div>}
    <div className="composer-wrap">
      <form className="composer" onSubmit={(event) => { event.preventDefault(); onSend(); }}>
        <textarea ref={textareaRef} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSend(); } }} placeholder="Nhập câu hỏi của bạn…" rows={1} maxLength={4000} aria-label="Tin nhắn" />
        <button disabled={!draft.trim() || busy}><Send size={18} /><span>Gửi</span></button>
      </form>
      <div className="composer-note">Không nhập thông tin sức khỏe hoặc định danh thật · {note}</div>
    </div>
  </>;
}
