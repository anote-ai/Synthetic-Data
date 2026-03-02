import React, { useState } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5000';

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
      const headers = { 'Content-Type': 'application/json' };
      if (apiKey.trim()) headers['Authorization'] = `Bearer ${apiKey.trim()}`;

      let parsedExamples = [];
      if (examples.trim()) {
        try {
          parsedExamples = JSON.parse(examples);
        } catch {
          setError('Examples must be valid JSON array');
          setLoading(false);
          return;
        }
      }

      const response = await axios.post(
        `${API_BASE}/public/generate`,
        {
          task_type: taskType,
          prompt,
          num_rows: Number(numRows),
          columns: columns.split(',').map((col) => col.trim()).filter(Boolean),
          examples: parsedExamples,
        },
        { headers }
      );
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadData = (filename, content, mimeType) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownload = () => {
    if (!result) return;
    const { data } = result;
    const isCsv = typeof data === 'string' && (data.includes(',') || data.includes('\n'));
    const baseName = `anote-generated-${Date.now()}`;
    if (isCsv) {
      downloadData(`${baseName}.csv`, data, 'text/csv;charset=utf-8;');
    } else {
      downloadData(`${baseName}.json`, JSON.stringify(result, null, 2), 'application/json');
    }
  };

  const renderResult = () => {
    if (!result) return null;
    const { data, request_id } = result;
    const isCsv = typeof data === 'string' && (data.includes(',') || data.includes('\n'));

    return (
      <div className="result">
        <div className="result-header">
          {request_id != null && (
            <span className="result-meta">Request ID: {request_id}</span>
          )}
          <button type="button" className="btn btn-download" onClick={handleDownload}>
            Download {isCsv ? 'CSV' : 'JSON'}
          </button>
        </div>
        {isCsv ? (
          <pre className="result-csv">{data}</pre>
        ) : (
          <pre className="result-json">{JSON.stringify(result, null, 2)}</pre>
        )}
      </div>
    );
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Anote Generate</h1>
        <p>Synthetic data generation</p>
      </header>

      <main className="main">
        <form onSubmit={handleSubmit} className="form">
          <label>
            API Key <span className="muted">(optional — auth disabled in dev)</span>
          </label>
          <input
            type="password"
            placeholder="Leave empty for local dev"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="input"
          />

          <label>Task type</label>
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            className="input"
          >
            <option value="text">Text</option>
            <option value="image">Image</option>
            <option value="video">Video</option>
            <option value="audio">Audio</option>
            <option value="agent">Agent</option>
          </select>

          <label>Prompt</label>
          <textarea
            placeholder="e.g. Generate 5 product reviews for a coffee shop"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="input textarea"
            rows={3}
          />

          <label>Number of rows</label>
          <input
            type="number"
            min={1}
            max={100}
            value={numRows}
            onChange={(e) => setNumRows(e.target.value)}
            className="input input-narrow"
          />

          <label>Columns (comma-separated)</label>
          <input
            type="text"
            placeholder="e.g. product, review, rating"
            value={columns}
            onChange={(e) => setColumns(e.target.value)}
            className="input"
          />

          <label>Examples <span className="muted">(optional JSON array)</span></label>
          <textarea
            placeholder='[{"question": "Capital of France?", "answer": "Paris"}]'
            value={examples}
            onChange={(e) => setExamples(e.target.value)}
            className="input textarea"
            rows={2}
          />

          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Generating…' : 'Generate'}
          </button>
        </form>

        {error && (
          <div className="error">
            {error}
          </div>
        )}

        {result && renderResult()}
      </main>
    </div>
  );
}

export default App;
