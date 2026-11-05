import { Activity, BookOpen, Bot, Check, Clock3, FileCheck2, History, ShieldCheck, Waves, X } from 'lucide-react';

const CAPABILITIES = [
  { icon: Activity, text: 'Tính BMI' },
  { icon: Waves, text: 'Diễn giải ngưỡng xét nghiệm' },
  { icon: History, text: 'Xem lịch sử mô phỏng' },
  { icon: FileCheck2, text: 'Tìm nguồn đã được duyệt' },
  { icon: ShieldCheck, text: 'Bảng hỏi nguy cơ · tham khảo' },
];

function StatusCard({ icon: Icon, title, detail, ready, readyLabel, pendingLabel }) {
  return <div className="status-card">
    <div className={`status-icon ${ready ? '' : 'pending'}`}><Icon size={22} /></div>
    <div className="status-main"><strong>{title}</strong><span>{detail}</span></div>
    <span className={`state-pill ${ready ? 'ready' : 'pending'}`}>{ready ? readyLabel : pendingLabel}</span>
  </div>;
}

export default function InsightRail({ health, open, onClose }) {
  const healthLoaded = Boolean(health);
  const modelReady = Boolean(health?.model?.available);
  const documentCount = health?.knowledge_base?.approved_document_count;
  return <aside id="system-rail" className={`insight-rail ${open ? 'is-open' : ''}`} aria-label="Trạng thái hệ thống">
    <div className="rail-heading"><h2>Trạng thái hệ thống</h2><span className={`rail-live ${healthLoaded ? '' : 'is-loading'}`}><i />{healthLoaded ? 'LOCAL' : 'Đang kiểm tra'}</span><button className="rail-close" type="button" onClick={onClose} aria-label="Đóng trạng thái hệ thống"><X size={17} /></button></div>
    <div className="status-card">
      <div className="status-icon"><Bot size={22} /></div>
      <div className="status-main"><strong>Agent điều phối</strong><span>LangGraph · local</span></div>
      <span className={`status-check ${healthLoaded ? '' : 'pending'}`} aria-label={healthLoaded ? 'Hoạt động' : 'Đang kiểm tra'}>{healthLoaded ? <Check size={15} strokeWidth={3} /> : <Clock3 size={15} />}</span>
    </div>
    <StatusCard icon={Activity} title="Mô hình nghiên cứu" detail={!healthLoaded ? 'Đang kiểm tra' : modelReady ? 'Nạp mô hình' : 'Chưa có artifact'} ready={modelReady} readyLabel="Sẵn sàng" pendingLabel={healthLoaded ? 'Chưa nạp' : 'Đang tải'} />
    <StatusCard icon={BookOpen} title="Knowledge Base" detail={healthLoaded ? `${documentCount ?? '—'} nguồn đã duyệt` : 'Đang kiểm tra'} ready={Boolean(documentCount)} readyLabel="Sẵn sàng" pendingLabel={healthLoaded ? 'Chưa có nguồn' : 'Đang tải'} />
    <div className="rail-divider" />
    <div className="rail-heading"><h2>Công cụ hỗ trợ</h2></div>
    <div className="capability-list">
      {CAPABILITIES.map(({ icon: Icon, text }) => <div className="capability" key={text}><span className="capability-icon"><Icon size={18} /></span><span>{text}</span></div>)}
    </div>
    <div className="model-notice"><ShieldCheck size={26} strokeWidth={1.9} /><div><strong>Không tạo số liệu giả</strong><p>Model score và citation chỉ xuất hiện khi có artifact hoặc nguồn đã duyệt.</p></div></div>
    <div className="rail-footer"><Clock3 size={18} /> Phiên demo không lưu hội thoại</div>
  </aside>;
}
