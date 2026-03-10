const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');
const axios = require('axios');
const FormData = require('form-data');
require('dotenv').config();

const app = express();
app.use(bodyParser.json());

app.get('/api-docs', (req, res) => {
    res.status(200).send('WPP Server');
});

const PORT = process.env.PORT ? parseInt(process.env.PORT) : 21465;
const DEFAULT_SESSION = process.env.WPP_SESSION || 'default';
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const ADMIN_CHAT_IDS = process.env.ADMIN_CHAT_IDS ? process.env.ADMIN_CHAT_IDS.split(',').map(id => id.trim()) : [];

let client = null;
let currentQr = null;
let status = 'DISCONNECTED';
let starting = false;
let lastQrSent = null;

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendTelegramPhoto(caption, base64Data) {
    if (!TELEGRAM_BOT_TOKEN || ADMIN_CHAT_IDS.length === 0) return;

    const base64Image = base64Data.split(';base64,').pop();
    const formData = new FormData();
    const blob = new Blob([Buffer.from(base64Image, 'base64')], { type: 'image/png' });
    
    for (const chatId of ADMIN_CHAT_IDS) {
        try {
            const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto`;
            const body = new URLSearchParams();
            body.append('chat_id', chatId);
            body.append('caption', caption);
            
            // Note: Telegram API usually prefers multipart for actual files, 
            // but for simplicity here we could also send as a file stream if needed.
            // Using a simple buffer approach with axios:
            const form = {
                chat_id: chatId,
                caption: caption,
                photo: Buffer.from(base64Image, 'base64')
            };

            // Since we're in Node, we use form-data package or similar. 
            // For now, let's use a more standard Node way with axios and form-data.
        } catch (e) {
            console.error(`[Telegram] Error sending to ${chatId}:`, e.message);
        }
    }
}

// Improved Telegram sender for Node
async function notifyAdmins(message, base64Qr = null) {
    if (!TELEGRAM_BOT_TOKEN || ADMIN_CHAT_IDS.length === 0) return;

    for (const chatId of ADMIN_CHAT_IDS) {
        try {
            if (base64Qr) {
                const form = new FormData();
                const base64Image = base64Qr.split(';base64,').pop();
                const buffer = Buffer.from(base64Image, 'base64');
                
                form.append('chat_id', chatId);
                form.append('photo', buffer, { filename: 'qrcode.png' });
                form.append('caption', message);
                form.append('parse_mode', 'Markdown');

                await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto`, form, {
                    headers: form.getHeaders()
                });
            } else {
                await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
                    chat_id: chatId,
                    text: message,
                    parse_mode: 'Markdown'
                });
            }
        } catch (e) {
            console.error(`[Telegram] Error notifying ${chatId}:`, e.response?.data || e.message);
        }
    }
}

// Watchdog to ensure connection
async function startWatchdog() {
    console.log(`[Watchdog] Started for session: ${DEFAULT_SESSION}`);
    let lastStatus = null;

    while (true) {
        try {
            if (!client && !starting) {
                console.log(`[Watchdog] Client not found, starting session...`);
                await startWpp(DEFAULT_SESSION);
            } else if (client && status === 'DISCONNECTED') {
                console.log(`[Watchdog] Client disconnected, restarting...`);
                client = null;
                starting = false;
                await startWpp(DEFAULT_SESSION);
            }

            // Notify on status change to CONNECTED
            if (status !== lastStatus) {
                if (status === 'CONNECTED') {
                    await notifyAdmins("✅ *WhatsApp Conectado!*\nO servidor WPPConnect está pronto para enviar mensagens.");
                } else if (status === 'DISCONNECTED' || status === 'BROWSERCLOSE') {
                    await notifyAdmins("⚠️ *WhatsApp Desconectado!*\nO servidor tentará reconectar automaticamente.");
                }
                lastStatus = status;
            }

        } catch (e) {
            console.error('[Watchdog] Error:', e);
        }
        await sleep(10000); // Check every 10 seconds
    }
}

// Initialize session
async function startWpp(sessionName) {
    if (client || starting) return;
    starting = true;

    status = 'STARTING';
    try {
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
        
        client = await wppconnect.create({
            session: sessionName,
            userDataDir: path.join('./tokens', sessionName, 'userData'),
            catchQR: (base64Qr, asciiQR) => {
                currentQr = base64Qr && base64Qr.startsWith('data:') ? base64Qr : `data:image/png;base64,${base64Qr}`;
                status = 'QRCODE';
                
                // Auto send QR to Telegram if it's new
                if (currentQr !== lastQrSent) {
                    console.log('[WPP] New QR Code generated, sending to Telegram...');
                    notifyAdmins("📲 *Novo QR Code do WhatsApp*\nEscaneie para conectar o servidor.", currentQr);
                    lastQrSent = currentQr;
                }
            },
            statusFind: (statusSession, session) => {
                console.log(`[WPP] Status: ${statusSession}`);
                if (statusSession === 'inChat' || statusSession === 'isLogged') {
                    status = 'CONNECTED';
                    currentQr = null;
                    lastQrSent = null;
                } else {
                    status = statusSession.toUpperCase();
                    if (statusSession === 'autocloseCalled' || statusSession === 'browserClose' || statusSession === 'qrReadSuccess') {
                        if (statusSession === 'qrReadSuccess') {
                            console.log('[WPP] QR Code read successfully!');
                        } else {
                            try { client && client.close(); } catch {}
                            client = null;
                            currentQr = null;
                            starting = false;
                        }
                    }
                }
            },
            folderNameToken: tokensRoot,
            tokenStore: 'file',
            headless: true,
            devtools: false,
            useChrome: !!executablePath,
            debug: false,
            logQR: false,
            autoClose: 0,
            waitForLogin: true,
            updatesLog: false,
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
                headless: true
            }
        });
        
        try {
            await client.start();
        } catch (e) {
            console.error('Error on client.start()', e);
        }
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
    }
    const waitQr = !!(req.body && req.body.waitQrCode);

    if (!waitQr) {
        return res.json({ status: status, qrcode: currentQr });
    }

    // Wait up to 60s for QR or connection
    const start = Date.now();
    while (Date.now() - start < 60000) {
        if (!client && !starting) {
            startWpp(session);
        }
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
    startWatchdog();
});
