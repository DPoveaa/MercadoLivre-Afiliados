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

const PORT = process.env.PORT ? parseInt(process.env.PORT) : 21465;
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const ADMIN_CHAT_IDS = process.env.ADMIN_CHAT_IDS ? process.env.ADMIN_CHAT_IDS.split(',').map(id => id.trim()) : [];
const SESSION_NAME = 'default';

let client = null;
let currentQr = null;
let status = 'DISCONNECTED';
let starting = false;
let lastQrSent = null;

// Pasta fixa para persistência da sessão
const tokensPath = path.join(__dirname, 'tokens');

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

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

async function startWpp() {
    if (client || starting) return;
    starting = true;
    status = 'STARTING';
    currentQr = null;

    console.log(`[WPP] Starting session '${SESSION_NAME}' with persistence in ${tokensPath}`);

    try {
        const isLinux = process.platform === 'linux';
        let executablePath = undefined;
        if (isLinux) {
            const candidates = ['/usr/bin/google-chrome', '/usr/bin/chromium-browser', '/snap/bin/chromium', '/usr/bin/chromium'];
            for (const p of candidates) {
                if (fs.existsSync(p)) {
                    executablePath = p;
                    break;
                }
            }
        }

        client = await wppconnect.create({
            session: SESSION_NAME,
            folderNameToken: tokensPath, // Pasta raiz para os tokens
            mkdirFolderToken: tokensPath, // Força a criação da pasta
            catchQR: (base64Qr) => {
                currentQr = base64Qr.startsWith('data:') ? base64Qr : `data:image/png;base64,${base64Qr}`;
                status = 'QRCODE';
                
                if (currentQr !== lastQrSent) {
                    console.log('[WPP] QR Code generated, notifying admins...');
                    notifyAdmins("📲 *Novo QR Code do WhatsApp*\nEscaneie para conectar e manter a sessão.", currentQr);
                    lastQrSent = currentQr;
                }
            },
            statusFind: (statusSession) => {
                console.log(`[WPP] Status event: ${statusSession}`);
                if (statusSession === 'inChat' || statusSession === 'isLogged') {
                    status = 'CONNECTED';
                    currentQr = null;
                    lastQrSent = null;
                } else if (statusSession === 'notLogged' || statusSession === 'desconnectedMobile') {
                    status = 'DISCONNECTED';
                } else if (statusSession === 'browserClose' || statusSession === 'autocloseCalled') {
                    status = 'DISCONNECTED';
                    client = null;
                    starting = false;
                }
            },
            headless: true,
            useChrome: !!executablePath,
            autoClose: 0,
            waitForLogin: true,
            disableWelcome: true,
            updatesLog: false,
            debug: false,
            browserArgs: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-zygote',
                '--window-size=1280,720',
                '--disable-blink-features=AutomationControlled'
            ],
            puppeteerOptions: {
                executablePath: executablePath
            }
        });

        // Tenta desativar autoClose explicitamente se a versão do pacote suportar
        try {
            if (client && typeof client.disableAutoClose === 'function') {
                await client.disableAutoClose();
            }
        } catch (e) {}

        starting = false;
    } catch (error) {
        console.error('[WPP] Fatal error starting:', error);
        status = 'DISCONNECTED';
        client = null;
        starting = false;
    }
}

async function startWatchdog() {
    console.log('[Watchdog] Monitoring connection...');
    while (true) {
        try {
            if (!client && !starting) {
                await startWpp();
            } else if (client && !starting) {
                const isLoggedIn = await client.isLoggedIn().catch(() => false);
                if (!isLoggedIn && status === 'CONNECTED') {
                    console.log('[Watchdog] Session expired or disconnected, resetting...');
                    status = 'DISCONNECTED';
                    try { await client.close(); } catch (e) {}
                    client = null;
                }
            }
        } catch (e) {
            console.error('[Watchdog] Error:', e.message);
        }
        await sleep(20000);
    }
}

// Endpoints
app.get('/api/:session/check-connection-state', (req, res) => {
    res.json({ status: 'success', state: status });
});

app.get('/api-docs', (req, res) => res.send('WPP Server Active'));

app.post('/api/:session/send-message', async (req, res) => {
    if (status !== 'CONNECTED' || !client) return res.status(400).json({ status: 'error', message: 'Not connected' });
    const { phone, message, groupId } = req.body;
    try {
        const dest = groupId || (phone.includes('@') ? phone : `${phone}@c.us`);
        const result = await client.sendText(dest, message);
        res.json({ status: 'success', result });
    } catch (e) {
        res.status(500).json({ status: 'error', message: e.toString() });
    }
});

app.post('/api/:session/send-file', async (req, res) => {
    if (status !== 'CONNECTED' || !client) return res.status(400).json({ status: 'error', message: 'Not connected' });
    const { phone, groupId, url, caption, fileName } = req.body;
    try {
        const dest = groupId || (phone.includes('@') ? phone : `${phone}@c.us`);
        const result = await client.sendFile(dest, url, fileName, caption);
        res.json({ status: 'success', result });
    } catch (e) {
        res.status(500).json({ status: 'error', message: e.toString() });
    }
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
    startWatchdog();
});
