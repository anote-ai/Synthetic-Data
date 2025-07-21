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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setResult(null);
    setError(null);
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
            Authorization: `Bearer ${apiKey}`,
          },
        }
      );
      setResult(response.data);
    } catch (err) {
      console.error(err);
      setError(err.message);
    }
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
      <h2>Anote Generate (Frontend)</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="API Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          required
          style={{ width: '100%', marginBottom: '1rem' }}
        />
        <select value={taskType} onChange={(e) => setTaskType(e.target.value)}>
          <option value="text">Text</option>
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
        <button type="submit">Generate</button>
      </form>
      <br />
      {error && <div style={{ color: 'red' }}>Error: {error}</div>}
      {result && (
        <div>
          <h4>Result:</h4>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default App;
