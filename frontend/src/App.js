import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';
const HISTORY_KEY = 'anote_generation_history';
const MAX_HISTORY = 10;

const ROI_TASKS = {
  classification: { label: 'Classification', labelsPerRow: 1, timePerRowMinutes: 0.6 },
  ner: { label: 'NER', labelsPerRow: 4, timePerRowMinutes: 2.5 },
  qa: { label: 'Q&A', labelsPerRow: 2, timePerRowMinutes: 2.0 },
};

const ROI_COMPLEXITY = {
  simple: { label: 'Simple', multiplier: 1 },
  medium: { label: 'Medium', multiplier: 2 },
  complex: { label: 'Complex', multiplier: 4 },
};

const ROI_RATES = {
  crowd: { low: 0.05, high: 0.50 },
  expert: { low: 2.00, high: 10.00 },
  synthetic: { low: 0.003, high: 0.03 },
};

// ── Task-specific param configs ───────────────────────────────────────────────

const TASK_PARAMS = {
  text: [
    { key: 'model', label: 'Model', type: 'select', options: ['gpt-4o-mini', 'gpt-4o', 'gpt-4'] },
    { key: 'batch_size', label: 'Batch Size', type: 'number', default: 5 },
  ],
  image: [
    { key: 'image_size', label: 'Image Size', type: 'select', options: ['1024x1024', '1792x1024', '1024x1792'] },
    { key: 'style', label: 'Style', type: 'select', options: ['vivid', 'natural'] },
    { key: 'run_detection', label: 'Run YOLO Detection', type: 'checkbox' },
  ],
  audio: [
    { key: 'voice', label: 'Voice', type: 'select', options: ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'] },
    { key: 'tts_model', label: 'TTS Model', type: 'select', options: ['tts-1', 'tts-1-hd'] },
    { key: 'speed', label: 'Speed', type: 'number', default: 1.0, min: 0.25, max: 4.0, step: 0.25 },
  ],
  video: [
    { key: 'fps', label: 'FPS', type: 'number', default: 6, min: 1, max: 60 },
    { key: 'resolution', label: 'Resolution', type: 'select', options: ['576x320', '1280x720', '1920x1080'] },
    { key: 'duration', label: 'Duration (s)', type: 'number', default: 4, min: 1, max: 30 },
    { key: 'annotate_frames', label: 'Annotate Frames (GPT-4o)', type: 'checkbox' },
  ],
  agent: [
    { key: 'difficulty', label: 'Difficulty', type: 'select', options: ['easy', 'medium', 'hard'] },
  ],
  pii: [
    { key: 'locale', label: 'Locale', type: 'select', options: ['en_US', 'en_GB', 'de_DE', 'fr_FR', 'ja_JP'] },
  ],
  language: [
    { key: 'language', label: 'Target Language', type: 'select', options: ['English', 'Japanese', 'Spanish', 'French', 'German', 'Chinese', 'Korean'] },
    { key: 'model', label: 'Model', type: 'select', options: ['gpt-4o-mini', 'gpt-4o'] },
  ],
  tabular: [
    { key: 'model', label: 'Model', type: 'select', options: ['gpt-4o-mini', 'gpt-4o'] },
  ],
  code: [
    { key: 'code_type', label: 'Code Type', type: 'select', options: ['function', 'unittest', 'bugfix', 'review', 'docstring'] },
    { key: 'language', label: 'Language', type: 'select', options: ['python', 'javascript', 'typescript', 'go', 'rust', 'java', 'cpp', 'sql'] },
  ],
};

// ── Prompt templates ──────────────────────────────────────────────────────────

const TEMPLATES = [
  { id: 'sentiment',      taskType: 'text', title: 'Sentiment Analysis',      columns: 'text,label',          prompt: 'Generate customer reviews with positive, negative, and neutral sentiment about a SaaS product' },
  { id: 'support-intent', taskType: 'text', title: 'Support Ticket Intent',   columns: 'ticket_text,category', prompt: 'Generate customer support tickets classified by intent: billing, technical issue, feature request, account access' },
  { id: 'email-priority', taskType: 'text', title: 'Email Priority',          columns: 'email_text,priority',  prompt: 'Generate work emails classified as urgent, normal, or low priority' },
  { id: 'product-faq',    taskType: 'text', title: 'Product FAQ',             columns: 'question,answer',      prompt: "Generate Q&A pairs about a B2B SaaS product's features and pricing" },
  { id: 'tech-qa',        taskType: 'text', title: 'Technical Q&A',           columns: 'question,answer',      prompt: 'Generate Q&A pairs a developer might ask about a REST API' },
  { id: 'medical-ner',    taskType: 'text', title: 'Medical Records (NER)',   columns: 'clinical_note,entities', prompt: 'Generate clinical notes containing patient names, medications, dosages, and diagnoses for NER training' },
  { id: 'financial-ner',  taskType: 'text', title: 'Financial News (NER)',    columns: 'sentence,entities',    prompt: 'Generate financial news sentences containing company names, dollar amounts, and dates' },
  { id: 'legal-ner',      taskType: 'text', title: 'Legal Contracts (NER)',   columns: 'clause,entities',      prompt: 'Generate contract clauses containing party names, dates, and obligation types' },
  { id: 'pii-test',       taskType: 'pii',  title: 'PII Test Data',           columns: 'text,pii_types',       prompt: 'Generate realistic but fake records containing names, emails, phone numbers, and addresses for testing redaction pipelines' },
];

// ── Utilities ─────────────────────────────────────────────────────────────────

function toCSV(rows) {
  if (!rows.length) return '';
  const cols = Object.keys(rows[0]).filter(k => k !== 'status');
  const header = cols.join(',');
  const lines = rows.map(row =>
    cols.map(c => {
      const v = row[c] ?? '';
      const s = String(v).replace(/"/g, '""');
      return /[",\n]/.test(s) ? `"${s}"` : s;
    }).join(',')
  );
  return [header, ...lines].join('\n');
}

function toJSONL(rows) {
  return rows.map(r => JSON.stringify(r)).join('\n');
}

function downloadBlob(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); }
  catch { return []; }
}

function saveHistory(entry) {
  const hist = loadHistory();
  hist.unshift(entry);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(hist.slice(0, MAX_HISTORY)));
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TemplateSelector({ onSelect }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
      {TEMPLATES.map(t => (
        <button
          key={t.id}
          type="button"
          onClick={() => onSelect(t)}
          title={t.prompt}
          style={{ padding: '3px 10px', fontSize: 12, background: '#f0f4ff', border: '1px solid #c5d3f5', borderRadius: 12, cursor: 'pointer', whiteSpace: 'nowrap' }}
        >
          {t.title}
        </button>
      ))}
    </div>
  );
}

