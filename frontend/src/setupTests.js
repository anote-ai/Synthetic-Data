import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';

// jsdom's test environment doesn't expose these globally, but App.js's SSE
// stream parsing (TextDecoder) and the test suite (TextEncoder) both need them.
if (typeof global.TextEncoder === 'undefined') global.TextEncoder = TextEncoder;
if (typeof global.TextDecoder === 'undefined') global.TextDecoder = TextDecoder;
