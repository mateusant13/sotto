const { app } = require('electron');
app.whenReady().then(() => { console.log('ELECTRON_OK'); app.exit(0); });
