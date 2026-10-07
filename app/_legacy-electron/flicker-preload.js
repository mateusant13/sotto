// Mock process to avoid errors in the oracle's main condition
if (typeof process === 'undefined') {
  global.process = { argv: [] };
}