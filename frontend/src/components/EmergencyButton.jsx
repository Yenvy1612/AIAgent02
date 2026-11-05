import { useState } from 'react';
import { ArrowUpRight, CircleAlert } from 'lucide-react';

export default function EmergencyButton() {
  const [open, setOpen] = useState(false);
  return <>
    <button className="emergency-quick" onClick={() => setOpen(true)}><span className="emergency-pulse" />Tôi đang cấp cứu</button>
    {open && <div className="dialog-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section className="emergency-dialog" role="dialog" aria-modal="true" aria-labelledby="emergency-title">
        <button className="dialog-close" onClick={() => setOpen(false)} aria-label="Đóng">×</button>
        <div className="dialog-alert-icon"><CircleAlert size={25} /></div>
        <div className="eyebrow"><span className="eyebrow-line" /> HỖ TRỢ KHẨN CẤP</div>
        <h2 id="emergency-title">Bạn có thể cần <em>trợ giúp ngay.</em></h2>
        <p>Nếu bạn hoặc người bên cạnh đang bất tỉnh, co giật, lú lẫn hoặc khó thở, hãy gọi cấp cứu 115 ngay. Nhờ người ở gần hỗ trợ và không tự lái xe.</p>
        <a className="dialog-call" href="tel:115"><span>Gọi 115</span><ArrowUpRight size={17} /></a>
        <button className="dialog-secondary" onClick={() => setOpen(false)}>Quay lại ứng dụng</button>
        <small>DiaCare AI không thay thế dịch vụ cấp cứu.</small>
      </section>
    </div>}
  </>;
}