function ParamField({ spec, value, onChange }) {
  const id = `param-${spec.key}`;
  const common = { id, style: { marginLeft: 8 } };

  if (spec.type === 'checkbox') {
    return (
      <label htmlFor={id} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <input type="checkbox" {...common} checked={!!value} onChange={e => onChange(e.target.checked)} />
        {spec.label}
      </label>
    );
  }
  if (spec.type === 'select') {
    return (
      <label htmlFor={id}>
        {spec.label}
        <select {...common} value={value ?? spec.options[0]} onChange={e => onChange(e.target.value)}>
          {spec.options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </label>
    );
  }
  return (
    <label htmlFor={id}>
      {spec.label}
      <input
        type="number" {...common}
        value={value ?? spec.default ?? ''}
        min={spec.min} max={spec.max} step={spec.step}
        onChange={e => onChange(e.target.value)}
        style={{ width: 70, marginLeft: 8 }}
      />
    </label>
  );
}

function ResultTable({ rows }) {
  const [page, setPage] = useState(0);
  const [sortCol, setSortCol] = useState(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [expanded, setExpanded] = useState({});
  const PAGE_SIZE = 20;

  const cols = rows.length ? Object.keys(rows[0]).filter(k => k !== 'status') : [];

  const sorted = sortCol
    ? [...rows].sort((a, b) => {
        const av = String(a[sortCol] ?? ''), bv = String(b[sortCol] ?? '');
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      })
    : rows;

  const pageRows = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(rows.length / PAGE_SIZE);

  const handleSort = col => {
    if (sortCol === col) setSortAsc(a => !a);
    else { setSortCol(col); setSortAsc(true); }
  };

  const cellStyle = (row, col) => ({
    padding: '4px 8px',
    maxWidth: 200,
    overflow: 'hidden',
    whiteSpace: expanded[`${rows.indexOf(row)}-${col}`] ? 'normal' : 'nowrap',
    textOverflow: 'ellipsis',
    cursor: 'pointer',
    background: row.status === 'failed' ? '#fff0f0' : undefined,
    borderBottom: '1px solid #eee',
  });

  const toggleExpand = (rowIdx, col) => {
    setExpanded(e => ({ ...e, [`${rowIdx}-${col}`]: !e[`${rowIdx}-${col}`] }));
  };

  const renderCell = (row, col, rowIdx) => {
    const val = row[col];
    if (typeof val === 'string' && val.startsWith('data:image/')) {
      return <img src={val} alt={col} style={{ maxHeight: 80 }} />;
    }
    if (typeof val === 'string' && val.startsWith('data:audio/')) {
      return <audio controls src={val} style={{ height: 32 }} />;
    }
    if (typeof val === 'string' && val.startsWith('data:video/')) {
      return <video controls src={val} style={{ maxHeight: 80 }} />;
    }
    return (
      <span onClick={() => toggleExpand(rowIdx, col)} title="Click to expand">
        {typeof val === 'object' ? JSON.stringify(val) : String(val ?? '')}
      </span>
    );
  };

  return (
    <div style={{ overflowX: 'auto', marginTop: 12 }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>
        <thead>
          <tr>
            {cols.map(c => (
              <th
                key={c}
                onClick={() => handleSort(c)}
                style={{ padding: '6px 8px', background: '#f5f5f5', cursor: 'pointer', textAlign: 'left', borderBottom: '2px solid #ddd', whiteSpace: 'nowrap' }}
              >
                {c} {sortCol === c ? (sortAsc ? '↑' : '↓') : ''}
              </th>
            ))}
            <th style={{ padding: '6px 8px', background: '#f5f5f5', borderBottom: '2px solid #ddd' }}>status</th>
          </tr>
        </thead>
        <tbody>
          {pageRows.map((row, i) => (
            <tr key={i}>
              {cols.map(col => (
                <td key={col} style={cellStyle(row, col)} >
                  {renderCell(row, col, page * PAGE_SIZE + i)}
                </td>
              ))}
              <td style={{ padding: '4px 8px', borderBottom: '1px solid #eee', color: row.status === 'failed' ? 'red' : 'green' }}>
                {row.status}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
          <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>‹ Prev</button>
          <span>Page {page + 1} / {totalPages}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next ›</button>
        </div>
      )}
    </div>
  );
}

function formatUSD(value) {
  return value < 100
    ? value.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
    : value.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

function formatRange(low, high) {
  return low === high ? formatUSD(low) : `${formatUSD(low)} - ${formatUSD(high)}`;
}

function formatManualTime(minutes) {
  const days = Math.max(1, Math.ceil(minutes / (60 * 6)));
  if (days < 10) return `${days} business day${days === 1 ? '' : 's'}`;
  const weeks = Math.ceil(days / 5);
  if (weeks < 8) return `${weeks} week${weeks === 1 ? '' : 's'}`;
  return `${Math.ceil(weeks / 4)} month${weeks < 8 ? '' : 's'}`;
}

function RoiCalculator({ defaultRows }) {
  const [rows, setRows] = useState(defaultRows || 1000);
  const [task, setTask] = useState('classification');
  const [complexity, setComplexity] = useState('medium');
  const [showMethodology, setShowMethodology] = useState(false);

  const safeRows = Math.max(1, Number(rows) || 1);
  const taskSpec = ROI_TASKS[task];
  const complexitySpec = ROI_COMPLEXITY[complexity];
  const labelUnits = safeRows * taskSpec.labelsPerRow * complexitySpec.multiplier;
  const manualMinutes = safeRows * taskSpec.timePerRowMinutes * complexitySpec.multiplier;
  const syntheticCostLow = safeRows * ROI_RATES.synthetic.low;
  const syntheticCostHigh = safeRows * ROI_RATES.synthetic.high;

  const estimates = [
    {
      approach: 'Manual labeling (crowd)',
      cost: formatRange(labelUnits * ROI_RATES.crowd.low, labelUnits * ROI_RATES.crowd.high),
      time: formatManualTime(manualMinutes),
    },
    {
      approach: 'Expert labeling (agency)',
      cost: formatRange(labelUnits * ROI_RATES.expert.low, labelUnits * ROI_RATES.expert.high),
      time: formatManualTime(manualMinutes * 2.5),
    },
    {
      approach: 'Anote Synthetic Data',
      cost: formatRange(syntheticCostLow, syntheticCostHigh),
      time: '~5 minutes',
    },
  ];

  return (
    <section style={{ marginTop: 18, padding: '14px 16px', border: '1px solid #ddd', borderRadius: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16 }}>ROI calculator</h3>
          <div style={{ color: '#666', fontSize: 13, marginTop: 4 }}>Estimate manual labeling cost vs synthetic generation.</div>
        </div>
        <button type="button" onClick={() => setShowMethodology(v => !v)} style={{ fontSize: 12 }}>
          {showMethodology ? 'Hide' : 'Show'} methodology
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginTop: 14 }}>
        <label style={{ fontSize: 12, color: '#555' }}>
          Rows needed
          <input
            type="number"
            min={1}
            value={rows}
            onChange={e => setRows(e.target.value)}
            style={{ width: '100%', marginTop: 4, padding: '6px 8px', boxSizing: 'border-box' }}
          />
        </label>
        <label style={{ fontSize: 12, color: '#555' }}>
          Task type
          <select value={task} onChange={e => setTask(e.target.value)} style={{ width: '100%', marginTop: 4, padding: '6px 8px' }}>
            {Object.entries(ROI_TASKS).map(([key, spec]) => <option key={key} value={key}>{spec.label}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: '#555' }}>
          Labeling complexity
          <select value={complexity} onChange={e => setComplexity(e.target.value)} style={{ width: '100%', marginTop: 4, padding: '6px 8px' }}>
            {Object.entries(ROI_COMPLEXITY).map(([key, spec]) => <option key={key} value={key}>{spec.label}</option>)}
          </select>
        </label>
      </div>

      <div style={{ overflowX: 'auto', marginTop: 14 }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: '6px 8px', background: '#f5f5f5' }}>Approach</th>
              <th style={{ textAlign: 'left', padding: '6px 8px', background: '#f5f5f5' }}>Cost</th>
              <th style={{ textAlign: 'left', padding: '6px 8px', background: '#f5f5f5' }}>Time</th>
            </tr>
          </thead>
          <tbody>
            {estimates.map(row => (
              <tr key={row.approach}>
                <td style={{ padding: '7px 8px', borderBottom: '1px solid #eee' }}>{row.approach}</td>
                <td style={{ padding: '7px 8px', borderBottom: '1px solid #eee' }}>{row.cost}</td>
                <td style={{ padding: '7px 8px', borderBottom: '1px solid #eee' }}>{row.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showMethodology && (
        <div style={{ marginTop: 10, color: '#666', fontSize: 12, lineHeight: 1.5 }}>
          Uses {taskSpec.labelsPerRow} label unit{taskSpec.labelsPerRow === 1 ? '' : 's'} per row for {taskSpec.label.toLowerCase()}
          {' '}and a {complexitySpec.multiplier}x complexity multiplier. Crowd labeling is estimated at $0.05-$0.50 per label,
          expert labeling at $2-$10 per label, and synthetic generation at $0.003-$0.03 per row. These defaults are editable in code as market rates change.
        </div>
      )}
    </section>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [apiKey, setApiKey] = useState('');
  const [taskType, setTaskType] = useState('text');
  const [prompt, setPrompt] = useState('');
  const [numRows, setNumRows] = useState(5);
  const [columns, setColumns] = useState('question,answer');
  const [examples, setExamples] = useState('');
  const [params, setParams] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [streamProgress, setStreamProgress] = useState(null);
  const [copyMsg, setCopyMsg] = useState('');
  const [history, setHistory] = useState(loadHistory);
  const [showHistory, setShowHistory] = useState(false);
  const [showTemplates, setShowTemplates] = useState(true);
  const [validationErrors, setValidationErrors] = useState({});

  // Reset params when task type changes
  useEffect(() => { setParams({}); }, [taskType]);

  const applyTemplate = useCallback((t) => {
    setTaskType(t.taskType);
    setPrompt(t.prompt);
    setColumns(t.columns);
    setShowTemplates(false);
  }, []);

  const setParam = useCallback((key, val) => {
    setParams(p => ({ ...p, [key]: val }));
  }, []);

  const validate = () => {
    const errs = {};
    if (!prompt.trim()) errs.prompt = 'Prompt is required';
    const cols = columns.split(',').map(c => c.trim()).filter(Boolean);
    if (!cols.length) errs.columns = 'At least one column required';
    if (!Number.isInteger(Number(numRows)) || numRows < 1 || numRows > 100)
      errs.numRows = 'Must be 1–100';
    if (examples.trim()) {
      try { JSON.parse(examples); }
      catch { errs.examples = 'Must be valid JSON array'; }
    }
    return errs;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    setValidationErrors(errs);
    if (Object.keys(errs).length) return;

    setResult(null);
    setError(null);
    setLoading(true);
    setStreamProgress(null);

    const body = {
      task_type: taskType,
      prompt,
      num_rows: Number(numRows),
      columns: columns.split(',').map(c => c.trim()).filter(Boolean),
      examples: examples.trim() ? JSON.parse(examples) : [],
      params,
    };

    try {
      const resp = await fetch(`${API_BASE}/public/generate/stream`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(err.error || resp.statusText);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const accumulatedRows = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let event;
          try { event = JSON.parse(line.slice(6)); } catch { continue; }

          if (event.type === 'progress') {
            accumulatedRows.push(event.data);
            setStreamProgress({ completed: event.row + 1, total: event.total });
          } else if (event.type === 'done') {
            const data = event.data && event.data.length ? event.data : accumulatedRows;
            setResult({ data });
            saveHistory({ ts: new Date().toISOString(), task_type: taskType, num_rows: Number(numRows), preview: columns.split(',')[0].trim(), body });
            setHistory(loadHistory());
            return;
          } else if (event.type === 'error') {
            throw new Error(event.message);
          }
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setStreamProgress(null);
    }
  };

  const restoreHistory = (entry) => {
    setTaskType(entry.body.task_type);
    setPrompt(entry.body.prompt);
    setNumRows(entry.body.num_rows);
    setColumns(entry.body.columns.join(','));
    setExamples(entry.body.examples.length ? JSON.stringify(entry.body.examples, null, 2) : '');
    setParams(entry.body.params || {});
    setShowHistory(false);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(result?.data || [], null, 2));
    setCopyMsg('Copied!');
    setTimeout(() => setCopyMsg(''), 2000);
  };

  const fieldStyle = (key) => ({
    width: '100%',
    padding: '6px 8px',
    marginBottom: validationErrors[key] ? 2 : 8,
    borderColor: validationErrors[key] ? 'red' : '#ccc',
    borderWidth: 1,
    borderStyle: 'solid',
    borderRadius: 4,
    boxSizing: 'border-box',
  });

  const paramSpecs = TASK_PARAMS[taskType] || [];

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>Anote Synthetic Data Generator</h2>
        <button onClick={() => setShowHistory(h => !h)} style={{ fontSize: 12 }}>
          {showHistory ? 'Hide' : 'Show'} History ({history.length})
        </button>
      </div>

      {/* Generation history panel */}
      {showHistory && (
        <div style={{ border: '1px solid #ddd', borderRadius: 4, padding: '1rem', marginTop: 12, marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <strong>Recent generations</strong>
            <button
              onClick={() => { localStorage.removeItem(HISTORY_KEY); setHistory([]); }}
              style={{ fontSize: 11, color: 'red' }}
            >Clear</button>
          </div>
          {history.length === 0 && <div style={{ color: '#888', fontSize: 13 }}>No history yet.</div>}
          {history.map((h, i) => (
            <div
              key={i}
              onClick={() => restoreHistory(h)}
              style={{ cursor: 'pointer', padding: '6px 8px', borderRadius: 4, marginBottom: 4, background: '#f9f9f9', fontSize: 13 }}
            >
              <strong>{h.task_type}</strong> · {h.num_rows} rows · {h.preview} column ·{' '}
              <span style={{ color: '#888' }}>{new Date(h.ts).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ marginTop: 16 }}>
        {/* API Key */}
        <label htmlFor="apiKey" style={{ fontSize: 12, color: '#555' }}>API Key</label>
        <input
          id="apiKey"
          type="password"
          placeholder="Bearer token"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          style={fieldStyle('apiKey')}
        />

        {/* Task type */}
        <label htmlFor="taskType" style={{ fontSize: 12, color: '#555' }}>Task Type</label>
        <select
          id="taskType"
          value={taskType}
          onChange={e => setTaskType(e.target.value)}
          style={{ ...fieldStyle('taskType'), display: 'block' }}
        >
          {['text','image','video','audio','agent','pii','language','tabular','code'].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        {/* Prompt */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
          <label htmlFor="prompt" style={{ fontSize: 12, color: '#555' }}>Prompt</label>
          <button type="button" onClick={() => setShowTemplates(s => !s)} style={{ fontSize: 11, color: '#1a73e8', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
            {showTemplates ? 'Hide templates' : 'Templates'}
          </button>
        </div>
        {showTemplates && <TemplateSelector onSelect={applyTemplate} />}
        <textarea
          id="prompt"
          placeholder="Describe the dataset you want to generate"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          style={{ ...fieldStyle('prompt'), height: '4rem', resize: 'vertical' }}
        />
        {validationErrors.prompt && <div style={{ color: 'red', fontSize: 12, marginBottom: 6 }}>{validationErrors.prompt}</div>}

        {/* Columns + num_rows */}
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 3 }}>
            <label htmlFor="columns" style={{ fontSize: 12, color: '#555' }}>Columns (comma-separated)</label>
            <input
              id="columns"
              type="text"
              placeholder="question,answer"
              value={columns}
              onChange={e => setColumns(e.target.value)}
              style={fieldStyle('columns')}
            />
            {validationErrors.columns && <div style={{ color: 'red', fontSize: 12, marginBottom: 6 }}>{validationErrors.columns}</div>}
          </div>
          <div style={{ flex: 1 }}>
            <label htmlFor="numRows" style={{ fontSize: 12, color: '#555' }}>Rows (1–100)</label>
            <input
              id="numRows"
              type="number"
              min={1} max={100}
              value={numRows}
              onChange={e => setNumRows(e.target.value)}
              style={fieldStyle('numRows')}
            />
            {validationErrors.numRows && <div style={{ color: 'red', fontSize: 12, marginBottom: 6 }}>{validationErrors.numRows}</div>}
          </div>
        </div>

        {/* Examples */}
        <label htmlFor="examples" style={{ fontSize: 12, color: '#555' }}>Examples (JSON array, optional)</label>
        <textarea
          id="examples"
          placeholder='[{"question": "What is Python?", "answer": "A programming language"}]'
          value={examples}
          onChange={e => setExamples(e.target.value)}
          style={{ ...fieldStyle('examples'), height: '5rem', resize: 'vertical' }}
        />
        {validationErrors.examples && <div style={{ color: 'red', fontSize: 12, marginBottom: 6 }}>{validationErrors.examples}</div>}

        {/* Task-specific params */}
        {paramSpecs.length > 0 && (
          <div style={{ background: '#f8f8f8', border: '1px solid #eee', borderRadius: 4, padding: '12px 16px', marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: '#555', marginBottom: 8 }}>
              <strong>{taskType}</strong> options
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
              {paramSpecs.map(spec => (
                <ParamField key={spec.key} spec={spec} value={params[spec.key]} onChange={v => setParam(spec.key, v)} />
              ))}
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{ padding: '8px 24px', background: loading ? '#aaa' : '#1a73e8', color: '#fff', border: 'none', borderRadius: 4, cursor: loading ? 'not-allowed' : 'pointer', fontSize: 15 }}
        >
          {loading ? 'Generating…' : 'Generate'}
        </button>
      </form>

      <RoiCalculator defaultRows={Number(numRows) || 1000} />

      {loading && (
        <div style={{ marginTop: 16 }}>
          {streamProgress ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#555', marginBottom: 4 }}>
                <span>Generating… {streamProgress.completed} / {streamProgress.total} rows</span>
                <span>{Math.round((streamProgress.completed / streamProgress.total) * 100)}%</span>
              </div>
              <div style={{ height: 8, background: '#e0e0e0', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  width: `${(streamProgress.completed / streamProgress.total) * 100}%`,
                  background: '#1a73e8',
                  borderRadius: 4,
                  transition: 'width 0.2s ease',
                }} />
              </div>
            </>
          ) : (
            <div style={{ color: '#555', fontSize: 13 }}>⏳ Connecting…</div>
          )}
        </div>
      )}

      {error && (
        <div style={{ marginTop: 16, color: 'red', background: '#fff0f0', padding: '8px 12px', borderRadius: 4 }}>
          Error: {error}
        </div>
      )}

      {result && result.data && (
        <div style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ margin: 0 }}>
              Results — {result.data.length} rows
              {result.version_id && <span style={{ fontSize: 12, color: '#888', marginLeft: 8 }}>v:{result.version_id.slice(0, 8)}</span>}
            </h4>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => downloadBlob(toCSV(result.data), 'synthetic_data.csv', 'text/csv')}>
                ↓ CSV
              </button>
              <button onClick={() => downloadBlob(toJSONL(result.data), 'synthetic_data.jsonl', 'application/jsonl')}>
                ↓ JSONL
              </button>
              <button onClick={handleCopy}>
                {copyMsg || '⧉ Copy JSON'}
              </button>
            </div>
          </div>
          <ResultTable rows={result.data} />
        </div>
      )}
    </div>
  );
}
