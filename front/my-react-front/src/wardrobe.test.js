/* global process */
import { groupItems, errorMessage } from './wardrobe.js';
const expect = (value, expected) => { if (JSON.stringify(value) !== JSON.stringify(expected)) throw new Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(value)}`); };
const items = [
  { category: 'bottom', rank: 1 },
  { category: 'top', rank: 4, created_at: '2026-10-01' },
  { category: 'outerwear', rank: 3 },
  { category: 'top', rank: 2, created_at: '2026-10-03' },
  { category: 'future-label', rank: 5 },
  { rank: 6 },
];
expect(groupItems(items).map(([key]) => key), ['outerwear', 'top', 'bottom', '미분류', 'future-label']);
expect(groupItems(items, 'top', true)[0][1].map((item) => item.rank), [2, 4]);
expect(groupItems(items, 'top')[0][1].map((item) => item.created_at), ['2026-10-03', '2026-10-01']);
expect(groupItems(items, 'headwear'), []);
expect(groupItems([], 'all'), []);
expect(items.map((item) => item.rank), [1, 4, 3, 2, 5, 6]);
expect(errorMessage({ response: { data: { detail: [{ msg: 'ID required' }] } } }), 'ID required');
process.stdout.write('PASS: label ordering, recommendation ranks, dates, missing/unknown labels, filtering, immutability, validation errors\n');
