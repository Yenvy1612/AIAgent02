import { useEffect, useMemo, useRef, useState } from 'react';
import { CircleAlert } from 'lucide-react';

const HEIGHT = 230;
const LEFT = 40;
const RIGHT = 10;

function makeChart(values, width) {
  if (!values.length) return { line: '', area: '', points: [], min: 0, max: 0 };
  const min = Math.floor((Math.min(...values) - 10) / 10) * 10;
  const max = Math.ceil((Math.max(...values) + 10) / 10) * 10;
  const span = width - LEFT - RIGHT;
  const points = values.map((value, i) => ({ x: LEFT + (values.length === 1 ? span / 2 : i * span / (values.length - 1)), y: 205 - ((value - min) / (max - min || 1)) * 180 }));
  const line = points.map((point, i) => `${i ? 'L' : 'M'}${point.x},${point.y}`).join(' ');
  const area = `${line} L${points[points.length - 1].x},205 L${points[0].x},205 Z`;
  return { line, area, points, min, max };
}

export default function GlucoseChart({ values }) {
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(700);
  // Draw at the real pixel width so points stay round and labels are not stretched.
  useEffect(() => {
    if (!wrapRef.current) return undefined;
    const observer = new ResizeObserver(([entry]) => { if (entry.contentRect.width) setWidth(entry.contentRect.width); });
    observer.observe(wrapRef.current);
    return () => observer.disconnect();
  }, [values.length > 0]);
  const chart = useMemo(() => makeChart(values, width), [values.join(','), width]);
  return <div className="chart-card">
    <div className="chart-heading"><div><strong>Diễn biến glucose</strong><span>Quy đổi biểu đồ sang mg/dL · 12 tuần gần nhất</span></div><div className="chart-legend"><i /> Glucose</div></div>
    {values.length ? <div className="chart-wrap" ref={wrapRef}><svg viewBox={`0 0 ${width} ${HEIGHT}`} role="img" aria-label="Biểu đồ glucose tổng hợp">
      {[0, 1, 2, 3].map((tick) => <g key={tick}><line x1={LEFT} x2={width - RIGHT} y1={25 + tick * 60} y2={25 + tick * 60} className="grid-line" /><text x="0" y={29 + tick * 60} className="axis-label">{Math.round(chart.max - tick * (chart.max - chart.min) / 3)}</text></g>)}
      <path d={chart.area} className="chart-area" /><path d={chart.line} className="chart-line" />
      {chart.points.map((point, i) => <circle key={i} cx={point.x} cy={point.y} r="3.5" className="chart-point" />)}
      <text x={LEFT} y="225" className="axis-label">12 tuần trước</text><text x={width - RIGHT} y="225" textAnchor="end" className="axis-label">Gần đây</text>
    </svg></div> : <div className="empty-chart">Chưa có phép đo để vẽ biểu đồ.</div>}
    <div className="chart-disclaimer"><CircleAlert size={16} /> Không diễn giải xu hướng hoặc dự báo từ dữ liệu mô phỏng.</div>
  </div>;
}
