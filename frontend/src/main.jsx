import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowRight, ArrowUpRight, BookOpen, Check, CheckCheck, ChevronRight, CircleCheck, Clock3, Download, Eye, EyeOff, FileCheck2, FileText, FolderClock, LayoutDashboard, SlidersHorizontal, LoaderCircle, LockKeyhole, LogOut, Menu, Plus, ScanText, ShieldCheck, Sparkles, UploadCloud, X, AlertCircle, Type, Ruler, ListChecks } from 'lucide-react';
import { api, sendJSON } from './api';
import { ProfilePicker, ProfileManager, ReviewWorkspace } from './v2';
import './styles.css';

const go = (route) => { window.location.hash = route; };
const date = (value) => new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
const label = (name) => name.replace(/ Errors$/, '');
const finding = (line) => line.startsWith('❌') || line.includes('Error:');
const clean = (line) => line.replace(/^[❌✔✅•]\s*/, '');
const categories = [
  ['Typography', 'Arial, 12 pt for body text and headings.', Type],
  ['Captions', 'Arial, 11 pt for numbered tables and figures.', FileText],
  ['Spacing & margins', '1.5 line spacing and one-inch margins.', Ruler],
  ['Headers & footers', 'Arial, 9 pt. Header page numbers aligned right.', LayoutDashboard],
  ['Heading structure', 'Review Heading 1 and Heading 2 styles.', ListChecks],
  ['APA references', 'Reference pattern screening with manual review.', BookOpen],
];

function Brand({ light = false }) {
  return <a className={`brand ${light ? 'light' : ''}`} href="#/" aria-label="ADF Check home"><span className="brand-icon"><FileCheck2 size={23}/></span><span>ADF<span className="brand-light">Check</span><small>ACADEMIC WORKSPACE</small></span></a>;
}
function ErrorMessage({ children }) { return children ? <div className="error" role="alert"><AlertCircle size={18}/><span>{children}</span></div> : null; }
function Button({ children, className = '', ...props }) { return <button className={`button ${className}`} {...props}>{children}</button>; }

export function App() {
  const [route, setRoute] = useState(window.location.hash.slice(1) || '/');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionMessage, setSessionMessage] = useState('');
  useEffect(() => {
    const change = () => { setRoute(window.location.hash.slice(1) || '/'); window.scrollTo(0, 0); };
    const expired = () => { setUser(null); setSessionMessage('Your session expired. Sign in again to continue.'); go('/login'); };
    window.addEventListener('hashchange', change);
    window.addEventListener('session-expired', expired);
    api('/auth/me').then(setUser).catch((e) => { if (e.status !== 401) setSessionMessage(e.message); }).finally(() => setLoading(false));
    return () => { window.removeEventListener('hashchange', change); window.removeEventListener('session-expired', expired); };
  }, []);
  if (loading) return <div className="startup"><Brand/><LoaderCircle className="spin"/><p>Opening your workspace…</p></div>;
  const onAuth = (account) => { setUser(account); setSessionMessage(''); go('/workspace'); };
  if (!user) {
    if (route === '/login' || route === '/signup' || route.startsWith('/workspace')) return <Auth signup={route === '/signup'} onAuth={onAuth} notice={sessionMessage}/>;
    return <Landing/>;
  }
  return <Workspace user={user} route={route} onLogout={() => { setUser(null); go('/'); }}/>;
}

