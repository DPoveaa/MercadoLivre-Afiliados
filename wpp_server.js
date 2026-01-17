const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(bodyParser.json());
app.use((req, res, next) => {
    console.log(`[REQ] ${req.method} ${req.url}`);
    next();
});

app.get('/api-docs', (req, res) => {
    res.status(200).send('WPP Server');
});

const PORT = process.env.PORT ? parseInt(process.env.PORT) : 21465;
let client = null;
let currentQr = null;
let status = 'DISCONNECTED';
let starting = false;

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// Initialize session
async function startWpp(sessionName) {
    if (client || starting) return;
    starting = true;

    status = 'STARTING';
    try {
        console.log(`[WPP] startWpp session=${sessionName} platform=${process.platform} pm2=${process.env.pm_id || ''} PORT=${PORT}`);
        const isLinux = process.platform === 'linux';
        let executablePath = undefined;
        if (isLinux) {
            const candidates = ['/usr/bin/google-chrome', '/usr/bin/chromium-browser', '/snap/bin/chromium', '/usr/bin/chromium'];
            for (const p of candidates) {
                try {
                    if (fs.existsSync(p)) {
                        executablePath = p;
                        break;
                    }
                } catch {}
            }
        }
        const tokensRoot = './tokens';
        try {
            fs.mkdirSync(path.join(tokensRoot, sessionName), { recursive: true });
        } catch {}
        console.log(`[WPP] executablePath=${executablePath || 'puppeteer'} useChrome=${!!executablePath} tokensRoot=${tokensRoot}`);
        client = await wppconnect.create({
            session: sessionName,
            userDataDir: path.join('./tokens', sessionName, 'userData'),
            catchQR: (base64Qr, asciiQR) => {
                currentQr = base64Qr && base64Qr.startsWith('data:') ? base64Qr : `data:image/png;base64,${base64Qr}`;
                console.log(`[WPP] QR captured len=${currentQr ? currentQr.length : 0}`);
                status = 'QRCODE';
            },
            statusFind: (statusSession, session) => {
                if (statusSession === 'inChat' || statusSession === 'isLogged') {
                    console.log(`[WPP] statusFind=${statusSession} -> CONNECTED`);
                    status = 'CONNECTED';
                    currentQr = null;
                } else {
                    console.log(`[WPP] statusFind=${statusSession}`);
                    status = statusSession.toUpperCase();
                    if (statusSession === 'autocloseCalled' || statusSession === 'browserClose') {
                        console.log('[WPP] browser closed, resetting client');
                        try { client && client.close(); } catch {}
                        client = null;
                        currentQr = null;
                        starting = false;
                    }
                }
            },
            folderNameToken: tokensRoot,
            tokenStore: 'file',
            headless: true,
            devtools: false,
            useChrome: !!executablePath,
            debug: true,
            logQR: true,
            autoClose: -1,
            waitForLogin: true,
            updatesLog: true,
            browserArgs: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--remote-debugging-port=9222',
                '--window-size=1280,720',
                '--disable-features=VizDisplayCompositor',
                '--disable-blink-features=AutomationControlled'
            ],
            puppeteerOptions: {
                executablePath: executablePath,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-dev-tools',
                    '--disable-software-rasterizer',
                    '--remote-debugging-port=9222',
                    '--window-size=1280,720',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-blink-features=AutomationControlled'
                ],
                headless: 'new'
            }
        });
        // Do not call client.start() to avoid premature auto close behavior; QR will be captured via catchQR.
        console.log('[WPP] client created');
        starting = false;
    } catch (error) {
        console.error('Error starting WPPConnect:', error);
        status = 'errored';
        starting = false;
    }
}

// Endpoints mock the wppconnect-server structure

