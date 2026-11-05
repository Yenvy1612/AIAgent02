import { Activity, Bot, Check, ChevronDown } from 'lucide-react';

const LABELS = {
  safety_gate: 'Safety Gate', agent_bypass: 'Agent bypass', medication_boundary: 'Ranh giới thuốc',
  unit_safety: 'Kiểm tra đơn vị', intent_router: 'Intent Router', fusion: 'Fusion',
  output_validator: 'Output Validator', llm_composer: 'LLM Composer', guidance: 'Hướng dẫn nhập liệu', api_request: 'Yêu cầu API',
};

function traceLabel(step) {
  return LABELS[step] || step.replace(/^tool:/, 'Tool · ');
}

function TraceList({ rows, labelKey, statusKey, labels = {} }) {
  return <div className="trace-body">{rows.map((row, i) => <div className="trace-item" key={`${row[labelKey]}-${i}`}>
    <span className="trace-node"><Check size={10} /></span>
    <span className="trace-tool">{labels[row[labelKey]] || row[labelKey]}</span>
    <span className={`trace-status ${/OK|NORMAL|VALIDATED|SENT/.test(row[statusKey]) ? 'success' : 'muted'}`}>{row[statusKey]}</span>
  </div>)}</div>;
}

export default function ToolTrace({ trace = [], calls = [] }) {
  if (!trace.length && !calls.length) return null;
  const namedTrace = trace.map((step) => ({ ...step, label: traceLabel(step.step) }));
  return <div className="trace-panels">
    {trace.length > 0 && <details className="tool-trace"><summary><span className="trace-icon"><Activity size={13} /></span>Trace xử lý <span className="trace-count">{trace.length} bước</span><ChevronDown size={13} className="details-chevron" /></summary><TraceList rows={namedTrace} labelKey="label" statusKey="status" /></details>}
    {calls.length > 0 && <details className="tool-trace"><summary><span className="trace-icon"><Bot size={13} /></span>Tools được gọi <span className="trace-count">{calls.length} / tối đa 5</span><ChevronDown size={13} className="details-chevron" /></summary><TraceList rows={calls} labelKey="tool" statusKey="status" /></details>}
  </div>;
}
