import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import App from './App';

const ANOTE_IMPORT_URL = 'https://api.anote.ai/api/import/dataset';
const ANOTE_KEY_STORAGE = 'anote_product_api_key';

function jsonResponse(data, { ok = true, status = 200 } = {}) {
  return Promise.resolve({ ok, status, statusText: 'error', json: async () => data });
}

// Builds a fetch Response whose body is a single-chunk SSE stream, matching
// how /public/generate/stream is consumed in App.js (reader.read() + 'data: ' lines).
function sseResponse(events) {
  const text = events.map(e => `data: ${JSON.stringify(e)}\n`).join('');
  const chunk = new TextEncoder().encode(text);
  let delivered = false;
  return Promise.resolve({
    ok: true,
    body: {
      getReader() {
        return {
          read: async () => {
            if (!delivered) {
              delivered = true;
              return { done: false, value: chunk };
            }
            return { done: true, value: undefined };
          },
        };
      },
    },
  });
}

// URL-substring-matched fetch dispatcher. Tests prepend handlers that need to
// override the defaults (versions / quality), which always resolve harmlessly.
function mockFetch(handlers = []) {
  const allHandlers = [
    ...handlers,
    ['/public/generate/versions', () => jsonResponse({ versions: [] })],
    ['/public/generate/quality', () => jsonResponse({ quality: null })],
  ];
  global.fetch = jest.fn((url) => {
    const u = String(url);
    const match = allHandlers.find(([needle]) => u.includes(needle));
    if (match) return match[1](u);
    return jsonResponse({});
  });
}

// Renders App and waits out the mount-time history fetch so it doesn't land
// mid-test and trip React's "update not wrapped in act" warning.
async function renderApp() {
  render(<App />);
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
}

async function generateOneRow() {
  mockFetch([
    ['/public/generate/stream', () => sseResponse([
      { type: 'progress', row: 0, total: 1, data: { question: 'Q1', answer: 'A1', status: 'succeeded' } },
      { type: 'done', data: [{ question: 'Q1', answer: 'A1', status: 'succeeded' }], version_id: 'abcdef1234567890' },
    ])],
  ]);

  await renderApp();

  fireEvent.change(screen.getByLabelText('Prompt'), { target: { value: 'Generate Q&A pairs' } });
  fireEvent.click(screen.getByRole('button', { name: /generate/i }));

  await screen.findByText(/Results — 1 rows/);
}

beforeEach(() => {
  window.localStorage.clear();
  jest.restoreAllMocks();
  global.URL.createObjectURL = jest.fn(() => 'blob:mock');
  global.URL.revokeObjectURL = jest.fn();
});

test('renders the generator form with default fields', async () => {
  mockFetch();
  await renderApp();
  expect(screen.getByRole('heading', { name: /Anote Synthetic Data Generator/i })).toBeInTheDocument();
  expect(screen.getByLabelText('Prompt')).toBeInTheDocument();
  expect(screen.getByLabelText(/Columns/)).toHaveValue('question,answer');
});

test('shows validation errors and does not submit when the prompt is empty', async () => {
  mockFetch();
  await renderApp();

  const callsBeforeSubmit = global.fetch.mock.calls.length;

  fireEvent.click(screen.getByRole('button', { name: /generate/i }));

  expect(await screen.findByText('Prompt is required')).toBeInTheDocument();
  // No new network call (i.e. /public/generate/stream was never hit) beyond the initial mount fetch.
  expect(global.fetch.mock.calls.length).toBe(callsBeforeSubmit);
});

test('rejects a row count outside 1-100', async () => {
  mockFetch();
  await renderApp();

  fireEvent.change(screen.getByLabelText('Prompt'), { target: { value: 'Some prompt' } });
  fireEvent.change(document.getElementById('numRows'), { target: { value: '500' } });
  fireEvent.click(screen.getByRole('button', { name: /generate/i }));

  expect(await screen.findByText('Must be 1–100')).toBeInTheDocument();
});

