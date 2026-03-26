// src/App.js
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';
const MAX_HISTORY = 10;

// Task-specific parameter configurations
const TASK_PARAMS = {
  text: [
    { key: 'model', label: 'Model', type: 'select', options: ['gpt-4o-mini', 'gpt-4o'], default: 'gpt-4o-mini' },
    { key: 'batch_size', label: 'Batch Size', type: 'number', default: 10, min: 1, max: 20 },
    { key: 'concurrency', label: 'Concurrency', type: 'number', default: 5, min: 1, max: 10 },
  ],
  image: [
    { key: 'image_size', label: 'Image Size', type: 'select', options: ['1024x1024', '1792x1024', '1024x1792'], default: '1024x1024' },
    { key: 'style', label: 'Style', type: 'select', options: ['vivid', 'natural'], default: 'vivid' },
    { key: 'run_detection', label: 'Run YOLO Detection', type: 'checkbox', default: true },
  ],
  audio: [
    { key: 'voice', label: 'Voice', type: 'select', options: ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'], default: 'nova' },
    { key: 'tts_model', label: 'TTS Model', type: 'select', options: ['tts-1', 'tts-1-hd'], default: 'tts-1' },
    { key: 'speed', label: 'Speed', type: 'number', default: 1.0, min: 0.25, max: 4.0, step: 0.25 },
  ],
  video: [
    { key: 'width', label: 'Width', type: 'number', default: 576, min: 128, max: 1024 },
    { key: 'height', label: 'Height', type: 'number', default: 320, min: 128, max: 1024 },
    { key: 'fps', label: 'FPS', type: 'number', default: 6, min: 1, max: 30 },
    { key: 'num_frames', label: 'Num Frames', type: 'number', default: 24, min: 8, max: 120 },
    { key: 'annotate_frames', label: 'Annotate Frames (GPT-4o)', type: 'checkbox', default: false },
  ],
  agent: [
    { key: 'difficulty', label: 'Difficulty', type: 'select', options: ['easy', 'medium', 'hard'], default: 'medium' },
    { key: 'concurrency', label: 'Concurrency', type: 'number', default: 3, min: 1, max: 5 },
  ],
  pii: [],
  tabular: [
    { key: 'batch_size', label: 'Batch Size', type: 'number', default: 10, min: 1, max: 20 },
  ],
  code: [
    { key: 'code_type', label: 'Code Type', type: 'select', options: ['function', 'unittest', 'bugfix', 'review', 'docstring'], default: 'function' },
    { key: 'language', label: 'Language', type: 'select', options: ['python', 'javascript', 'typescript', 'go', 'rust', 'java', 'cpp', 'sql'], default: 'python' },
    { key: 'validate_syntax', label: 'Validate Syntax', type: 'checkbox', default: true },
  ],
};

function MediaPreview({ value }) {
  if (!value || typeof value !== 'string') return null;
  if (value.startsWith('data:image') || (value.length > 100 && /^[A-Za-z0-9+/=]+$/.test(value.slice(0, 50)))) {
    const src = value.startsWith('data:') ? value : `data:image/png;base64,${value}`;
    return <img src={src} alt="generated" style={{ maxWidth: 200, maxHeight: 200, display: 'block' }} />;
  }
  return null;
}

function ResultTable({ data }) {
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;
  if (!data || !data.length) return null;
  const columns = Object.keys(data[0]);
  const totalPages = Math.ceil(data.length / PAGE_SIZE);
  const rows = data.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.85rem' }}>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col} style={{ border: '1px solid #ccc', padding: '6px 10px', background: '#f5f5f5', textAlign: 'left' }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map(col => (
                <td key={col} style={{ border: '1px solid #ccc', padding: '6px 10px', maxWidth: 300 }}>
                  <MediaPreview value={row[col]} />
                  {typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div style={{ marginTop: '0.5rem' }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>Prev</button>
          {' '}{page + 1} / {totalPages}{' '}
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1}>Next</button>
        </div>
      )}
    </div>
  );
}

