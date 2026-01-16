const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(bodyParser.json());

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
        const tokensRoot = path.join(__dirname, 'tokens');
        client = await wppconnect.create({
            session: sessionName,
            catchQR: (base64Qr, asciiQR) => {
                currentQr = base64Qr && base64Qr.startsWith('data:') ? base64Qr : `data:image/png;base64,${base64Qr}`;
                status = 'QRCODE';
            },
            statusFind: (statusSession, session) => {
                if (statusSession === 'inChat' || statusSession === 'isLogged' || statusSession === 'qrReadSuccess') {
                    status = 'CONNECTED';
                    currentQr = null;
                } else {
                    status = statusSession.toUpperCase();
                }
            },
            folderNameToken: tokensRoot,
            tokenStore: 'file',
            headless: true,
            devtools: false,
            useChrome: false, // Use bundled chromium from puppeteer
            debug: true,
            logQR: false,
            autoClose: false,
            updatesLog: true,
            browserArgs: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        });
        // Do not call client.start() to avoid premature auto close behavior; QR will be captured via catchQR.
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
    startWpp(session); // Async start
    const waitQr = !!(req.body && req.body.waitQrCode);

    if (!waitQr) {
        return res.json({ status: status, qrcode: currentQr });
    }

    // Wait up to 60s for QR or connection
    const start = Date.now();
    while (Date.now() - start < 60000) {
        if (currentQr) {
            return res.json({ status: status, qrcode: currentQr });
        }
        if (status === 'CONNECTED') {
            return res.json({ status: status });
        }
        await sleep(500);
    }
    res.json({ status: status, qrcode: currentQr });
});

app.get('/api/:session/check-connection-state', (req, res) => {
    res.json({ status: 'success', state: status });
});

app.get('/api/:session/getQrCode', (req, res) => {
    res.json({ qrcode: currentQr });
});

app.get('/api/:session/status-session', (req, res) => {
    res.status(200).send(status);
});

app.post('/api/:session/send-message', async (req, res) => {
    if (!client || status !== 'CONNECTED') {
        return res.status(400).json({ status: 'error', message: 'Not connected' });
    }
    const { phone, message, groupId } = req.body;
    try {
        let result;
        if (groupId) {
            result = await client.sendText(groupId, message);
        } else if (phone) {
            // Ensure phone format
            let dest = phone.includes('@') ? phone : `${phone}@c.us`;
            result = await client.sendText(dest, message);
        }
        res.json({ status: 'success', response: result });
    } catch (error) {
        res.status(500).json({ status: 'error', error: error.toString() });
    }
});

app.post('/api/:session/send-group-message', async (req, res) => {
    if (!client || status !== 'CONNECTED') {
        return res.status(400).json({ status: 'error', message: 'Not connected' });
    }
    const { groupId, message } = req.body;
    try {
        const result = await client.sendText(groupId, message);
        res.json({ status: 'success', response: result });
    } catch (error) {
        res.status(500).json({ status: 'error', error: error.toString() });
    }
});

app.post('/api/:session/send-file', async (req, res) => {
    if (!client || status !== 'CONNECTED') {
        return res.status(400).json({ status: 'error', message: 'Not connected' });
    }
    // Simplification: expects 'url' (image url) setup in scraper
    const { phone, groupId, url, caption, fileName } = req.body;
    try {
        let result;
        if (groupId) {
            result = await client.sendFile(groupId, url, fileName, caption);
        } else if (phone) {
            let dest = phone.includes('@') ? phone : `${phone}@c.us`;
            result = await client.sendFile(dest, url, fileName, caption);
        }
        res.json({ status: 'success', response: result });
    } catch (error) {
        res.status(500).json({ status: 'error', error: error.toString() });
    }
});


app.listen(PORT, () => {
    console.log(`WPPConnect Bridge Server http://localhost:${PORT}/`);
});