test('streams a generation and renders the results table with export buttons', async () => {
  await generateOneRow();

  expect(screen.getByText('Q1')).toBeInTheDocument();
  expect(screen.getByText('A1')).toBeInTheDocument();
  expect(screen.getByText(/v:abcdef12/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '↓ CSV' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '↓ JSONL' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Send to Anote Product →' })).toBeInTheDocument();
});

test('downloading CSV builds a blob without throwing', async () => {
  await generateOneRow();

  // jsdom has no real download behavior for <a download>; it would otherwise
  // log a fake "Not implemented: navigation" error when the link is clicked.
  const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

  fireEvent.click(screen.getByRole('button', { name: '↓ CSV' }));

  expect(global.URL.createObjectURL).toHaveBeenCalled();
  expect(clickSpy).toHaveBeenCalled();
});

test('Send to Anote Product: prompts for an API key, posts the dataset, and shows the project link', async () => {
  await generateOneRow();

  mockFetch([
    ['/public/generate/stream', () => sseResponse([])], // not used again in this test
    [ANOTE_IMPORT_URL, () => jsonResponse({ project_id: 'proj-123' })],
  ]);

  jest.spyOn(window, 'prompt')
    .mockReturnValueOnce('anote-key-123') // API key prompt
    .mockReturnValueOnce('My Project');   // project name prompt

  fireEvent.click(screen.getByRole('button', { name: 'Send to Anote Product →' }));

  await screen.findByText('Project created in Anote');
  const link = screen.getByRole('link', { name: /Open in Anote/i });
  expect(link).toHaveAttribute('href', 'https://anote.ai/projects/proj-123');

  // Key is persisted so the next call skips the prompt.
  expect(window.localStorage.getItem(ANOTE_KEY_STORAGE)).toBe('anote-key-123');

  const importCall = global.fetch.mock.calls.find(([url]) => String(url) === ANOTE_IMPORT_URL);
  expect(importCall).toBeTruthy();
  const [, options] = importCall;
  expect(options.headers.Authorization).toBe('Bearer anote-key-123');
  const body = JSON.parse(options.body);
  expect(body.rows).toEqual([{ question: 'Q1', answer: 'A1' }]);
  expect(body.name).toBe('My Project');
});

test('Send to Anote Product: reuses a stored API key without prompting again', async () => {
  window.localStorage.setItem(ANOTE_KEY_STORAGE, 'stored-key');
  await generateOneRow();

  mockFetch([
    ['/public/generate/stream', () => sseResponse([])],
    [ANOTE_IMPORT_URL, () => jsonResponse({ project_id: 'proj-456' })],
  ]);

  const promptSpy = jest.spyOn(window, 'prompt').mockReturnValueOnce('My Project');

  fireEvent.click(screen.getByRole('button', { name: 'Send to Anote Product →' }));

  await screen.findByText('Project created in Anote');
  // Only the project-name prompt fires; the API key prompt is skipped.
  expect(promptSpy).toHaveBeenCalledTimes(1);
});

test('Send to Anote Product: shows a clear error when no API key is provided', async () => {
  await generateOneRow();

  jest.spyOn(window, 'prompt').mockReturnValueOnce(null);

  fireEvent.click(screen.getByRole('button', { name: 'Send to Anote Product →' }));

  expect(await screen.findByText('Enter your Anote API key from anote.ai/settings')).toBeInTheDocument();
});

test('Send to Anote Product: surfaces a failed import and clears the stored key', async () => {
  window.localStorage.setItem(ANOTE_KEY_STORAGE, 'bad-key');
  await generateOneRow();

  mockFetch([
    ['/public/generate/stream', () => sseResponse([])],
    [ANOTE_IMPORT_URL, () => jsonResponse({ error: 'Invalid API key' }, { ok: false, status: 401 })],
  ]);

  jest.spyOn(window, 'prompt').mockReturnValueOnce('My Project');

  fireEvent.click(screen.getByRole('button', { name: 'Send to Anote Product →' }));

  expect(await screen.findByText('Invalid API key')).toBeInTheDocument();
  expect(window.localStorage.getItem(ANOTE_KEY_STORAGE)).toBeNull();
});

test('applying a template fills in the prompt and columns', async () => {
  mockFetch();
  await renderApp();

  const templateButton = screen.getByRole('button', { name: 'Sentiment Analysis' });
  fireEvent.click(templateButton);

  expect(screen.getByLabelText('Prompt')).toHaveValue(
    'Generate customer reviews with positive, negative, and neutral sentiment about a SaaS product'
  );
  expect(screen.getByLabelText(/Columns/)).toHaveValue('text,label');
});

test('ROI calculator updates estimated cost when rows change', async () => {
  mockFetch();
  await renderApp();

  const roiSection = screen.getByText('ROI calculator').closest('section');
  const rowsInput = within(roiSection).getByLabelText('Rows needed');

  fireEvent.change(rowsInput, { target: { value: '2000' } });

  const syntheticRow = within(roiSection).getByText('Anote Synthetic Data').closest('tr');
  // 2000 rows * $0.003-$0.03/row synthetic rate
  expect(within(syntheticRow).getByText('$6.00 - $60.00')).toBeInTheDocument();
});