function downloadFile(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function toCSV(data) {
  if (!data.length) return '';
  const cols = Object.keys(data[0]);
  const header = cols.join(',');
  const rows = data.map(row =>
    cols.map(c => JSON.stringify(row[c] ?? '')).join(',')
  );
  return [header, ...rows].join('\n');
}

function toJSONL(data) {
  return data.map(row => JSON.stringify(row)).join('\n');
}

function buildInitialParams(taskType) {
  const params = {};
  (TASK_PARAMS[taskType] || []).forEach(({ key, default: def }) => { params[key] = def; });
  return params;
}

function App() {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('anote_api_key') || '');
  const [taskType, setTaskType] = useState('text');
  const [prompt, setPrompt] = useState('');
  const [numRows, setNumRows] = useState(5);
  const [columns, setColumns] = useState('question,answer');
  const [examples, setExamples] = useState('');
  const [params, setParams] = useState(() => buildInitialParams('text'));
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem('anote_history') || '[]'); } catch { return []; }
  });

  useEffect(() => { localStorage.setItem('anote_api_key', apiKey); }, [apiKey]);
  useEffect(() => { localStorage.setItem('anote_history', JSON.stringify(history)); }, [history]);

  const handleTaskTypeChange = useCallback((newType) => {
    setTaskType(newType);
    setParams(buildInitialParams(newType));
  }, []);

  const handleParamChange = (key, value) => {
    setParams(prev => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setResult(null);
    setError(null);
    if (!apiKey.trim()) { setError('API key is required'); return; }
    if (!prompt.trim()) { setError('Prompt is required'); return; }
    const colList = columns.split(',').map(c => c.trim()).filter(Boolean);
    if (!colList.length) { setError('At least one column is required'); return; }

    let parsedExamples = [];
    if (examples.trim()) {
      try { parsedExamples = JSON.parse(examples); }
      catch { setError('Examples must be valid JSON array'); return; }
    }

    setLoading(true);
    try {
      const response = await axios.post(
        `${API_BASE}/public/generate`,
        { task_type: taskType, prompt, num_rows: Number(numRows), columns: colList, examples: parsedExamples, params },
        { headers: { Authorization: `Bearer ${apiKey}` } }
      );
      const data = response.data.data || response.data;
      setResult(data);
      const entry = { taskType, prompt, columns, numRows, params, timestamp: new Date().toISOString() };
      setHistory(prev => [entry, ...prev].slice(0, MAX_HISTORY));
    } catch (err) {
      const apiError = err.response?.data?.error || err.response?.data?.details?.[0]?.msg || err.message;
      setError(apiError);
    } finally {
      setLoading(false);
    }
  };

  const restoreHistory = (entry) => {
    setTaskType(entry.taskType);
    setPrompt(entry.prompt);
    setColumns(entry.columns);
    setNumRows(entry.numRows);
    setParams(entry.params || buildInitialParams(entry.taskType));
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif', maxWidth: 900, margin: '0 auto' }}>
      <h2>Anote Synthetic Data Generator</h2>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label>API Key<br />
            <input
              type="password"
              placeholder="Bearer token"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              style={{ width: '100%', padding: '6px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label>Task Type<br />
            <select value={taskType} onChange={(e) => handleTaskTypeChange(e.target.value)} style={{ padding: '6px' }}>
              {Object.keys(TASK_PARAMS).map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label>Prompt<br />
            <textarea
              placeholder="Describe what data to generate..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              style={{ width: '100%', height: '4rem', padding: '6px' }}
            />
          </label>
        </div>

        <div style={{ marginBottom: '1rem', display: 'flex', gap: '1rem' }}>
          <label>Num Rows<br />
            <input type="number" value={numRows} min={1} max={100}
              onChange={(e) => setNumRows(e.target.value)}
              style={{ width: 80, padding: '6px' }} />
          </label>
          <label style={{ flex: 1 }}>Columns (comma-separated)<br />
            <input type="text" value={columns} onChange={(e) => setColumns(e.target.value)}
              style={{ width: '100%', padding: '6px' }} />
          </label>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label>Examples (JSON array, optional)<br />
            <textarea
              placeholder='[{"col1": "value1", "col2": "value2"}]'
              value={examples}
              onChange={(e) => setExamples(e.target.value)}
              style={{ width: '100%', height: '5rem', padding: '6px', fontFamily: 'monospace', fontSize: '0.8rem' }}
            />
          </label>
        </div>

        {TASK_PARAMS[taskType]?.length > 0 && (
          <div style={{ background: '#f9f9f9', border: '1px solid #ddd', borderRadius: 4, padding: '1rem', marginBottom: '1rem' }}>
            <strong>{taskType.charAt(0).toUpperCase() + taskType.slice(1)} Options</strong>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginTop: '0.5rem' }}>
              {TASK_PARAMS[taskType].map(({ key, label, type, options, min, max, step, default: def }) => (
                <label key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {label}
                  {type === 'select' && (
                    <select value={params[key] ?? def} onChange={(e) => handleParamChange(key, e.target.value)} style={{ padding: '4px' }}>
                      {options.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  )}
                  {type === 'number' && (
                    <input type="number" value={params[key] ?? def} min={min} max={max} step={step}
                      onChange={(e) => handleParamChange(key, Number(e.target.value))}
                      style={{ width: 80, padding: '4px' }} />
                  )}
                  {type === 'checkbox' && (
                    <input type="checkbox" checked={params[key] ?? def}
                      onChange={(e) => handleParamChange(key, e.target.checked)} />
                  )}
                </label>
              ))}
            </div>
          </div>
        )}

        <button type="submit" disabled={loading}
          style={{ padding: '8px 24px', fontSize: '1rem', cursor: loading ? 'not-allowed' : 'pointer' }}>
          {loading ? 'Generating...' : 'Generate'}
        </button>
      </form>

      {error && <div style={{ color: 'red', marginTop: '1rem', padding: '0.5rem', background: '#fff5f5', border: '1px solid #ffcccc', borderRadius: 4 }}>Error: {error}</div>}

      {result && (
        <div style={{ marginTop: '1.5rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
            <strong>Results ({result.length} rows)</strong>
            <button onClick={() => downloadFile(toCSV(result), 'synthetic_data.csv', 'text/csv')}>Download CSV</button>
            <button onClick={() => downloadFile(toJSONL(result), 'synthetic_data.jsonl', 'application/x-ndjson')}>Download JSONL</button>
            <button onClick={() => { navigator.clipboard.writeText(JSON.stringify(result, null, 2)); }}>Copy JSON</button>
          </div>
          <ResultTable data={result} />
        </div>
      )}

      {history.length > 0 && (
        <div style={{ marginTop: '2rem' }}>
          <strong>Recent Generations</strong>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {history.map((entry, i) => (
              <li key={i} style={{ padding: '4px 0', borderBottom: '1px solid #eee', cursor: 'pointer', fontSize: '0.85rem' }}
                onClick={() => restoreHistory(entry)}>
                <span style={{ color: '#666' }}>{entry.timestamp.slice(0, 16)}</span>{' '}
                <strong>{entry.taskType}</strong> — {entry.prompt.slice(0, 60)}{entry.prompt.length > 60 ? '…' : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default App;
