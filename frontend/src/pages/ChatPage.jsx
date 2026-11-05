import { ArrowUpRight, Bot, CircleAlert, CircleX, Globe, UserRound } from 'lucide-react';
import ChatBox from '../components/ChatBox.jsx';
import CitationCard from '../components/CitationCard.jsx';
import ToolTrace from '../components/ToolTrace.jsx';

// Icon, row class and label differ per status, so the state never depends on color alone.
const STATUS_STYLES = {
  EMERGENCY: { row: 'urgent', avatar: 'urgent-avatar', icon: CircleAlert, flag: 'CẢNH BÁO KHẨN' },
  WEB_UNVERIFIED: { row: 'web-unverified', avatar: 'web-avatar', icon: Globe, flag: 'NGUỒN WEB, CHƯA DUYỆT' },
  ERROR: { row: 'errored', avatar: 'error-avatar', icon: CircleX, flag: 'LỖI KẾT NỐI' },
};

function inlineParts(text, cited) {
  return text.split(/(\*\*[^*]+\*\*|\[C\d+\]|\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g).map((part, index) => {
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (cited && /^\[C\d+\]$/.test(part)) return <a key={index} href={`#citation-${part.slice(1, -1)}`}>{part}</a>;
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/);
    if (link) return <a key={index} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>;
    return part;
  });
}

function tableCells(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
}

function isTableDivider(line) {
  const cells = tableCells(line);
  return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function AnswerBody({ answer, cited }) {
  const blocks = [];
  const lines = answer.replace(/\r/g, '').split('\n');
  let paragraph = [];
  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: 'paragraph', text: paragraph.join(' ') });
    paragraph = [];
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    const listItem = line.match(/^([-*•]|\d+[.)])\s+(.*)$/);

    if (!line) {
      flushParagraph();
      continue;
    }
    if (heading) {
      flushParagraph();
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] });
      continue;
    }
    if (line.includes('|') && index + 1 < lines.length && isTableDivider(lines[index + 1])) {
      flushParagraph();
      const headers = tableCells(line);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        rows.push(tableCells(lines[index]));
        index += 1;
      }
      index -= 1;
      blocks.push({ type: 'table', headers, rows });
      continue;
    }
    if (listItem) {
      flushParagraph();
      const ordered = /^\d/.test(listItem[1]);
      const items = [listItem[2]];
      while (index + 1 < lines.length) {
        const nextItem = lines[index + 1].trim().match(/^([-*•]|\d+[.)])\s+(.*)$/);
        if (!nextItem || /^\d/.test(nextItem[1]) !== ordered) break;
        items.push(nextItem[2]);
        index += 1;
      }
      blocks.push({ type: ordered ? 'ordered-list' : 'list', items });
      continue;
    }
    paragraph.push(line);
  }
  flushParagraph();

  return blocks.map((block, index) => {
    if (block.type === 'heading') {
      const Heading = `h${Math.min(block.level + 1, 5)}`;
      return <Heading key={index}>{inlineParts(block.text, cited)}</Heading>;
    }
    if (block.type === 'list' || block.type === 'ordered-list') {
      const List = block.type === 'ordered-list' ? 'ol' : 'ul';
      return <List key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}>{inlineParts(item, cited)}</li>)}</List>;
    }
    if (block.type === 'table') {
      return <div className="answer-table-wrap" key={index}><table className="answer-table"><thead><tr>{block.headers.map((cell, cellIndex) => <th scope="col" key={cellIndex}>{inlineParts(cell, cited)}</th>)}</tr></thead><tbody>{block.rows.map((row, rowIndex) => <tr key={rowIndex}>{block.headers.map((_, cellIndex) => <td key={cellIndex}>{inlineParts(row[cellIndex] || '', cited)}</td>)}</tr>)}</tbody></table></div>;
    }
    return <p key={index}>{inlineParts(block.text, cited)}</p>;
  });
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
    <section className="chat-card" aria-label="Hội thoại">
      <div className="chat-card-top">
        <div className="conversation-label"><span className="assistant-avatar"><Bot size={19} /></span><div><strong>DiaCare Assistant</strong><small>Trợ lý sức khỏe đái tháo đường</small></div></div>
        <span className="session-badge"><span /> {conversationStarted ? 'Đang trò chuyện' : 'Phiên mới'}</span>
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
