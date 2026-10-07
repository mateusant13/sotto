#!/usr/bin/env node

/**
 * Flicker DOM Oracle - Counts DOM mutations in the Sotto panel.
 * 
 * Usage:
 *   node flicker-dom-oracle.js [seconds]   - Run for N seconds (default 5)
 *   node flicker-dom-oracle.js --selftest  - Run self test
 */

const fs = require('fs');

function runNormalMode(seconds = 5) {
    // Determine the panel to observe
    let panel = document.querySelector('#sotto-panel');
    if (!panel) {
        console.warn('Panel with id "sotto-panel" not found, falling back to document.body');
        panel = document.body;
    }

    // Counters
    let liAddedRemoved = 0;
    let textContentChanged = 0;
    let classChanged = 0;

    // Mutation observer
    const observer = new MutationObserver(mutations => {
        for (const mutation of mutations) {
            if (mutation.type === 'childList') {
                for (const node of mutation.addedNodes) {
                    if (node.nodeName === 'LI') liAddedRemoved++;
                }
                for (const node of mutation.removedNodes) {
                    if (node.nodeName === 'LI') liAddedRemoved++;
                }
            } else if (mutation.type === 'characterData') {
                // Check if the changed text node is inside an <li>
                if (mutation.target.parentNode && mutation.target.parentNode.nodeName === 'LI') {
                    textContentChanged++;
                }
            } else if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                classChanged++;
            }
        }
    });

    // Start observing
    observer.observe(panel, {
        childList: true,
        characterData: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
    });

    // Stop after N seconds
    setTimeout(() => {
        observer.disconnect();
        console.log(`Li added/removed: ${liAddedRemoved}`);
        console.log(`Text content changed: ${textContentChanged}`);
        console.log(`Class changed: ${classChanged}`);
        console.log(`Total: ${liAddedRemoved + textContentChanged + classChanged}`);
        process.exit(0);
    }, seconds * 1000);
}

function runSelfTest() {
    // Check if jsdom is available
    let jsdom;
    try {
        jsdom = require('jsdom');
    } catch (e) {
        console.error('Self test requires jsdom. Please install it: npm install jsdom');
        process.exit(1);
    }

    const { JSDOM } = jsdom;
    const dom = new JSDOM(`<!DOCTYPE html><div id="sotto-panel"><ul><li>Item 1</li><li>Item 2</li></ul></div>`);
    global.window = dom.window;
    global.document = dom.window.document;
    global.MutationObserver = dom.window.MutationObserver;

    // Create the observer and store the counts in variables that we can access by using an object.
    const counts = { liAddedRemoved: 0, textContentChanged: 0, classChanged: 0 };
    const panel = document.querySelector('#sotto-panel');
    const observer = new MutationObserver(mutations => {
        for (const mutation of mutations) {
            console.log('Mutation:', mutation);
            if (mutation.type === 'childList') {
                for (const node of mutation.addedNodes) {
                    if (node.nodeName === 'LI') {
                        counts.liAddedRemoved++;
                        console.log('  Added LI');
                    }
                    if (node.nodeType === dom.window.Node.TEXT_NODE && node.parentNode && node.parentNode.nodeName === 'LI') {
                        counts.textContentChanged++;
                        console.log('  Added text node under LI');
                    }
                }
                for (const node of mutation.removedNodes) {
                    if (node.nodeName === 'LI') {
                        counts.liAddedRemoved++;
                        console.log('  Removed LI');
                    }
                    if (node.nodeType === dom.window.Node.TEXT_NODE && node.parentNode && node.parentNode.nodeName === 'LI') {
                        counts.textContentChanged++;
                        console.log('  Removed text node under LI');
                    }
                }
            } else if (mutation.type === 'characterData') {
                if (mutation.target.parentNode && mutation.target.parentNode.nodeName === 'LI') {
                    counts.textContentChanged++;
                    console.log('  Character data change in LI');
                }
            } else if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                counts.classChanged++;
                console.log('  Class changed');
            }
        }
    });

    observer.observe(panel, {
        childList: true,
        characterData: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
    });

    // Apply mutations after a short delay to let the observer start.
    setTimeout(() => {
        // 1. Remove an <li>
        const liToRemove = document.querySelector('#sotto-panel li');
        if (liToRemove) liToRemove.remove();

        // 2. Create an <li>
        const newLi = document.createElement('li');
        newLi.textContent = 'New Item';
        document.querySelector('#sotto-panel').appendChild(newLi);

        // 3. Change textContent of an existing <li>
        const liToChange = document.querySelector('#sotto-panel li:nth-child(2)');
        if (liToChange) liToChange.textContent = 'Changed Item';

        // 4. Toggle a class on an existing <li>
        const liToToggle = document.querySelector('#sotto-panel li');
        if (liToToggle) liToToggle.classList.toggle('test-class');

        // Wait a bit more for the observer to catch the mutations.
        setTimeout(() => {
            observer.disconnect();
            console.log(`Final counts: liAddedRemoved=${counts.liAddedRemoved}, textContentChanged=${counts.textContentChanged}, classChanged=${counts.classChanged}`);
            if (counts.liAddedRemoved === 2 && counts.textContentChanged === 1 && counts.classChanged === 1) {
                console.log('Self test passed');
                process.exit(0);
            } else {
                console.error(`Self test failed: liAddedRemoved=${counts.liAddedRemoved}, textContentChanged=${counts.textContentChanged}, classChanged=${counts.classChanged}`);
                process.exit(1);
            }
        }, 100);
    }, 100);
}

// Main
if (process.argv.includes('--selftest')) {
    runSelfTest();
} else {
    const args = process.argv.slice(2);
    let seconds = 5;
    if (args.length > 0 && !isNaN(args[0])) {
        seconds = parseFloat(args[0]);
    }
    runNormalMode(seconds);
}