app.post('/api/:session/start-session', async (req, res) => {
    const session = req.params.session;
    if (!client) {
        startWpp(session); // Async start
    } else {
        console.log('[API] start-session client already exists');
    }
    const waitQr = !!(req.body && req.body.waitQrCode);
    console.log(`[API] start-session session=${session} waitQr=${waitQr}`);

    if (!waitQr) {
        console.log(`[API] start-session immediate status=${status} hasQr=${!!currentQr}`);
        return res.json({ status: status, qrcode: currentQr });
    }

    // Wait up to 60s for QR or connection
    const start = Date.now();
    while (Date.now() - start < 60000) {
        if (!client && !starting) {
            console.log('[API] start-session restarting client...');
            startWpp(session);
        }
        if (currentQr) {
            console.log('[API] start-session returning QR');
            return res.json({ status: status, qrcode: currentQr });
        }
        if (status === 'CONNECTED') {
            console.log('[API] start-session connected');
            return res.json({ status: status });
        }
        await sleep(500);
    }
    console.log(`[API] start-session timeout status=${status} hasQr=${!!currentQr}`);
    res.json({ status: status, qrcode: currentQr });
});

app.get('/api/:session/check-connection-state', (req, res) => {
    console.log(`[API] check-connection-state state=${status}`);
    res.json({ status: 'success', state: status });
});

app.get('/api/:session/getQrCode', (req, res) => {
    console.log(`[API] getQrCode hasQr=${!!currentQr}`);
    res.json({ qrcode: currentQr });
});

app.get('/api/:session/status-session', (req, res) => {
    console.log(`[API] status-session ${status}`);
    res.status(200).send(status);
});

app.post('/api/:session/send-message', async (req, res) => {
    if (!client || status !== 'CONNECTED') {
        console.log('[API] send-message not connected');
        return res.status(400).json({ status: 'error', message: 'Not connected' });
    }
    const { phone, message, groupId } = req.body;
    try {
        console.log(`[API] send-message groupId=${groupId || ''} phone=${phone || ''}`);
        let result;
        if (groupId) {
            result = await client.sendText(groupId, message);
        } else if (phone) {
            // Ensure phone format
            let dest = phone.includes('@') ? phone : `${phone}@c.us`;
            result = await client.sendText(dest, message);
        }
        console.log('[API] send-message success');
        res.json({ status: 'success', response: result });
    } catch (error) {
        console.log(`[API] send-message error ${error}`);
        res.status(500).json({ status: 'error', error: error.toString() });
    }
});

app.post('/api/:session/send-group-message', async (req, res) => {
    if (!client || status !== 'CONNECTED') {
        console.log('[API] send-group-message not connected');
        return res.status(400).json({ status: 'error', message: 'Not connected' });
    }
    const { groupId, message } = req.body;
    try {
        console.log(`[API] send-group-message groupId=${groupId}`);
        const result = await client.sendText(groupId, message);
        console.log('[API] send-group-message success');
        res.json({ status: 'success', response: result });
    } catch (error) {
        console.log(`[API] send-group-message error ${error}`);
        res.status(500).json({ status: 'error', error: error.toString() });
    }
});

app.post('/api/:session/send-file', async (req, res) => {
    if (!client || status !== 'CONNECTED') {
        console.log('[API] send-file not connected');
        return res.status(400).json({ status: 'error', message: 'Not connected' });
    }
    // Simplification: expects 'url' (image url) setup in scraper
    const { phone, groupId, url, caption, fileName } = req.body;
    try {
        console.log(`[API] send-file groupId=${groupId || ''} phone=${phone || ''} urlLen=${url ? url.length : 0}`);
        let result;
        if (groupId) {
            result = await client.sendFile(groupId, url, fileName, caption);
        } else if (phone) {
            let dest = phone.includes('@') ? phone : `${phone}@c.us`;
            result = await client.sendFile(dest, url, fileName, caption);
        }
        console.log('[API] send-file success');
        res.json({ status: 'success', response: result });
    } catch (error) {
        console.log(`[API] send-file error ${error}`);
        res.status(500).json({ status: 'error', error: error.toString() });
    }
});


app.listen(PORT, () => {
    console.log(`WPPConnect Bridge Server http://localhost:${PORT}/`);
});
