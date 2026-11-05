import { ArrowUpRight, BookOpen, FileCheck2, Globe } from 'lucide-react';

export default function CitationCard({ citations = [], referenceOnly = [], webSources = [] }) {
  return <>
    {webSources.length > 0 && <div className="web-sources"><div className="web-sources-title"><Globe size={16} />Nguồn web — chưa được duyệt</div>{webSources.filter((source) => source.url?.startsWith('https://')).map((source) => <a href={source.url} target="_blank" rel="noreferrer" className="web-source" key={source.url}>
      <span><strong>{source.title}</strong><small>{source.cited_text}</small></span><ArrowUpRight size={16} />
    </a>)}</div>}
    {citations.length > 0 && <div className="citation-heading">Nguồn tham khảo ({citations.length})</div>}
    {citations.length > 0 && <div className="citation-list">{citations.map((citation) => <a id={citation.display_label ? `citation-${citation.display_label}` : undefined} href={citation.source_url?.startsWith('https://') ? citation.source_url : '#'} target="_blank" rel="noreferrer" className="citation" key={citation.chunk_id}>
      <BookOpen size={20} strokeWidth={1.8} /><span><strong>{citation.display_label ? `[${citation.display_label}] ` : ''}{citation.document_id} · {citation.title}</strong><small>{citation.page ? `Trang ${citation.page} · ` : ''}{citation.chunk_id}</small></span><ArrowUpRight size={16} />
    </a>)}</div>}
    {referenceOnly.length > 0 && <details className="reference-only"><summary><FileCheck2 size={18} />Tham chiếu quy tắc <span>chưa được ingest</span></summary>{referenceOnly.map((ref) => <a key={ref.reference_id} href={ref.source_url || '#'} target="_blank" rel="noreferrer">{ref.title}<ArrowUpRight size={16} /></a>)}</details>}
  </>;
}
