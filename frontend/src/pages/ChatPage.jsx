import { ArrowUpRight, Bot, CircleAlert, CircleX, Globe, UserRound } from 'lucide-react';
import ChatBox from '../components/ChatBox.jsx';
import CitationCard from '../components/CitationCard.jsx';
import Mascot from '../components/Mascot.jsx';
import ToolTrace from '../components/ToolTrace.jsx';

// Icon, row class and label differ per status, so the state never depends on color alone.
const STATUS_STYLES = {
  EMERGENCY: { row: 'urgent', avatar: 'urgent-avatar', icon: CircleAlert, flag: 'CẢNH BÁO KHẨN' },
  WEB_UNVERIFIED: { row: 'web-unverified', avatar: 'web-avatar', icon: Globe, flag: 'NGUỒN WEB, CHƯA DUYỆT' },
  ERROR: { row: 'errored', avatar: 'error-avatar', icon: CircleX, flag: 'LỖI KẾT NỐI' },
};

function inlineParts(text, cited) {
  return text.split(/(\*\*[^*]+\*\*|\[C\d+\])/g).map((part, index) => {
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (cited && /^\[C\d+\]$/.test(part)) return <a key={index} href={`#citation-${part.slice(1, -1)}`}>{part}</a>;
    return part;
  });
}

function AnswerBody({ answer, cited }) {
  const blocks = [];
  for (const line of answer.split('\n')) {
    const bullet = line.match(/^\s*[-•]\s+(.*)$/);
    if (bullet) {
      const last = blocks[blocks.length - 1];
      if (last?.items) last.items.push(bullet[1]);
      else blocks.push({ items: [bullet[1]] });
    } else if (line.trim()) {
      blocks.push({ text: line });
    }
  }
  return blocks.map((block, index) => (block.items
    ? <ul key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}>{inlineParts(item, cited)}</li>)}</ul>
    : <p key={index}>{inlineParts(block.text, cited)}</p>));
}

function Message({ message }) {
  const user = message.role === 'user';
  const answer = message.answer || message.content || '';
  const style = STATUS_STYLES[message.status];
  const Icon = style?.icon || Bot;
  return <div className={`message-row ${user ? 'user' : 'assistant'} ${style?.row || ''}`}>
    {!user && <span className={`assistant-avatar ${style?.avatar || ''}`}><Icon size={22} /></span>}
    <div className="message-content">
      {user && <div className="message-meta">Bạn</div>}
      <div className="message-bubble">
        {style && <div className="message-flag">{style.flag}</div>}
        <AnswerBody answer={answer} cited={message.answer_mode === 'llm_cited'} />
        {message.status === 'EMERGENCY' && <a className="call-115" href="tel:115"><span>Gọi cấp cứu 115</span><ArrowUpRight size={18} /></a>}
      </div>
      {!user && <ResponseDetails message={message} />}
    </div>
    {user && <span className="user-avatar"><UserRound size={20} /></span>}
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

export default function ChatPage({ messages, busy, draft, setDraft, onSend, textareaRef, bottomRef }) {
  const latestAssistant = [...messages].reverse().find((message) => message.role === 'assistant');
  const composerNote = latestAssistant?.answer_mode === 'llm_cited'
    ? 'Phần giải thích do Claude viết từ nguồn đã duyệt.'
    : latestAssistant?.status === 'WEB_UNVERIFIED'
      ? 'Thông tin tra cứu web chưa được kiểm duyệt.'
      : 'Nội dung trích từ nguồn và quy tắc của hệ thống.';
  const conversationStarted = messages.length > 1;
  return <div className="chat-page">
    <div className={`page-intro ${conversationStarted ? 'compact' : ''}`}>
      <Mascot />
      <div className="page-intro-copy">
        <div className="eyebrow"><span className="eyebrow-line" /> TRỢ LÝ SỨC KHỎE ĐÁI THÁO ĐƯỜNG</div>
        <h1>Chào bạn, mình có thể <em>giúp gì?</em></h1>
        <p>Hỏi về chỉ số, hồ sơ mô phỏng hoặc kiến thức có nguồn. Mình ưu tiên nguồn đã duyệt và sẽ nói rõ khi chưa đủ dữ liệu.</p>
      </div>
    </div>

    <section className="chat-card" aria-label="Hội thoại">
      <div className="chat-card-top">
        <div className="conversation-label"><span className="assistant-avatar"><Bot size={24} /></span><div><strong>DiaCare Assistant</strong><small>Trợ lý sức khỏe đái tháo đường</small></div></div>
        <span className="session-badge"><span /> Phiên mới</span>
      </div>
      <div className="message-list">
        {messages.map((message, index) => <Message key={index} message={message} />)}
        {busy && <div className="typing-row" role="status"><span className="assistant-avatar small"><Bot size={18} /></span><span className="typing-dots"><i /><i /><i /></span><span>Đang kiểm tra quy tắc và nguồn…</span></div>}
        <div ref={bottomRef} />
      </div>
      <ChatBox draft={draft} setDraft={setDraft} onSend={onSend} textareaRef={textareaRef} busy={busy} showSuggestions={!conversationStarted} note={composerNote} />
    </section>
  </div>;
}
