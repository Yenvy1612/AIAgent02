import { ArrowUpRight, Bot, Sparkles, UserRound } from 'lucide-react';
import ChatBox from '../components/ChatBox.jsx';
import CitationCard from '../components/CitationCard.jsx';
import ToolTrace from '../components/ToolTrace.jsx';

function Message({ message }) {
  const user = message.role === 'user';
  const answer = message.answer || message.content || '';
  const emergency = message.status === 'EMERGENCY';
  const unverified = message.status === 'WEB_UNVERIFIED';
  return <div className={`message-row ${user ? 'user' : 'assistant'} ${emergency ? 'urgent' : ''} ${unverified ? 'web-unverified' : ''}`}>
    {!user && <span className={`assistant-avatar ${emergency ? 'urgent-avatar' : ''}`}><Bot size={16} /></span>}
    <div className="message-content">
      <div className="message-meta"><strong>{user ? 'Bạn' : 'DiaCare'}</strong><span>{user ? '' : emergency ? 'CẢNH BÁO KHẨN' : unverified ? 'NGUỒN WEB, CHƯA DUYỆT' : 'TRỢ LÝ GIÁO DỤC'}</span></div>
      <div className="message-bubble">{answer.split('\n').map((line, i) => <p key={i}>{line}</p>)}
        {emergency && <a className="call-115" href="tel:115"><span>Gọi cấp cứu 115</span><ArrowUpRight size={15} /></a>}
      </div>
      {!user && <ResponseDetails message={message} />}
    </div>
    {user && <span className="user-avatar"><UserRound size={15} /></span>}
  </div>;
}

function ResponseDetails({ message }) {
  const trace = message.trace || [];
  const calls = message.tool_calls || [];
  const citations = message.citations || [];
  const referenceOnly = message.reference_only || [];
  const webSources = message.web_sources || [];
  if (!trace.length && !calls.length && !citations.length && !referenceOnly.length && !webSources.length) return null;
  return <div className="response-details">
    <ToolTrace trace={trace} calls={calls} />
    <CitationCard citations={citations} referenceOnly={referenceOnly} webSources={webSources} />
  </div>;
}

export default function ChatPage({ messages, busy, draft, setDraft, onSend, textareaRef, bottomRef, profile }) {
  return <div className="chat-page">
    <div className="page-intro">
      <div className="eyebrow"><span className="eyebrow-line" /> TRỢ LÝ SỨC KHỎE GIÁO DỤC</div>
      <h1>Chào bạn, mình có thể <em>giúp gì?</em></h1>
      <p>Hỏi về chỉ số, hồ sơ mô phỏng hoặc kiến thức có nguồn. Mình sẽ nói rõ khi chưa đủ dữ liệu.</p>
    </div>

    <div className="chat-card">
      <div className="chat-card-top">
        <div className="conversation-label"><span className="assistant-avatar"><Bot size={17} /></span><div><strong>DiaCare Assistant</strong><small>Luồng hỗ trợ giáo dục</small></div></div>
        <span className="session-badge"><span /> PHIÊN MỚI</span>
      </div>
      <div className="message-list">
        {messages.map((message, index) => <Message key={index} message={message} />)}
        {busy && <div className="typing-row"><span className="assistant-avatar small"><Bot size={14} /></span><span className="typing-dots"><i /><i /><i /></span><span>Đang kiểm tra quy tắc và nguồn…</span></div>}
        <div ref={bottomRef} />
      </div>
      <ChatBox draft={draft} setDraft={setDraft} onSend={onSend} textareaRef={textareaRef} busy={busy} showSuggestions={messages.length === 1} />
    </div>
    <div className="chat-footnote"><Sparkles size={14} /> {profile?.display_name || 'Hồ sơ tổng hợp'} · Nội dung do agent cục bộ điều phối, không gọi LLM bên ngoài.</div>
  </div>;
}
