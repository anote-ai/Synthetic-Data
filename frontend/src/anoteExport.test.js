import { buildAnoteImportPayload, projectUrlFromResponse } from './anoteExport';

test('builds an import payload without internal row status', () => {
  const payload = buildAnoteImportPayload(
    [{ text: 'Hello', label: 'greeting', status: 'complete' }],
    { name: 'Greetings', columns: [], taskType: 'text', prompt: 'Generate greetings' },
    () => '2026-07-16T00:00:00.000Z',
  );
  expect(payload.rows).toEqual([{ text: 'Hello', label: 'greeting' }]);
  expect(payload.columns).toEqual(['text', 'label']);
  expect(payload.metadata.generated_rows).toBe(1);
  expect(payload.metadata.created_at).toBe('2026-07-16T00:00:00.000Z');
});

test('builds the required direct project link from an id', () => {
  expect(projectUrlFromResponse({ project_id: 'project-123' }))
    .toBe('https://anote.ai/projects/project-123');
});

test('prefers a project URL returned by the API', () => {
  expect(projectUrlFromResponse({ project_url: 'https://anote.ai/p/custom' }))
    .toBe('https://anote.ai/p/custom');
});
