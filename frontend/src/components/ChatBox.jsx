import { Activity, ArrowUpRight, History, Send, Shield, Waves } from 'lucide-react';

const PROMPTS = [
  { icon: <Waves size={15} />, text: 'Đường huyết của tôi là 7' },
  { icon: <Activity size={15} />, text: 'Tính BMI của hồ sơ này' },
  { icon: <History size={15} />, text: 'Xem lịch sử đo gần đây' },
];

export default function ChatBox({ draft, setDraft, onSend, textareaRef, busy, showSuggestions }) {
  return <>
    {showSuggestions && <div className="suggestion-area"><div className="suggestion-label">THỬ HỎI</div><div className="suggestions">{PROMPTS.map((prompt) => <button key={prompt.text} onClick={() => onSend(prompt.text)}>{prompt.icon}{prompt.text}<ArrowUpRight size={13} className="prompt-arrow" /></button>)}</div></div>}
    <form className="composer" onSubmit={(event) => { event.preventDefault(); onSend(); }}>
      <textarea ref={textareaRef} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSend(); } }} placeholder="Nhập câu hỏi của bạn…" rows={2} maxLength={4000} aria-label="Tin nhắn" />
      <div className="composer-footer"><span><Shield size={13} /> Không nhập thông tin sức khỏe thật</span><button disabled={!draft.trim() || busy} aria-label="Gửi tin nhắn"><Send size={16} /><span>Gửi</span></button></div>
    </form>
  </>;
}
