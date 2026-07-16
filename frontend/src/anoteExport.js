export function buildAnoteImportPayload(rows, context, now = () => new Date().toISOString()) {
  const data = rows.map(({ status, ...row }) => row);
  const columns = data.length ? Object.keys(data[0]) : context.columns;

  return {
    name: context.name,
    columns,
    rows: data,
    source: 'anote-synthetic-data',
    metadata: {
      task_type: context.taskType,
      prompt: context.prompt,
      generated_rows: data.length,
      created_at: now(),
    },
  };
}

export function projectUrlFromResponse(body) {
  return body.project_url || body.url || body.project?.url ||
    (body.project_id ? `https://anote.ai/projects/${body.project_id}` : null);
}
