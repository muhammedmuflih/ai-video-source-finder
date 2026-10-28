import { ExternalLink, Youtube, Search, CheckCircle2, AlertTriangle } from "lucide-react";

export default function SearchResults({ job }) {
  if (!job) return null;
  const results = job.results || [];

  return (
    <section className="results-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SEARCH REPORT</p>
          <h2>Results</h2>
        </div>
        <span className="result-count">{results.length} candidate{results.length === 1 ? "" : "s"}</span>
      </div>

      <div className="summary-grid">
        <div className="summary-card">
          <span>Frames analyzed</span>
          <strong>{job.extracted_frames}</strong>
        </div>
        <div className="summary-card">
          <span>Search status</span>
          <strong className="status-text">{job.status}</strong>
        </div>
      </div>

      {job.message && <div className="notice"><AlertTriangle size={18} /><span>{job.message}</span></div>}

      {results.length === 0 ? (
        <div className="empty-results">
          <Search size={28} />
          <strong>No candidates returned</strong>
          <p>Try a more descriptive query, and check whether a YouTube API key is configured.</p>
        </div>
      ) : (
        <div className="result-list">
          {results.map((result, index) => (
            <article className="result-card" key={result.url || index}>
              <div className="thumbnail-wrap">
                {result.thumbnail ? <img src={result.thumbnail} alt="" /> : <div className="thumbnail-placeholder"><Youtube /></div>}
              </div>
              <div className="result-info">
                <div className="result-platform"><Youtube size={15} /> YouTube · Text search candidate</div>
                <h3>{result.title}</h3>
                <p>{result.channel}{result.published_at ? ` · ${new Date(result.published_at).toLocaleDateString()}` : ""}</p>
                <small>{result.note}</small>
                <a href={result.url} target="_blank" rel="noreferrer">
                  Open source post <ExternalLink size={15} />
                </a>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="accuracy-note">
        <CheckCircle2 size={17} />
        <span>These are search candidates, not confirmed identical videos. Open each link and verify the content manually.</span>
      </div>
    </section>
  );
}
