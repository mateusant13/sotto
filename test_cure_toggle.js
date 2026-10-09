// Test that verifies the cure toggle works correctly
const fs = require('fs');
const path = require('path');

// Import the formulation engine
const { createEngine } = require('./app/panel/caption-formulation.js');

// Test data - simulate fragments that would cause duplication without cure
const testFragments = [
  { text: "Hello", meta: { start: 0, end: 1.5 } },
  { text: "Hello world", meta: { start: 0, end: 3.0 } }, // Same start, longer - should be continuation
  { text: "Hello world how", meta: { start: 0, end: 4.5 } }, // Same start, longer - should be continuation
  { text: "Hello world how are", meta: { start: 0, end: 6.0 } }, // Same start, longer - should be continuation
  { text: "Hello world how are you", meta: { start: 0, end: 7.5 } }, // Same start, longer - should be continuation
];

console.log('Testing cureEnabled: true (with cure)...');
const engineWithCure = createEngine({
  onCommit: (line, reason) => { 
    console.log(`  COMMIT: "${line}" (${reason})`); 
  },
  onProvisional: (committed, provisional) => {
    const committedText = committed.map(t => t.w).join(' ');
    const provisionalText = provisional.map(t => t.w).join(' ');
    console.log(`  PROVISIONAL: "${committedText}" | "${provisionalText}"`);
  },
  cureEnabled: true
});

testFragments.forEach((fragment, index) => {
  console.log(`Fragment ${index + 1}: "${fragment.text}" (start: ${fragment.meta.start}, end: ${fragment.meta.end})`);
  engineWithCure.ingest(fragment.text, fragment.meta);
});

console.log('\nTesting cureEnabled: false (without cure)...');
const engineWithoutCure = createEngine({
  onCommit: (line, reason) => { 
    console.log(`  COMMIT: "${line}" (${reason})`); 
  },
  onProvisional: (committed, provisional) => {
    const committedText = committed.map(t => t.w).join(' ');
    const provisionalText = provisional.map(t => t.w).join(' ');
    console.log(`  PROVISIONAL: "${committedText}" | "${provisionalText}"`);
  },
  cureEnabled: false
});

testFragments.forEach((fragment, index) => {
  console.log(`Fragment ${index + 1}: "${fragment.text}" (start: ${fragment.meta.start}, end: ${fragment.meta.end})`);
  engineWithoutCure.ingest(fragment.text, fragment.meta);
});

console.log('\nTest completed.');