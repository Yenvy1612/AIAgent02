import { Activity, CircleAlert, History, LoaderCircle, Sparkles, UserRound, Waves } from 'lucide-react';
import GlucoseChart from '../components/GlucoseChart.jsx';

function MetricCard({ label, value, suffix, icon }) {
  return <div className="metric-card"><div className="metric-icon">{icon}</div><span className="metric-label">{label}</span><strong>{value}</strong><small>{suffix}</small></div>;
}

function formatDate(value) {
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function measurementLabel(value) {
  return ({ fasting: 'Lúc đói', random: 'Ngẫu nhiên', ogtt_2h: 'OGTT · 2 giờ' })[value] || 'Chưa rõ';
}

export default function HistoryPage({ profile, history, loading }) {
  const readings = history?.readings || [];
  const values = readings.map((reading) => reading.glucose_mg_dl);
  const latest = readings[readings.length - 1];
  const average = values.length ? Math.round(values.reduce((sum, item) => sum + item, 0) / values.length) : null;
  return <div className="history-page">
    <div className="page-intro history-intro">
      <div className="eyebrow"><span className="eyebrow-line" /> HỒ SƠ MÔ PHỎNG</div>
      <h1>Lịch sử <em>chỉ số</em></h1>
      <p>Các phép đo minh họa được tạo tổng hợp để trình diễn luồng dữ liệu.</p>
    </div>
    <div className="history-profile-card">
      <div className="history-profile-icon"><UserRound size={20} /></div>
      <div className="history-profile-copy"><span>ĐANG XEM</span><strong>{profile?.display_name || 'Chọn hồ sơ mô phỏng'}</strong><small>{profile ? `${profile.id} · ${profile.age} tuổi · ${profile.gender}` : ''}</small></div>
      <span className="synthetic-chip"><span /> SYNTHETIC DATA</span>
    </div>
    {loading ? <div className="loading-state"><LoaderCircle className="spin" /> Đang tải lịch sử…</div> : !history ? <div className="empty-state"><History size={25} /><strong>Chưa có dữ liệu</strong><span>Chọn một hồ sơ mô phỏng để xem lịch sử.</span></div> : <>
      <div className="metric-grid">
        <MetricCard label="LẦN ĐO" value={readings.length} suffix="phép đo" icon={<Waves size={17} />} />
        <MetricCard label="GIÁ TRỊ GẦN NHẤT" value={latest ? `${latest.original_value}` : '—'} suffix={latest?.original_unit || ''} icon={<Activity size={17} />} />
        <MetricCard label="TRUNG BÌNH THAM KHẢO" value={average ?? '—'} suffix="mg/dL" icon={<Sparkles size={17} />} />
      </div>
      <GlucoseChart values={values} />
      <div className="table-card">
        <div className="table-heading"><div><strong>Các lần đo</strong><span>{readings.length} bản ghi · nguồn synthetic</span></div><span className="table-unit">ĐƠN VỊ GỐC ĐƯỢC GIỮ</span></div>
        <div className="table-scroll"><table><thead><tr><th>THỜI GIAN</th><th>GLUCOSE GỐC</th><th>KIỂU ĐO</th><th>QUY ĐỔI</th><th>NGUỒN</th></tr></thead><tbody>{[...readings].reverse().map((reading, i) => <tr key={`${reading.measured_at}-${i}`}><td>{formatDate(reading.measured_at)}</td><td><strong>{reading.original_value}</strong> <span>{reading.original_unit}</span></td><td><span className="measurement-tag">{measurementLabel(reading.measurement_type)}</span></td><td>{Math.round(reading.glucose_mg_dl)} mg/dL</td><td><span className="source-label"><i /> {reading.source_type}</span></td></tr>)}</tbody></table></div>
      </div>
    </>}
  </div>;
}