function Landing() {
  return <div className="landing">
    <header className="landing-nav"><Brand/><nav><a href="#how-it-works" onClick={(e) => { e.preventDefault(); document.getElementById('how-it-works').scrollIntoView({ behavior: 'smooth' }); }}>How it works</a><a href="#/login">Sign in</a><Button onClick={() => go('/signup')}>Create account <ArrowUpRight size={16}/></Button></nav></header>
    <main>
      <section className="landing-hero">
        <div className="hero-copy"><span className="eyebrow"><span className="green-dot"/> BUILT FOR YOUR NEXT CHAPTER</span><h1>Great ideas.<br/>Beautifully<br/><em>presented.</em></h1><p>Your research deserves a strong finish. Check academic formatting, understand what needs attention, and turn your draft into a more polished document.</p><div className="hero-actions"><Button onClick={() => go('/signup')}>Start your document review <ArrowRight size={18}/></Button><span>No Firebase setup.<br/>Just your next great draft.</span></div><div className="hero-trust"><ShieldCheck size={16}/> Private account <span>•</span><FileCheck2 size={16}/> Original file preserved</div></div>
        <div className="document-scene" aria-label="Illustration of a document formatting review"><div className="scene-grid"/><div className="scene-label">FROM FIRST DRAFT TO FINAL SUBMISSION</div><div className="paper"><div className="paper-top"><span>RESEARCH PAPER</span><BookOpen size={20}/></div><h3>The next chapter<br/>starts here.</h3><div className="paper-meta">ACADEMIC DOCUMENT · FORMATTING REVIEW</div><div className="paper-rule"/><b>01 &nbsp; Introduction</b><div className="paper-lines"><i/><i/><i/><i/></div><div className="paper-highlight"><CheckCheck size={17}/> Consistent typography</div><div className="paper-lines short"><i/><i/><i/></div><div className="paper-bottom"><span>ADF CHECK</span><span>01</span></div></div><div className="floating-review"><div className="review-icon"><Check size={24}/></div><div><b>A clearer path to submission</b><small>Check · Refine · Download</small></div></div><div className="floating-note"><Sparkles size={16}/> Every detail counts.</div></div>
      </section>
      <section className="landing-strip"><span>ONE FOCUSED WORKSPACE</span><b>9 formatting checks</b><b>3 useful downloads</b><b>Your original, untouched</b></section>
      <section id="how-it-works" className="how"><div><span className="eyebrow">A BETTER FINAL DRAFT</span><h2>A little less formatting.<br/>A lot more focus.</h2></div><div className="steps">{[['01','Bring your draft','Upload a Word document. We keep your original intact.'],['02','Find the details','Review clear findings across nine formatting categories.'],['03','Make it submission-ready','Download your PDF review, highlighted file and corrected copy.']].map(([n,title,text]) => <article key={n}><span>{n}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
    </main><footer className="landing-footer"><Brand/><span>Made for the work that matters.</span><a href="#/login">Open your workspace <ArrowUpRight size={15}/></a></footer>
  </div>;
}

function Auth({ signup, onAuth, notice }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);
  const form = useRef(null);
  useEffect(() => { setError(''); form.current?.reset(); }, [signup]);
  async function submit(e) {
    e.preventDefault(); setError('');
    const data = new FormData(e.currentTarget);
    if (signup && data.get('password') !== data.get('confirm')) { setError('Your passwords do not match.'); return; }
    setBusy(true);
    try { onAuth(await api(signup ? '/auth/signup' : '/auth/login', sendJSON({ username: data.get('username').trim(), password: data.get('password') }))); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <main className="auth-page"><aside className="auth-story"><Brand light/><div><span className="eyebrow">YOUR WORK DESERVES A STRONG FINISH</span><h1>Less fixing.<br/>More <em>finishing.</em></h1><p>A thoughtful workspace for your final draft. Review the details, refine your document, and move forward with confidence.</p><div className="auth-benefits"><span><CircleCheck/> Nine academic formatting checks</span><span><CircleCheck/> Clear reports and corrected documents</span><span><CircleCheck/> Private, protected account access</span></div></div><small>ADF CHECK &nbsp; / &nbsp; A BETTER FINAL DRAFT</small></aside><section className="auth-form-area"><a className="back-link" href="#/">← Back to overview</a><div className="auth-form"><div className="auth-symbol"><LockKeyhole size={24}/></div><span className="eyebrow">{signup ? 'START SOMETHING GREAT' : 'YOUR WORKSPACE IS WAITING'}</span><h2>{signup ? 'Create your account.' : 'Welcome back.'}</h2><p>{signup ? 'Just a username and password. Then you’re ready to review.' : 'Sign in to continue working on your next great draft.'}</p><ErrorMessage>{error || notice}</ErrorMessage><form ref={form} onSubmit={submit}><label>Username<input name="username" required minLength={3} maxLength={32} pattern="[a-zA-Z0-9_.\-]+" autoComplete="username" placeholder="e.g. aisha.research" disabled={busy}/></label>{signup && <small className="field-hint">3–32 letters, numbers, dots, underscores or hyphens.</small>}<label>Password<div className="password-field"><input name="password" type={show ? 'text' : 'password'} required minLength={8} maxLength={128} autoComplete={signup ? 'new-password' : 'current-password'} placeholder={signup ? 'At least 8 characters' : 'Enter your password'} disabled={busy}/><button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18}/> : <Eye size={18}/>}</button></div></label>{signup && <label>Confirm password<input name="confirm" type={show ? 'text' : 'password'} required minLength={8} maxLength={128} autoComplete="new-password" placeholder="Enter your password again" disabled={busy}/></label>}<Button type="submit" disabled={busy} className="full">{busy ? <LoaderCircle className="spin" size={18}/> : <>{signup ? 'Create account' : 'Sign in'}<ArrowRight size={18}/></>}</Button></form><p className="switch-auth">{signup ? 'Already have an account?' : 'New to ADF Check?'} <a href={signup ? '#/login' : '#/signup'}>{signup ? 'Sign in' : 'Create an account'}</a></p><div className="secure-note"><ShieldCheck size={16}/> Passwords are hashed. Your session is protected.</div></div><small className="auth-bottom">A focused space for your academic work.</small></section></main>;
}

function Workspace({ user, route, onLogout }) {
  const [menu, setMenu] = useState(false);
  const [reviews, setReviews] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busyLogout, setBusyLogout] = useState(false);
  const page = route === '/history' ? 'history' : route === '/guide' ? 'guide' : route === '/profiles' ? 'profiles' : 'workspace';
  async function refresh() { try { setReviews(await api('/reviews')); } catch (e) { setError(e.message); } }
  useEffect(() => { refresh(); }, []);
  useEffect(() => { setMenu(false); if (page === 'history') refresh(); }, [page]);
  async function logout() { setBusyLogout(true); try { await api('/auth/logout', { method:'POST' }); onLogout(); } catch (e) { if (e.status === 401) onLogout(); else setError(e.message); } finally { setBusyLogout(false); } }
  async function openReview(review) { try { setResult(await api(`/reviews/${review.id}`)); go('/workspace'); } catch (e) { setError(e.message); refresh(); } }
  function complete(review) { setResult(review); refresh(); }
  return <div className="app-shell">
    {menu && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMenu(false)}/>}
    <aside className={`sidebar ${menu ? 'open' : ''}`}><Brand/><button className="mobile-close icon-button" onClick={() => setMenu(false)} aria-label="Close menu"><X/></button><div className="nav-label">YOUR WORKSPACE</div><nav>{[['workspace','Document review',LayoutDashboard],['history','Recent reviews',FolderClock],['guide','Formatting guide',BookOpen],['profiles','University profiles',SlidersHorizontal]].map(([key,text,Icon]) => <a key={key} className={page === key ? 'active' : ''} href={`#/${key}`}><Icon size={19}/>{text}{page === key && <span className="nav-dot"/>}</a>)}</nav><div className="sidebar-note"><div className="note-icon"><Sparkles size={20}/></div><h3>A better final draft.</h3><p>Small details make a big difference. Give your research the finish it deserves.</p><a href="#/guide">Explore the standards <ArrowUpRight size={14}/></a></div><div className="sidebar-account"><span className="avatar">{user.username.slice(0,2).toUpperCase()}</span><div><b>{user.username}</b><small>Personal workspace</small></div><button className="icon-button" onClick={logout} aria-label="Sign out" title="Sign out" disabled={busyLogout}><LogOut size={18}/></button></div></aside>
    <div className="main-shell"><header className="topbar"><div><button className="mobile-toggle icon-button" aria-label="Open menu" onClick={() => setMenu(true)}><Menu/></button><span>Workspace</span><ChevronRight size={14}/><b>{page === 'history' ? 'Recent reviews' : page === 'guide' ? 'Formatting guide' : page === 'profiles' ? 'University profiles' : 'Document review'}</b></div><span className="private-badge"><ShieldCheck size={14}/> Private workspace</span></header><main className="workspace-main"><ErrorMessage>{error}</ErrorMessage>
      {page === 'workspace' && <><div className="page-heading"><div><span className="eyebrow">LET’S MAKE EVERY DETAIL COUNT</span><h1>Your next great submission.</h1><p>Check your formatting. Refine your draft. Focus on what matters.</p></div><div className="heading-mark"><FileCheck2 size={30}/></div></div>
        <div className="workspace-banner"><div className="banner-icon"><ScanText size={27}/></div><div><strong>A polished document starts with a thoughtful review.</strong><p>Nine checks, clear feedback, and a corrected copy—all in one place.</p></div><span className="tag">.DOCX READY</span></div>
        <div className="review-layout"><div><Upload onComplete={complete}/></div><aside className="right-rail"><section className="card standards-card"><div className="section-icon"><ListChecks size={20}/></div><h3>The details we check</h3><p>A complete look at your document’s formatting.</p>{['Fonts & heading styles','Line spacing & margins','Tables & figure captions','Headers & page numbers','APA reference patterns'].map(item => <div className="check-item" key={item}><CircleCheck size={16}/>{item}</div>)}<a href="#/guide">View formatting guide <ArrowRight size={15}/></a></section><div className="privacy-card"><ShieldCheck size={22}/><div><b>Your work stays yours.</b><p>Your original is never changed. Files are temporary and accessible only through your account.</p></div></div></aside></div>
        {result && <ReviewWorkspace key={result.id} result={result}/>}
        <Recent reviews={reviews.slice(0,3)} onOpen={openReview} compact/>
      </>}
      {page === 'history' && <><div className="page-heading"><div><span className="eyebrow">PICK UP WHERE YOU LEFT OFF</span><h1>Recent reviews.</h1><p>Your recent findings, ready when you need them.</p></div><Button onClick={() => go('/workspace')}><Plus size={17}/> New review</Button></div><Recent reviews={reviews} onOpen={openReview}/><div className="info-note"><Clock3 size={18}/><p>Reviews and downloads are temporary: up to 10 per account for one hour, while this server is running. Your account stays saved; document files do not.</p></div></>}
      {page === 'profiles' && <ProfileManager/>}
      {page === 'guide' && <><div className="page-heading"><div><span className="eyebrow">THE SMALL DETAILS, EXPLAINED</span><h1>Your formatting field guide.</h1><p>The built-in default rules. Create a department profile to use different standards.</p></div></div><div className="guide-grid">{categories.map(([title,text,Icon],i) => <section className="card guide-card" key={title}><div><Icon size={24}/><span>0{i+1}</span></div><h3>{title}</h3><p>{text}</p></section>)}</div><section className="card guide-explainer"><h3>What automatic correction does</h3><p>Applies fonts, font sizes, line spacing and margins; aligns existing header page-number fields. Text, tables and document fields are preserved.</p><h3>What still needs your judgment</h3><p>Review reference accuracy, heading structure and missing page numbers manually. Page locations are estimates, and APA screening uses patterns rather than full citation verification. Optional AI estimates are not plagiarism checks or proof of authorship.</p><Button onClick={() => go('/workspace')}>Review a document <ArrowRight size={17}/></Button></section></>}
    </main><footer className="app-footer"><span>ADF Check <span className="muted">/ A better final draft.</span></span><span>Made for academic work.</span></footer></div>
  </div>;
}

