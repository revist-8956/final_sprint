// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('글을 열고 좋아요를 누르면 서버가 준 숫자를 보여준다', async () => {
  let likes = 0;
  const post = () => ({ id: '1', title: '첫 글', content: '안녕하세요', createdAt: '2026-11-10T00:00:00Z', comments: [], likes });
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/likes')) likes += 1;
    const data = url === '/api/posts' ? [post()] : post();
    return { ok: true, json: async () => data };
  }));

  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: /첫 글/ }));
  fireEvent.click(await screen.findByRole('button', { name: /좋아요, 현재 0개/ }));
  await waitFor(() => expect(screen.getByRole('button', { name: /좋아요, 현재 1개/ })).toBeTruthy());
});

it('목록은 다섯 개씩 보여 주고 연필 버튼으로 글쓰기를 연다', async () => {
  const posts = Array.from({ length: 6 }, (_, index) => ({
    id: String(index + 1), title: `글 ${index + 1}`,
    createdAt: '2026-11-10T00:00:00Z', likes: 0,
  }));
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => posts })));

  render(<App />);
  expect(await screen.findByText('6개')).toBeTruthy();
  expect(screen.getAllByRole('listitem')).toHaveLength(5);
  expect(screen.queryByRole('button', { name: /글 6 / })).toBeNull();

  fireEvent.click(screen.getByRole('button', { name: '다음' }));
  expect(screen.getAllByRole('listitem')).toHaveLength(1);
  expect(screen.getByRole('button', { name: /글 6 / })).toBeTruthy();
  expect(screen.queryByRole('heading', { name: '새 글 쓰기' })).toBeNull();

  fireEvent.click(screen.getByRole('button', { name: '새 글 쓰기' }));
  expect(screen.getByRole('heading', { name: '새 글 쓰기' })).toBeTruthy();
  expect(screen.queryByRole('heading', { name: '글 목록' })).toBeNull();
  expect(screen.queryByRole('heading', { name: '글을 선택해 주세요' })).toBeNull();
  fireEvent.change(screen.getByRole('textbox', { name: '제목' }), { target: { value: '임시 제목' } });
  fireEvent.click(screen.getByRole('button', { name: '글쓰기 취소' }));
  expect(screen.getByRole('heading', { name: '글 목록' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '새 글 쓰기' }));
  expect((screen.getByRole('textbox', { name: '제목' }) as HTMLInputElement).value).toBe('');
});
