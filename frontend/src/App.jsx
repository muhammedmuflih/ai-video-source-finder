import { useEffect, useState } from "react";
import { Search, ShieldCheck, Video, Link2, LoaderCircle, Sparkles } from "lucide-react";
import VideoUpload from "./components/VideoUpload";
import SearchResults from "./components/SearchResults";
import { initializeSession, signOut, submitVideo } from "./services/api";

export default function App() {
  const [file, setFile] = useState(null);
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    initializeSession()
      .then(setUser)
      .catch(() => { window.location.href = "/login.html#signin"; })
      .finally(() => setAuthLoading(false));
  }, []);

  async function handleLogout() {
    try {
      await signOut();
      window.location.href = "/login.html#signin";
    } catch {
      setError("Could not end your session. Please try again.");
    }
  }

  if (authLoading || !user) return <div className="auth-loading">Loading your account…</div>;

  async function handleSearch(e) {
    e.preventDefault();
    setError("");
    setJob(null);
    if (!file) {
      setError("Please upload a video first.");
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      setError("The video must be 100 MB or smaller.");
      return;
    }
    setLoading(true);
    try {
      const data = await submitVideo(file);
      setJob(data);
    } catch (err) {
      if (err.response?.status === 403) {
        window.location.href = "/login.html?auth_error=session_expired#signin";
        return;
      }
      setError(err.response?.data?.error || err.response?.data?.message || "Could not process the video. Make sure the Django server is running.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand-mark"><Video size={22} /></span>
          <span>Source<span className="brand-accent">Finder</span></span>
        </a>
        <div className="account-actions"><span className="topbar-label"><ShieldCheck size={16} /> {user.email}</span><button className="button secondary" type="button" onClick={handleLogout}>Log out</button></div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-pill"><Sparkles size={15} /> AI-ASSISTED VIDEO DISCOVERY</div>
          <h1>Find where a video<br /><span>may have appeared.</span></h1>
          <p>Upload a video, analyze its frames, and search for possible source posts using available search integrations.</p>
        </section>

        <section className="workspace">
          <form className="search-panel" onSubmit={handleSearch}>
            <div className="panel-heading">
              <div className="panel-icon"><Video size={22} /></div>
              <div>
                <h2>Upload a video</h2>
                <p>Start with the video your friend shared.</p>
              </div>
            </div>
            <VideoUpload file={file} setFile={setFile} />

            {error && <div className="error-message">{error}</div>}
            <button className="button primary search-button" type="submit" disabled={loading}>
              {loading ? <><LoaderCircle className="spin" size={18} /> Analyzing video...</> : <><Search size={18} /> Analyze & search</>}
            </button>
            <div className="privacy-note"><ShieldCheck size={16} /> In this local demo, uploaded files are stored on your computer in the Django media folder.</div>
          </form>

          <aside className="how-panel">
            <p className="eyebrow">HOW IT WORKS</p>
            <div className="how-step"><span>01</span><div><strong>Analyze frames</strong><p>Extract representative frames and calculate perceptual hashes.</p></div></div>
            <div className="how-step"><span>02</span><div><strong>Search candidates</strong><p>Use an optional YouTube API key and your descriptive query.</p></div></div>
            <div className="how-step"><span>03</span><div><strong>Verify source links</strong><p>Review each candidate. A result is not proof of an exact match.</p></div></div>
            <div className="aside-note"><Link2 size={17} /><span>Direct links are shown when a search result provides a public post URL.</span></div>
          </aside>
        </section>

        {job && <SearchResults job={job} />}

        <section className="platform-note">
          <h3>Platform coverage</h3>
          <p><strong>Currently integrated:</strong> YouTube text search, when an API key is configured.</p>
          <p><strong>Not automatically searched:</strong> all Instagram, Facebook, TikTok, or X posts. These require separate permitted integrations or indexed public web results; no universal free API provides complete reverse-video search across every platform.</p>
        </section>
      </main>

      <footer>AI Video Source Finder · React + Django REST Framework</footer>
    </div>
  );
}
