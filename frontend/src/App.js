import React, { useState, useEffect, useCallback } from 'react';
import exampleDatasets from './exampleDatasets';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';
const ANOTE_PRODUCT_KEY = 'anote_product_api_key';
const ANOTE_PRODUCT_IMPORT_URL = 'https://api.anote.ai/api/import/dataset';

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

// ── Version history API (backed by /public/generate/versions on the server) ───

function buildAnoteImportPayload(rows, context) {
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
      created_at: new Date().toISOString(),
    },
  };
}

async function apiRequest(apiKey, path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || resp.statusText);
  }
  return resp.json();
}

function fetchVersions(apiKey) {
  return apiRequest(apiKey, '/public/generate/versions?limit=50').then(r => r.versions || []);
}

function fetchVersion(apiKey, versionId) {
  return apiRequest(apiKey, `/public/generate/versions/${versionId}`);
}

function renameVersion(apiKey, versionId, name) {
  return apiRequest(apiKey, `/public/generate/versions/${versionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  });
}

function setVersionQuality(apiKey, versionId, quality) {
  return apiRequest(apiKey, `/public/generate/versions/${versionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ quality_score: quality }),
  });
}

function restoreVersion(apiKey, versionId) {
  return apiRequest(apiKey, `/public/generate/versions/${versionId}/restore`, { method: 'POST' });
}

