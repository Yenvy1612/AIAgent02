import { useMemo } from 'react';
import { CircleAlert } from 'lucide-react';

function makeChart(values) {
  if (!values.length) return { line: '', area: '', points: [], min: 0, max: 0 };
  const min = Math.floor((Math.min(...values) - 10) / 10) * 10;
  const max = Math.ceil((Math.max(...values) + 10) / 10) * 10;
  const points = values.map((value, i) => ({ x: 38 + (values.length === 1 ? 326 : i * 652 / (values.length - 1)), y: 205 - ((value - min) / (max - min || 1)) * 180 }));
  const line = points.map((point, i) => `${i ? 'L' : 'M'}${point.x},${point.y}`).join(' ');
  const area = `${line} L${points[points.length - 1].x},205 L${points[0].x},205 Z`;
  return { line, area, points, min, max };
}

export default function GlucoseChart({ values }) {
  const chart = useMemo(() => makeChart(values), [values.join(',')]);
  return <div className="chart-card">
    <div className="chart-heading"><div><strong>Diễn biến glucose</strong><span>Quy đổi biểu đồ sang mg/dL · 12 tuần gần nhất</span></div><div className="chart-legend"><i /> Glucose</div></div>
    {values.length ? <div className="chart-wrap"><svg viewBox="0 0 700 230" role="img" aria-label="Biểu đồ glucose tổng hợp" preserveAspectRatio="none">
      {[0, 1, 2, 3].map((tick) => <g key={tick}><line x1="38" x2="690" y1={25 + tick * 56} y2={25 + tick * 56} className="grid-line" /><text x="2" y={29 + tick * 56} className="axis-label">{Math.round(chart.max - tick * (chart.max - chart.min) / 3)}</text></g>)}
      <path d={chart.area} className="chart-area" /><path d={chart.line} className="chart-line" />
      {chart.points.map((point, i) => <circle key={i} cx={point.x} cy={point.y} r="3.3" className="chart-point" />)}
      <text x="38" y="225" className="axis-label">12 tuần trước</text><text x="642" y="225" className="axis-label">Gần đây</text>
    </svg></div> : <div className="empty-chart">Chưa có phép đo để vẽ biểu đồ.</div>}
    <div className="chart-disclaimer"><CircleAlert size={14} /> Không diễn giải xu hướng hoặc dự báo từ dữ liệu mô phỏng.</div>
  </div>;
}
