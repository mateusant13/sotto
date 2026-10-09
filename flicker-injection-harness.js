const path = require('path');
const fs = require('fs');

const electron = require('electron');
console.log('Electron loaded:', !!electron.app);
const app = electron.app;
const BrowserWindow = electron.BrowserWindow;




function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'app/electron/flicker-preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  win.loadFile(path.join(__dirname, 'app/electron/index.html')).catch(() => {
    // If index.html doesn't exist, try to load the app directly
    win.loadURL('file://' + path.join(__dirname, 'app/electron')).catch(err => {
      console.error('Failed to load app:', err);
      win.destroy();
    });
  });

  return win;
}

async function injectOracle(win) {
  const oraclePath = path.join(__dirname, '_main', 'flicker-dom-oracle.js');
  const oracleCode = fs.readFileSync(oraclePath, 'utf8');
  
  // Execute the oracle in the renderer context
  const result = await win.webContents.executeJavaScript(oracleCode);
  return result;
}

async function runMeasurement() {
  // Ensure app is ready
  const gotTheLock = app.requestSingleInstanceLock();
  if (!gotTheLock) {
    app.quit();
    return;
  }

  app.on('second-instance', (event, commandLine, workingDirectory) => {
    // Someone tried to run a second instance, we should focus our window.
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    mainWindow = createWindow();

    mainWindow.once('ready-to-show', async () => {
      mainWindow.show();
      
      try {
        // Wait a bit for the page to fully load
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        const result = await injectOracle(mainWindow);
        console.log('Oracle result:', JSON.stringify(result));
        
        // Write result to a file for the harness to capture
        fs.writeFileSync(path.join(__dirname, 'flicker-result.json'), JSON.stringify(result, null, 2));
      } catch (err) {
        console.error('Measurement error:', err);
        fs.writeFileSync(path.join(__dirname, 'flicker-result.json'), JSON.stringify({ error: err.message }, null, 2));
      } finally {
        mainWindow.destroy();
        app.quit();
      }
    });

    mainWindow.on('closed', () => {
      mainWindow = null;
    });
  });
}

let mainWindow;
runMeasurement().catch(console.error);