function diffVersions(apiKey, versionIdA, versionIdB) {
  return apiRequest(apiKey, `/public/generate/versions/${versionIdA}/diff?against=${versionIdB}`);
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

function QualityReport({ quality }) {
  if (!quality) return null;

  const { total_rows, unique_rows, duplicates_removed, avg_completeness, lexical_diversity, label_balance } = quality;

  const suggestions = [];
  if (duplicates_removed > 0)
    suggestions.push(`${duplicates_removed} duplicate row${duplicates_removed > 1 ? 's' : ''} detected — use the deduplication export to clean them.`);
  if (avg_completeness < 0.9)
    suggestions.push(`Completeness is ${Math.round(avg_completeness * 100)}% — some rows have empty values.`);
  if (lexical_diversity != null && lexical_diversity < 0.3)
    suggestions.push('Low lexical diversity — generated text may be repetitive. Try a more varied prompt.');
  if (label_balance) {
    for (const [col, counts] of Object.entries(label_balance)) {
      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      const [topVal, topCount] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
      if (topCount / total > 0.6)
        suggestions.push(`"${col}" is imbalanced — "${topVal}" appears in ${Math.round(topCount / total * 100)}% of rows.`);
    }
  }

  const Meter = ({ pct, warn }) => (
    <div style={{ display: 'inline-block', width: 80, height: 6, background: '#e0e0e0', borderRadius: 3, overflow: 'hidden', marginLeft: 6, verticalAlign: 'middle' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: warn ? '#ff9800' : '#4caf50', borderRadius: 3 }} />
    </div>
  );

  const uniquePct = Math.round(unique_rows / total_rows * 100);
  const compPct = Math.round(avg_completeness * 100);
  const divPct = lexical_diversity != null ? Math.round(lexical_diversity * 100) : null;

  return (
    <div style={{ marginTop: 16, padding: '12px 16px', border: '1px solid #e0e0e0', borderRadius: 6, fontSize: 13 }}>
      <div style={{ fontWeight: 600, marginBottom: 10 }}>Quality Report</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        <div>
          <span style={{ color: uniquePct === 100 ? 'green' : '#e67e22' }}>{uniquePct === 100 ? '✓' : '!'}</span>
          {' '}{unique_rows} / {total_rows} unique rows
          {duplicates_removed > 0 && <span style={{ color: '#e67e22', marginLeft: 6 }}>({duplicates_removed} duplicate{duplicates_removed > 1 ? 's' : ''})</span>}
        </div>
        <div>
          <span style={{ color: compPct >= 90 ? 'green' : '#e67e22' }}>{compPct >= 90 ? '✓' : '!'}</span>
          {' '}Completeness: {compPct}%
          <Meter pct={compPct} warn={compPct < 90} />
        </div>
        {divPct != null && (
          <div>
            <span style={{ color: divPct >= 30 ? 'green' : '#e67e22' }}>{divPct >= 30 ? '✓' : '!'}</span>
            {' '}Lexical diversity: {divPct}%
            <Meter pct={divPct} warn={divPct < 30} />
          </div>
        )}
      </div>

      {label_balance && Object.keys(label_balance).length > 0 && (
        <div style={{ marginTop: 12 }}>
          {Object.entries(label_balance).map(([col, counts]) => {
            const total = Object.values(counts).reduce((a, b) => a + b, 0);
            return (
              <div key={col} style={{ marginBottom: 8 }}>
                <div style={{ color: '#555', marginBottom: 4 }}>Distribution: <strong>{col}</strong></div>
                {Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([val, count]) => (
                  <div key={val} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                    <span style={{ width: 110, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#333' }} title={val}>{val}</span>
                    <div style={{ width: 140, height: 12, background: '#e0e0e0', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ width: `${Math.round(count / total * 100)}%`, height: '100%', background: '#1a73e8', borderRadius: 3 }} />
                    </div>
                    <span style={{ color: '#666', minWidth: 48 }}>{count} ({Math.round(count / total * 100)}%)</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}

      {suggestions.length > 0 && (
        <div style={{ marginTop: 10, padding: '8px 10px', background: '#fffbf0', border: '1px solid #ffe58f', borderRadius: 4 }}>
          <div style={{ fontWeight: 600, marginBottom: 4, color: '#8a6d00' }}>Suggestions</div>
          {suggestions.map((s, i) => <div key={i} style={{ color: '#5a4500' }}>• {s}</div>)}
        </div>
      )}
    </div>
  );
}

function DiffPanel({ diff, onClose }) {
  if (!diff) return null;
  const metaEntries = Object.entries(diff.metadata_changes || {});

  return (
    <div style={{ marginTop: 10, padding: '12px 16px', border: '1px solid #c5d3f5', borderRadius: 6, fontSize: 13, background: '#f7f9ff' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <strong>Diff: {diff.version_a.slice(0, 8)} → {diff.version_b.slice(0, 8)}</strong>
        <button onClick={onClose} style={{ fontSize: 11, background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}>✕ Close</button>
      </div>

      {metaEntries.length > 0 ? (
        <div style={{ marginBottom: 10 }}>
          {metaEntries.map(([field, { from, to }]) => (
            <div key={field} style={{ marginBottom: 4 }}>
              <strong>{field}</strong> changed:{' '}
              <span style={{ color: '#c0392b' }}>{JSON.stringify(from)}</span>
              {' → '}
              <span style={{ color: '#27ae60' }}>{JSON.stringify(to)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: '#666', marginBottom: 10 }}>No prompt/column/param changes between these versions.</div>
      )}

      <div style={{ display: 'flex', gap: 16, color: '#444' }}>
        <span>{diff.row_count_a} → {diff.row_count_b} rows</span>
        <span style={{ color: '#27ae60' }}>+{diff.rows_added.length} added</span>
        <span style={{ color: '#c0392b' }}>-{diff.rows_removed.length} removed</span>
        <span>{diff.rows_unchanged} unchanged</span>
      </div>
    </div>
  );
}

function ExampleGallery() {
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 18 }}>
        <div>
          <h2 style={{ margin: 0 }}>Example synthetic datasets</h2>
          <p style={{ margin: '6px 0 0', color: '#555' }}>
            Preview generated dataset schemas, sample rows, prompts, and download-ready CSV files.
          </p>
        </div>
        <a href="/" style={{ fontSize: 13 }}>Generator</a>
      </div>

      <div style={{ display: 'grid', gap: 18 }}>
        {exampleDatasets.map(dataset => {
          const schema = Object.keys(dataset.data[0] || {});
          const previewRows = dataset.data.map(row => ({ ...row, status: 'succeeded' }));
          return (
            <section key={dataset.slug} style={{ border: '1px solid #ddd', borderRadius: 4, padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 18 }}>{dataset.title}</h3>
                  <div style={{ marginTop: 4, color: '#666', fontSize: 13 }}>
                    {dataset.rows.toLocaleString()} rows · {schema.join(', ')}
                  </div>
                </div>
                <button
                  onClick={() => downloadBlob(toCSV(previewRows), `${dataset.slug}.csv`, 'text/csv')}
                  style={{ height: 32 }}
                >
                  Download CSV
                </button>
              </div>

              <div style={{ marginTop: 12, fontSize: 13 }}>
                <strong>Generation prompt:</strong> {dataset.prompt}
              </div>
              <div style={{ marginTop: 6, fontSize: 13, color: '#555' }}>
                <strong>Methodology:</strong> {dataset.methodology}
              </div>

              <ResultTable rows={previewRows} />
            </section>
          );
        })}
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const isExamplesPage = window.location.pathname === '/examples';
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
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [showTemplates, setShowTemplates] = useState(true);
  const [validationErrors, setValidationErrors] = useState({});
  const [quality, setQuality] = useState(null);
  const [classDistribution, setClassDistribution] = useState('');
  const [editingHistoryIdx, setEditingHistoryIdx] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [pendingParent, setPendingParent] = useState(null); // { versionId, name } when re-running a version
  const [diffSelection, setDiffSelection] = useState([]); // up to 2 version_ids
  const [diffResult, setDiffResult] = useState(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [anoteStatus, setAnoteStatus] = useState(null);

  // Reset params and class distribution when task type changes
  useEffect(() => { setParams({}); setClassDistribution(''); }, [taskType]);

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      setHistory(await fetchVersions(apiKey));
    } catch (err) {
      setHistoryError(err.message);
    } finally {
      setHistoryLoading(false);
    }
  }, [apiKey]);

  // Load history on mount, and again whenever the panel is (re)opened
  useEffect(() => { refreshHistory(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (showHistory) refreshHistory(); }, [showHistory, refreshHistory]);

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
    if (classDistribution.trim()) {
      try {
        const dist = JSON.parse(classDistribution);
        const cols = columns.split(',').map(c => c.trim()).filter(Boolean);
        const keys = Object.keys(dist);
        if (keys.length !== 1) errs.classDistribution = 'Must target exactly one column';
        else if (!cols.includes(keys[0])) errs.classDistribution = `Column "${keys[0]}" is not in the columns list`;
      } catch {
        errs.classDistribution = 'Must be valid JSON, e.g. {"label": {"positive": 30, "negative": 70}}';
      }
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
    setQuality(null);
    setAnoteStatus(null);

    const resolvedParams = classDistribution.trim()
      ? { ...params, class_distribution: JSON.parse(classDistribution) }
      : params;

    const body = {
      task_type: taskType,
      prompt,
      num_rows: Number(numRows),
      columns: columns.split(',').map(c => c.trim()).filter(Boolean),
      examples: examples.trim() ? JSON.parse(examples) : [],
      params: resolvedParams,
      ...(pendingParent ? { dataset_name: pendingParent.name, parent_version_id: pendingParent.versionId } : {}),
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
            const versionId = event.version_id;
            setResult({ data, version_id: versionId });
            setPendingParent(null); // this generation consumed the pending chain link
            refreshHistory();
            fetch(`${API_BASE}/public/generate/quality`, {
              method: 'POST',
              headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
              body: JSON.stringify({ data, prompt: body.prompt }),
            }).then(r => r.ok ? r.json() : null).then(r => {
              if (!r) return;
              setQuality(r.quality);
              if (versionId) {
                setVersionQuality(apiKey, versionId, r.quality).then(refreshHistory).catch(() => {});
              }
            }).catch(() => {});
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

  const restoreHistory = useCallback((v) => {
    const p = v.params || {};
    const cd = p.class_distribution;
    setTaskType(v.task_type);
    setPrompt(v.prompt);
    setNumRows(v.num_rows);
    setColumns((v.columns || []).join(','));
    setExamples(v.examples && v.examples.length ? JSON.stringify(v.examples, null, 2) : '');
    setParams({ ...p, class_distribution: undefined });
    setClassDistribution(cd ? JSON.stringify(cd, null, 2) : '');
    setResult(null);
    setQuality(null);
    setError(null);
    // Chains this re-run to v so the next generation becomes v's next version
    setPendingParent({ versionId: v.version_id, name: v.name || '' });
    setShowHistory(false);
  }, []);

  const viewHistory = useCallback(async (v) => {
    try {
      const full = await fetchVersion(apiKey, v.version_id);
      setResult({ data: full.result_data || [], version_id: full.version_id });
      setQuality(full.quality_score || null);
      setShowHistory(false);
    } catch (err) {
      setHistoryError(err.message);
    }
  }, [apiKey]);

  const commitHistoryName = useCallback(async (versionId) => {
    try {
      await renameVersion(apiKey, versionId, editingName.trim());
    } catch (err) {
      setHistoryError(err.message);
    }
    setEditingHistoryIdx(null);
    refreshHistory();
  }, [apiKey, editingName, refreshHistory]);

  const downloadHistoryEntry = useCallback(async (v, format) => {
    try {
      const full = await fetchVersion(apiKey, v.version_id);
      const rows = full.result_data || [];
      if (!rows.length) return;
      const filename = `${v.name || 'dataset'}.${format}`;
      downloadBlob(
        format === 'csv' ? toCSV(rows) : toJSONL(rows),
        filename,
        format === 'csv' ? 'text/csv' : 'application/jsonl'
      );
    } catch (err) {
      setHistoryError(err.message);
    }
  }, [apiKey]);

  const rollbackVersion = useCallback(async (versionId) => {
    try {
      await restoreVersion(apiKey, versionId);
      refreshHistory();
    } catch (err) {
      setHistoryError(err.message);
    }
  }, [apiKey, refreshHistory]);

  const toggleDiffSelect = useCallback((versionId) => {
    setDiffResult(null);
    setDiffSelection(sel => {
      if (sel.includes(versionId)) return sel.filter(id => id !== versionId);
      if (sel.length >= 2) return [sel[1], versionId];
      return [...sel, versionId];
    });
  }, []);

  const runDiff = useCallback(async () => {
    if (diffSelection.length !== 2) return;
    setDiffLoading(true);
    try {
      setDiffResult(await diffVersions(apiKey, diffSelection[0], diffSelection[1]));
    } catch (err) {
      setHistoryError(err.message);
    } finally {
      setDiffLoading(false);
    }
  }, [apiKey, diffSelection]);

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(result?.data || [], null, 2));
    setCopyMsg('Copied!');
    setTimeout(() => setCopyMsg(''), 2000);
  };

  const handleSendToAnote = async () => {
    if (!result?.data?.length) return;

    const storedKey = localStorage.getItem(ANOTE_PRODUCT_KEY) || '';
    const anoteKey = storedKey || window.prompt('Enter your Anote API key from anote.ai/settings');
    if (!anoteKey) {
      setAnoteStatus({ type: 'error', message: 'Enter your Anote API key from anote.ai/settings' });
      return;
    }

    const defaultName = prompt.trim().split(/\s+/).slice(0, 6).join(' ') || 'Synthetic dataset';
    const datasetName = window.prompt('Project name in Anote', defaultName);
    if (!datasetName) return;

    setAnoteStatus({ type: 'loading', message: 'Sending dataset to Anote Product...' });

    try {
      const resp = await fetch(ANOTE_PRODUCT_IMPORT_URL, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${anoteKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(buildAnoteImportPayload(result.data, {
          name: datasetName,
          taskType,
          prompt,
          columns: columns.split(',').map(c => c.trim()).filter(Boolean),
        })),
      });

      const body = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        localStorage.removeItem(ANOTE_PRODUCT_KEY);
        throw new Error(body.error || body.message || 'Enter your Anote API key from anote.ai/settings');
      }

      localStorage.setItem(ANOTE_PRODUCT_KEY, anoteKey);
      const projectUrl = body.project_url || body.url || body.project?.url;
      setAnoteStatus({
        type: 'success',
        message: 'Project created in Anote',
        url: projectUrl,
      });
    } catch (err) {
      setAnoteStatus({ type: 'error', message: err.message || 'Failed to send dataset to Anote Product' });
    }
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

  if (isExamplesPage) {
    return <ExampleGallery />;
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>Anote Synthetic Data Generator</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <a href="/examples" style={{ fontSize: 12 }}>Examples</a>
          <button onClick={() => setShowHistory(h => !h)} style={{ fontSize: 12 }}>
            {showHistory ? 'Hide' : 'Show'} History ({history.length})
          </button>
        </div>
      </div>

      {/* Generation history panel — backed by the server's /public/generate/versions API */}
      {showHistory && (() => {
        // Compute version numbers per named dataset chain (oldest = v1)
        const versionOf = {};
        const counts = {};
        [...history]
          .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
          .forEach(v => {
            const name = v.name || '';
            if (name) { counts[name] = (counts[name] || 0) + 1; versionOf[v.version_id] = counts[name]; }
          });

        return (
          <div style={{ border: '1px solid #ddd', borderRadius: 4, padding: '1rem', marginTop: 12, marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <strong>Generation History</strong>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {diffSelection.length === 2 && (
                  <button
                    onClick={runDiff}
                    disabled={diffLoading}
                    style={{ fontSize: 11, padding: '3px 10px', cursor: diffLoading ? 'wait' : 'pointer' }}
                  >{diffLoading ? 'Comparing…' : 'Compare selected'}</button>
                )}
                <button onClick={refreshHistory} style={{ fontSize: 11, background: 'none', border: 'none', cursor: 'pointer', color: '#1a73e8' }}>
                  ↻ Refresh
                </button>
              </div>
            </div>

            {historyError && <div style={{ color: 'red', fontSize: 12, marginBottom: 8 }}>{historyError}</div>}
            <DiffPanel diff={diffResult} onClose={() => setDiffResult(null)} />
            {historyLoading && <div style={{ color: '#888', fontSize: 13 }}>Loading…</div>}
            {!historyLoading && history.length === 0 && <div style={{ color: '#888', fontSize: 13 }}>No history yet. Run a generation to save it here.</div>}
            {history.map((v) => {
              const name = v.name || '';
              const model = v.params?.model || 'gpt-4o-mini';
              const completeness = v.quality_score ? Math.round(v.quality_score.avg_completeness * 100) : null;
              const vNum = versionOf[v.version_id];
              const label = name ? `${name}${vNum ? ` v${vNum}` : ''}` : null;
              const isEditing = editingHistoryIdx === v.version_id;
              const isSelectedForDiff = diffSelection.includes(v.version_id);

              return (
                <div key={v.version_id} style={{ border: isSelectedForDiff ? '1px solid #1a73e8' : '1px solid #e8e8e8', borderRadius: 6, padding: '10px 12px', marginBottom: 8, background: '#fafafa' }}>
                  {/* Header row: name + timestamp */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input
                        type="checkbox"
                        title="Select to compare with another version"
                        checked={isSelectedForDiff}
                        onChange={() => toggleDiffSelect(v.version_id)}
                      />
                      {isEditing ? (
                        <input
                          autoFocus
                          value={editingName}
                          onChange={e => setEditingName(e.target.value)}
                          onBlur={() => commitHistoryName(v.version_id)}
                          onKeyDown={e => { if (e.key === 'Enter') commitHistoryName(v.version_id); if (e.key === 'Escape') setEditingHistoryIdx(null); }}
                          placeholder="Dataset name…"
                          style={{ fontSize: 13, fontWeight: 600, border: '1px solid #1a73e8', borderRadius: 3, padding: '2px 6px', width: 180 }}
                        />
                      ) : (
                        <span
                          onClick={() => { setEditingHistoryIdx(v.version_id); setEditingName(name); }}
                          title="Click to name this dataset"
                          style={{ fontSize: 13, fontWeight: 600, color: label ? '#1a1a1a' : '#aaa', cursor: 'pointer', borderBottom: '1px dashed #ccc' }}
                        >
                          {label || 'Unnamed — click to name'}
                        </span>
                      )}
                      {v.parent_version_id && (
                        <span style={{ fontSize: 11, color: '#888' }} title={v.parent_version_id}>
                          based on {v.parent_version_id.slice(0, 8)}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: 11, color: '#999', flexShrink: 0, marginLeft: 8 }}>
                      {new Date(v.created_at).toLocaleString()}
                    </span>
                  </div>

                  {/* Meta row */}
                  <div style={{ fontSize: 12, color: '#555', marginBottom: 6 }}>
                    <strong>{v.task_type}</strong>
                    {' · '}{v.row_count ?? v.num_rows} rows
                    {' · '}{model}
                    {completeness !== null && <span style={{ color: completeness >= 90 ? '#2e7d32' : '#e67e22' }}>{' · '}Completeness {completeness}%</span>}
                  </div>

                  {/* Prompt preview */}
                  <div style={{ fontSize: 12, color: '#444', marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.prompt}>
                    "{v.prompt}"
                  </div>

                  {/* Action buttons */}
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button onClick={() => viewHistory(v)} style={{ fontSize: 11, padding: '3px 10px', cursor: 'pointer' }}>View</button>
                    <button onClick={() => restoreHistory(v)} style={{ fontSize: 11, padding: '3px 10px', cursor: 'pointer' }}>Re-run</button>
                    <button onClick={() => rollbackVersion(v.version_id)} title="Restore this version's data as the newest version" style={{ fontSize: 11, padding: '3px 10px', cursor: 'pointer' }}>Restore</button>
                    <button onClick={() => downloadHistoryEntry(v, 'csv')} style={{ fontSize: 11, padding: '3px 10px', cursor: 'pointer' }}>↓ CSV</button>
                    <button onClick={() => downloadHistoryEntry(v, 'jsonl')} style={{ fontSize: 11, padding: '3px 10px', cursor: 'pointer' }}>↓ JSONL</button>
                  </div>
                </div>
              );
            })}
          </div>
        );
      })()}

      {pendingParent && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#fff8e1', border: '1px solid #ffe58f', borderRadius: 4, padding: '6px 12px', marginBottom: 12, fontSize: 12 }}>
          <span>
            Re-running {pendingParent.name ? <strong>{pendingParent.name}</strong> : 'an unnamed dataset'} — the next generation will be saved as its next version.
          </span>
          <button onClick={() => setPendingParent(null)} style={{ fontSize: 11, background: 'none', border: 'none', cursor: 'pointer', color: '#8a6d00' }}>Cancel</button>
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

        {/* Class distribution — text task only */}
        {taskType === 'text' && (
          <div style={{ marginBottom: 12 }}>
            <label htmlFor="classDistribution" style={{ fontSize: 12, color: '#555' }}>
              Class Distribution (optional) — target exact label counts
            </label>
            <textarea
              id="classDistribution"
              placeholder='{"label": {"positive": 30, "negative": 70}}'
              value={classDistribution}
              onChange={e => setClassDistribution(e.target.value)}
              style={{ ...fieldStyle('classDistribution'), height: '3rem', resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }}
            />
            {validationErrors.classDistribution && (
              <div style={{ color: 'red', fontSize: 12, marginBottom: 6 }}>{validationErrors.classDistribution}</div>
            )}
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
              <button onClick={handleSendToAnote} disabled={anoteStatus?.type === 'loading'}>
                {anoteStatus?.type === 'loading' ? 'Sending...' : 'Send to Anote Product →'}
              </button>
              <button onClick={handleCopy}>
                {copyMsg || '⧉ Copy JSON'}
              </button>
            </div>
          </div>
          {anoteStatus && anoteStatus.type !== 'loading' && (
            <div
              style={{
                marginTop: 10,
                padding: '8px 12px',
                borderRadius: 4,
                background: anoteStatus.type === 'success' ? '#f0fff4' : '#fff0f0',
                color: anoteStatus.type === 'success' ? '#176b2c' : '#b00020',
                fontSize: 13,
              }}
            >
              {anoteStatus.message}
              {anoteStatus.url && (
                <>
                  {' '}
                  <a href={anoteStatus.url} target="_blank" rel="noreferrer">Open in Anote →</a>
                </>
              )}
            </div>
          )}
          <ResultTable rows={result.data} />
          <QualityReport quality={quality} />
        </div>
      )}
    </div>
  );
}
