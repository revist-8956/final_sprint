import { useEffect, useState, type FormEvent } from 'react';

type PostSummary = { id: string; title: string; createdAt: string; likes: number };
type Comment = { id: string; content: string; createdAt: string };
type Post = PostSummary & { content: string; comments: Comment[] };

async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/api/posts${path}`, body ? {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  } : undefined);
  if (!response.ok) throw new Error('요청을 처리하지 못했어요. Redis와 서버를 확인해 주세요.');
  return response.json() as Promise<T>;
}

const date = (value: string) => new Intl.DateTimeFormat('ko-KR', {
  dateStyle: 'medium', timeStyle: 'short',
}).format(new Date(value));

export default function App() {
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [selected, setSelected] = useState<Post | null>(null);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [comment, setComment] = useState('');
  const [composerOpen, setComposerOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pageCount = Math.max(1, Math.ceil(posts.length / 5));
  const visiblePosts = posts.slice((page - 1) * 5, page * 5);

  async function loadPosts() { setPosts(await api<PostSummary[]>('')); }

  useEffect(() => { void loadPosts().catch(e => setError(e.message)); }, []);
  useEffect(() => {
    if (composerOpen) document.getElementById('new-post')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, [composerOpen]);

  async function openPost(id: string) {
    try { setError(''); setSelected(await api<Post>(`/${id}`)); }
    catch (e) { setError((e as Error).message); }
  }

  async function createPost(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const created = await api<Post>('', { title, content });
      setTitle(''); setContent(''); setSelected(created); setComposerOpen(false); setPage(1);
      await loadPosts();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function addComment(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true); setError('');
    try { setSelected(await api<Post>(`/${selected.id}/comments`, { content: comment })); setComment(''); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function like() {
    if (!selected) return;
    setBusy(true); setError('');
    try { setSelected(await api<Post>(`/${selected.id}/likes`, {})); await loadPosts(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function cancelPost() {
    setTitle(''); setContent(''); setError(''); setComposerOpen(false);
  }

  return <div className="page">
    <header className="site-header">
      <p className="eyebrow">PRACTICE BOARD</p>
      <h1>작은 게시판</h1>
      <p>글을 쓰고, 댓글을 남기고, 좋아요를 눌러 보세요.</p>
    </header>

    {error && <p className="error" role="alert">{error}</p>}

    <div className={composerOpen ? 'layout writing' : 'layout'}>
      {composerOpen ? <main className="panel composer" id="new-post">
        <div className="section-heading">
          <h2>새 글 쓰기</h2>
          <button className="icon-button" type="button" aria-label="글쓰기 취소" title="글쓰기 취소"
            disabled={busy} onClick={cancelPost}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
              <path d="M5 5l14 14M19 5 5 19" />
            </svg>
          </button>
        </div>
        <form onSubmit={createPost}>
          <label htmlFor="title">제목</label>
          <input id="title" value={title} onChange={e => setTitle(e.target.value)} maxLength={100} required placeholder="무슨 이야기를 나눌까요?" />
          <label htmlFor="content">내용</label>
          <textarea id="content" value={content} onChange={e => setContent(e.target.value)} maxLength={2000} required rows={8} placeholder="내용을 적어 주세요." />
          <button className="primary" disabled={busy} type="submit">글 올리기</button>
        </form>
      </main> : <>
      <aside className="sidebar">
        <section className="panel">
          <div className="section-heading">
            <div className="section-title"><h2>글 목록</h2><span>{posts.length}개</span></div>
            <button className="icon-button" type="button" aria-label="새 글 쓰기"
              onClick={() => setComposerOpen(true)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L9 17l-4 1 1-4 10.5-10.5Z" />
              </svg>
            </button>
          </div>
          {posts.length === 0 ? <p className="muted">아직 글이 없어요. 첫 글을 작성해 보세요.</p> :
            <ul className="post-list">{visiblePosts.map(post => <li key={post.id}>
              <button className={selected?.id === post.id ? 'post-link active' : 'post-link'}
                onClick={() => void openPost(post.id)} aria-current={selected?.id === post.id ? 'true' : undefined}>
                <strong>{post.title}</strong>
                <span>{date(post.createdAt)} · 좋아요 {post.likes}</span>
              </button>
            </li>)}</ul>}
          {pageCount > 1 && <nav className="pagination" aria-label="글 목록 페이지">
            <button type="button" onClick={() => setPage(current => current - 1)} disabled={page === 1}>이전</button>
            <span>{page} / {pageCount}</span>
            <button type="button" onClick={() => setPage(current => current + 1)} disabled={page === pageCount}>다음</button>
          </nav>}
        </section>

      </aside>

      <main className="panel detail">
        {selected ? <>
          <div className="post-head">
            <div><p className="eyebrow">POST</p><h2>{selected.title}</h2><time dateTime={selected.createdAt}>{date(selected.createdAt)}</time></div>
            <button className="like" onClick={() => void like()} disabled={busy} aria-label={`좋아요, 현재 ${selected?.likes ?? 0}개`}>♥ 좋아요 {selected?.likes ?? 0}</button>
          </div>
          <p className="post-body">{selected.content}</p>
          <section className="comments">
            <h3>댓글 <span>{selected.comments.length}</span></h3>
            {selected.comments.length === 0 ? <p className="muted">첫 댓글을 남겨 보세요.</p> :
              <ul>{selected.comments.map(item => <li key={item.id}>
                <p>{item.content}</p><time dateTime={item.createdAt}>{date(item.createdAt)}</time>
              </li>)}</ul>}
            <form onSubmit={addComment}>
              <label htmlFor="comment">익명 댓글</label>
              <textarea id="comment" value={comment} onChange={e => setComment(e.target.value)} maxLength={500} required rows={3} placeholder="댓글을 적어 주세요." />
              <button className="primary" disabled={busy} type="submit">댓글 남기기</button>
            </form>
          </section>
        </> : <div className="empty-detail"><span aria-hidden="true">✎</span><h2>글을 선택해 주세요</h2><p>왼쪽에서 글을 고르거나 새 글을 작성해 보세요.</p></div>}
      </main>
      </>}
    </div>
  </div>;
}
