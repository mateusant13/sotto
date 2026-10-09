const engineWithCure = require('./app/_legacy-electron/caption-formulation_modified.js').createEngine({
  onCommit: (line, reason) => { console.log(`COMMIT: "${line}" (${reason})`); },
  onProvisional: (committed, provisional) => {},
  cureEnabled: true
});

const engineWithoutCure = require('./app/_legacy-electron/caption-formulation_modified.js').createEngine({
  onCommit: (line, reason) => { console.log(`COMMIT (no cure): "${line}" (${reason})`); },
  onProvisional: (committed, provisional) => {},
  cureEnabled: false
});

console.log('Engines created successfully');
// Test that they have the expected properties
console.log('With cure:', typeof engineWithCure.ingest === 'function');
console.log('Without cure:', typeof engineWithoutCure.ingest === 'function');
