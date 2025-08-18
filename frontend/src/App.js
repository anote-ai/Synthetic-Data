// src/App.js
import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [apiKey, setApiKey] = useState('');
  const [taskType, setTaskType] = useState('text');
  const [prompt, setPrompt] = useState('');
  const [numRows, setNumRows] = useState(5);
  const [columns, setColumns] = useState('question,answer');
  const [examples, setExamples] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setResult(null);
    setError(null);
    setLoading(true);
    try {
      const response = await axios.post(
        'http://localhost:5000/public/generate',
        {
          task_type: taskType,
          prompt,
          num_rows: Number(numRows),
          columns: columns.split(',').map(col => col.trim()),
          examples: examples ? JSON.parse(examples) : []
        },
        {
          headers: {
            ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
          },
        }
      );
      setResult(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadJSON = () => {
    if (!result || !result.data) return;
    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    a.download = `generated_${taskType}_${ts}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const toCSV = (rows) => {
    if (!rows || rows.length === 0) return '';
    const explicitCols = columns.split(',').map(c => c.trim()).filter(Boolean);
    const headerSet = new Set(explicitCols.length ? explicitCols : Object.keys(rows.reduce((acc, r) => { Object.keys(r || {}).forEach(k => acc[k] = true); return acc; }, {})));
    const headers = Array.from(headerSet);
    const esc = (v) => {
      if (v === null || v === undefined) return '';
      const s = typeof v === 'string' ? v : JSON.stringify(v);
      const needsQuote = /[",\n]/.test(s);
      const escaped = s.replace(/"/g, '""');
      return needsQuote ? `"${escaped}"` : escaped;
    };
    const lines = [headers.join(',')];
    for (const row of rows) {
      lines.push(headers.map(h => esc(row ? row[h] : '')).join(','));
    }
    return lines.join('\n');
  };

  const downloadCSV = () => {
    if (!result || !result.data) return;
    const csv = toCSV(result.data);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    a.download = `generated_${taskType}_${ts}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
      <h2>Anote Generate</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="API Key (optional)"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          style={{ width: '100%', marginBottom: '1rem' }}
        />
        <select value={taskType} onChange={(e) => setTaskType(e.target.value)}>
          <option value="text">Text</option>
          <option value="pii">PII</option>
          <option value="image">Image</option>
          <option value="video">Video</option>
          <option value="audio">Audio</option>
          <option value="agent">Agent</option>
        </select>
        <br /><br />
        <textarea
          placeholder="Prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          style={{ width: '100%', height: '4rem' }}
        />
        <br /><br />
        <input
          type="number"
          placeholder="Number of Rows"
          value={numRows}
          onChange={(e) => setNumRows(e.target.value)}
        />
        <br /><br />
        <input
          type="text"
          placeholder="Columns (comma separated)"
          value={columns}
          onChange={(e) => setColumns(e.target.value)}
          style={{ width: '100%' }}
        />
        <br /><br />
        <textarea
          placeholder='Examples (JSON array of dicts)'
          value={examples}
          onChange={(e) => setExamples(e.target.value)}
          style={{ width: '100%', height: '6rem' }}
        />
        <br /><br />
        <button type="submit" disabled={loading}>{loading ? 'Generating…' : 'Generate'}</button>
      </form>
      <br />
      {error && <div style={{ color: 'red' }}>Error: {error}</div>}
      {result && (
        <div>
          <h4>Result</h4>
          <div style={{ marginBottom: '0.5rem' }}>
            <button onClick={downloadJSON} style={{ marginRight: '0.5rem' }}>Download JSON</button>
            <button onClick={downloadCSV}>Download CSV</button>
          </div>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default App;
