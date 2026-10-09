// Test that specifically checks the cure functionality for preventing duplicates
const fs = require('fs');
const path = require('path');

// Import the formulation engine
const { createEngine } = require('./app/panel/caption-formulation.js');

// Simulate the scenario from the issue: 
// Worker sends LINE with same start but increasing end (cumulative fragments)
// Renderer's hold deadline can fire while worker is still holding the line
// This causes the emitted prefix and continuation to both end up in history
// Without cure: duplicate lines
// With cure: only one line

console.log('=== Testing the specific duplication scenario ===');

// Simulate fragments from the same line with same start but growing end
const lineFragments = [
  { text: "Hello", meta: { start: 10.0, end: 12.0 } },
  { text: "Hello world", meta: { start: 10.0, end: 14.0 } },
  { text: "Hello world how", meta: { start: 10.0, end: 16.0 } },
  { text: "Hello world how are", meta: { start: 10.0, end: 18.0 } },
  { text: "Hello world how are you", meta: { start: 10.0, end: 20.0 } },
];

// Simulate a hold timeout occurring after the third fragment
// This would cause a commit of the current state

function testScenario(cureEnabled, label) {
  console.log(`\n--- ${label} (cureEnabled: ${cureEnabled}) ---`);
  
  let committedLines = [];
  
  const engine = createEngine({
    onCommit: (line, reason) => {
      committedLines.push(line);
      console.log(`  COMMIT ["${line}"] (${reason})`);
    },
    onProvisional: (committed, provisional) => {
      const committedText = committed.map(t => t.w).join(' ');
      const provisionalText = provisional.map(t => t.w).join(' ');
      console.log(`  PROVISIONAL: "${committedText}" | "${provisionalText}"`);
    },
    cureEnabled: cureEnabled
  });

  // Process fragments
  lineFragments.forEach((fragment, index) => {
    console.log(`Fragment ${index + 1}: "${fragment.text}"`);
    engine.ingest(fragment.text, fragment.meta);
    
    // Simulate hold timeout after 3rd fragment (index 2)
    if (index === 2) {
      console.log('  -> Simulating hold timeout...');
      const heldLine = engine.expireHold();
      if (heldLine) {
        committedLines.push(heldLine);
        console.log(`  COMMIT from hold ["${heldLine}"] (hold-timeout)`);
      }
    }
  });
  
  // Final flush
  console.log('  -> Final flush...');
  const finalLine = engine.flush('final');
  if (finalLine) {
    committedLines.push(finalLine);
    console.log(`  COMMIT from flush ["${finalLine}"] (final)`);
  }
  
  console.log(`  Final committed lines (${committedLines.length}):`);
  committedLines.forEach((line, i) => {
    console.log(`    ${i + 1}: "${line}"`);
  });
  
  // Check for duplicates
  const uniqueLines = [...new Set(committedLines)];
  if (uniqueLines.length === committedLines.length) {
    console.log(`  ✓ No duplicates found`);
  } else {
    console.log(`  ✗ Duplicates found! ${committedLines.length} total, ${uniqueLines.length} unique`);
  }
  
  return committedLines;
}

// Test both scenarios
const linesWithCure = testScenario(true, 'WITH CURE');
const linesWithoutCure = testScenario(false, 'WITHOUT CURE');

console.log(`\n=== SUMMARY ===`);
console.log(`With cure: ${linesWithCure.length} lines committed`);
console.log(`Without cure: ${linesWithoutCure.length} lines committed`);

if (linesWithoutCure.length > linesWithCure.length) {
  console.log(`✓ Cure prevented ${linesWithoutCure.length - linesWithCure.length} duplicate line(s)`);
} else if (linesWithoutCure.length < linesWithCure.length) {
  console.log(`? Unexpected: cure resulted in more lines`);
} else {
  console.log(`= Same number of lines with and without cure`);
}