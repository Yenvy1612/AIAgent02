export default function Mascot() {
  return <svg className="mascot" viewBox="0 0 120 120" aria-hidden="true">
    <defs>
      <linearGradient id="mascot-shell" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor="#bbdbff" /></linearGradient>
      <linearGradient id="mascot-body" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor="#cfe5ff" /></linearGradient>
    </defs>
    <circle cx="60" cy="62" r="54" fill="#bfddff" opacity=".6" />
    <rect x="53" y="10" width="14" height="10" rx="4" fill="#5da6f2" />
    <rect x="26" y="18" width="68" height="56" rx="24" fill="url(#mascot-shell)" stroke="#8fbff2" strokeWidth="1.5" />
    <rect x="16" y="38" width="10" height="20" rx="5" fill="#2f8bef" />
    <rect x="94" y="38" width="10" height="20" rx="5" fill="#2f8bef" />
    <rect x="35" y="30" width="50" height="34" rx="15" fill="#0e2c5c" />
    <path d="M43 48q5-7 10 0M67 48q5-7 10 0" fill="none" stroke="#6fe3ff" strokeWidth="4" strokeLinecap="round" />
    <path d="M54 55q6 4 12 0" fill="none" stroke="#6fe3ff" strokeWidth="2.5" strokeLinecap="round" />
    <path d="M36 112V90a14 14 0 0 1 14-12h20a14 14 0 0 1 14 12v22z" fill="url(#mascot-body)" stroke="#8fbff2" strokeWidth="1.5" />
    <rect x="56" y="86" width="8" height="20" rx="2.5" fill="#0f6cdb" />
    <rect x="50" y="92" width="20" height="8" rx="2.5" fill="#0f6cdb" />
  </svg>;
}