function Upload({ onComplete }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [ai, setAi] = useState(false);
  const [profileId, setProfileId] = useState('default');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const input = useRef(null);
  function choose(next) {
    if (busy || !next) return;
    setError('');
    if (!next.name.toLowerCase().endsWith('.docx')) { setError('Please choose a Word .docx document.'); return; }
    if (next.size > 20*1024*1024) { setError('This file is too large. The limit is 20 MB.'); return; }
    if (!next.size) { setError('This file is empty. Choose a valid Word document.'); return; }
    setFile(next);
  }
  async function submit() {
    if (!file || busy) return;
    setBusy(true); setError('');
    try { onComplete(await api(`/reviews?include_ai=${ai}&profile_id=${encodeURIComponent(profileId)}`, { method:'POST', body:file, headers:{ 'Content-Type':'application/octet-stream', 'X-Filename':encodeURIComponent(file.name) } })); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <section className="card upload-card"><div className="card-heading"><div><h2>Bring your draft.</h2><p>Upload a document to begin your review.</p></div><span className="step-label">STEP 01</span></div><ProfilePicker value={profileId} onChange={setProfileId} disabled={busy}/><input ref={input} type="file" className="visually-hidden" accept=".docx" aria-label="Choose Word document" disabled={busy} onChange={(e) => choose(e.target.files[0])}/><button type="button" className={`dropzone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`} disabled={busy} onClick={() => input.current.click()} onDragOver={(e) => {e.preventDefault(); setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={(e) => {e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]);}}><span className="upload-icon">{file ? <FileText size={27}/> : <UploadCloud size={29}/>}</span><strong>{file ? file.name : 'Drop your document here'}</strong><span>{file ? `${(file.size/1024).toFixed(0)} KB · Click to choose another file` : <>or <b>browse files</b> from your computer</>}</span><small>WORD DOCUMENT (.DOCX) &nbsp; · &nbsp; UP TO 20 MB</small></button><label className="ai-option"><input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} disabled={busy}/><span><strong>Include an AI content estimate <span className="optional">OPTIONAL</span></strong><small>Sends the first 3,000 characters to an external detector. Not a plagiarism check.</small></span></label><ErrorMessage>{error}</ErrorMessage><Button className="full analyze-button" onClick={submit} disabled={!file || busy}>{busy ? <><LoaderCircle size={18} className="spin"/> Reviewing your document…</> : <>Analyze document <ArrowRight size={18}/></>}</Button><div className="upload-footnote" aria-live="polite">{busy ? 'Checking your selected rules and preparing the review. Please keep this page open.' : <><LockKeyhole size={12}/> Your original document stays unchanged.</>}</div></section>;
}

function Recent({ reviews, onOpen, compact=false }) {
  return <section className="recent-section"><div className="recent-title"><h2>{compact ? 'Your recent activity' : 'Document reviews'}</h2>{compact && <a href="#/history">View all <ArrowRight size={15}/></a>}</div><div className="card recent-card">{reviews.length ? <div className="review-table"><div className="table-head"><span>DOCUMENT</span><span>REVIEWED</span><span>STATUS</span><span/></div>{reviews.map(review => <button className="review-row" key={review.id} onClick={() => onOpen(review)}><span className="review-name"><span className="file-mini"><FileText size={20}/></span><span><b>{review.filename}</b><small>{review.total} issue group(s) · {review.words.toLocaleString()} words</small></span></span><span className="review-date">{date(review.created_at)}</span><span className={`status ${review.total ? 'review' : 'clear'}`}>{review.total ? 'Needs review' : 'No findings'}</span><ArrowUpRight size={17}/></button>)}</div> : <div className="empty-state"><span><FolderClock size={26}/></span><h3>A fresh page awaits.</h3><p>Your recent document reviews will appear here.<br/>Upload your first draft to get started.</p></div>}</div></section>;
}

const root = document.getElementById('root');
if (root) createRoot(root).render(<React.StrictMode><App/></React.StrictMode>);
