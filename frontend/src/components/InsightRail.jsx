import { Activity, BookOpen, Bot, Check, Clock3, FileCheck2, History, ShieldCheck, Waves } from 'lucide-react';

const CAPABILITIES = [
  { icon: Activity, text: 'Tính BMI' },
  { icon: Waves, text: 'Diễn giải ngưỡng xét nghiệm' },
  { icon: History, text: 'Xem lịch sử mô phỏng' },
  { icon: FileCheck2, text: 'Tìm nguồn đã được duyệt' },
];

function StatusCard({ icon: Icon, title, detail, ready, readyLabel, pendingLabel }) {
  return <div className="status-card">
    <div className={`status-icon ${ready ? '' : 'pending'}`}><Icon size={22} /></div>
    <div className="status-main"><strong>{title}</strong><span>{detail}</span></div>
    <span className={`state-pill ${ready ? 'ready' : 'pending'}`}>{ready ? readyLabel : pendingLabel}</span>
  </div>;
}

export default function InsightRail({ health }) {
  const modelReady = Boolean(health?.model?.available);
  const documentCount = health?.knowledge_base?.approved_document_count;
  return <aside className="insight-rail" aria-label="Trạng thái hệ thống">
    <div className="rail-heading"><h2>Trạng thái hệ thống</h2><span className="rail-live"><i /> LOCAL</span></div>
    <div className="status-card">
      <div className="status-icon"><Bot size={22} /></div>
      <div className="status-main"><strong>Agent điều phối</strong><span>LangGraph · local</span></div>
      <span className="status-check" aria-label="Hoạt động"><Check size={15} strokeWidth={3} /></span>
    </div>
    <StatusCard icon={Activity} title="Mô hình nghiên cứu" detail={modelReady ? 'Nạp mô hình' : 'Chưa có artifact'} ready={modelReady} readyLabel="SẴN SÀNG" pendingLabel="CHỜ DỮ LIỆU" />
    <StatusCard icon={BookOpen} title="Knowledge Base" detail={`${documentCount ?? '—'} nguồn đã duyệt`} ready={Boolean(documentCount)} readyLabel="SẴN SÀNG" pendingLabel="ĐANG RÀ SOÁT" />
    <div className="rail-divider" />
    <div className="rail-heading"><h2>Trợ lý có thể</h2></div>
    <div className="capability-list">
      {CAPABILITIES.map(({ icon: Icon, text }) => <div className="capability" key={text}><span className="capability-icon"><Icon size={20} /></span><span>{text}</span><Check size={18} strokeWidth={2.6} className="capability-check" /></div>)}
    </div>
    <div className="model-notice"><ShieldCheck size={26} strokeWidth={1.9} /><div><strong>Không tạo số liệu giả</strong><p>Model score và citation chỉ xuất hiện khi có artifact hoặc nguồn đã duyệt.</p></div></div>
    <div className="rail-footer"><Clock3 size={18} /> Phiên demo không lưu hội thoại</div>
  </aside>;
}
