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

// Caminhos fixos e isolados para garantir que não use nada global
const tokensPath = path.join(__dirname, 'tokens');
const sessionPath = path.join(tokensPath, SESSION_NAME);
const userDataPath = path.join(sessionPath, 'userData');

// Garante que a pasta base existe
if (!fs.existsSync(tokensPath)) fs.mkdirSync(tokensPath, { recursive: true });

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

    console.log(`[WPP] Starting session '${SESSION_NAME}'`);
    console.log(`[WPP] Tokens: ${tokensPath}`);
    console.log(`[WPP] UserData: ${userDataPath}`);

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

        console.log(`[WPP] Session persistence: ${tokensPath}`);
        if (!fs.existsSync(tokensPath)) {
            console.log(`[WPP] Persistence folder not found, a new QR will be generated.`);
        }

        client = await wppconnect.create({
            session: SESSION_NAME,
            folderNameToken: tokensPath,
            mkdirFolderToken: true,
            tokenStore: 'file',
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
                console.log(`[WPP] statusFind: ${statusSession}`);
                if (statusSession === 'inChat' || statusSession === 'isLogged' || statusSession === 'qrReadSuccess') {
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
            autoClose: false,
            waitForLogin: true,
            disableWelcome: true,
            updatesLog: false,
            debug: false,
            puppeteerOptions: {
                userDataDir: userDataPath, // ISOLAMENTO TOTAL AQUI
                executablePath: executablePath,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-first-run',
                    '--no-zygote',
                    '--window-size=1280,720',
                    '--disable-blink-features=AutomationControlled',
                    `--user-data-dir=${userDataPath}` // Força o diretório de dados do usuário via flag também
                ]
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
    let startupTime = Date.now();

    while (true) {
        try {
            if (!client && !starting) {
                await startWpp();
                startupTime = Date.now();
            } else if (client && status === 'CONNECTED' && !starting) {
                // Grace period: Espera 60s após conectar antes de começar a matar por isLoggedIn
                if (Date.now() - startupTime > 60000) {
                    const isLoggedIn = await client.isLoggedIn().catch(() => null);
                    if (isLoggedIn === false) {
                        console.log('[Watchdog] isLoggedIn returned false. Session expired, resetting...');
                        status = 'DISCONNECTED';
                        try { await client.close(); } catch (e) {}
                        client = null;
                    }
                }
            }
        } catch (e) {
            console.error('[Watchdog] Error:', e.message);
            if (e.message.includes('browser has disconnected')) {
                client = null;
                starting = false;
                status = 'DISCONNECTED';
            }
        }
        await sleep(30000);
    }
}

// Endpoints
// Endpoints API REST

// Status Completo
app.get('/api/status', async (req, res) => {
    let extra = {};
    if (client && status === 'CONNECTED') {
        try {
            extra = {
                isLoggedIn: await client.isLoggedIn(),
                connectionState: await client.getConnectionState(),
                battery: await client.getBatteryLevel().catch(() => 'N/A'),
                isReady: true
            };
        } catch (e) {}
    }
    
    res.json({
        status: 'success',
        session: SESSION_NAME,
        internalStatus: status,
        starting: starting,
        hasQr: !!currentQr,
        ...extra
    });
});

// Enviar Mensagem de Texto
app.post('/api/send-message', async (req, res) => {
    if (status !== 'CONNECTED' || !client) {
        return res.status(400).json({ 
            status: 'error', 
            message: status === 'QRCODE' ? 'Necessário ler QR Code' : 'WhatsApp não está conectado',
            state: status 
        });
    }
    
    const { phone, message, groupId } = req.body;
    if (!message || (!phone && !groupId)) {
        return res.status(400).json({ status: 'error', message: 'Parâmetros insuficientes' });
    }

    try {
        const dest = groupId || (phone.includes('@') ? phone : `${phone}@c.us`);
        const result = await client.sendText(dest, message);
        res.json({ status: 'success', result });
    } catch (e) {
        console.error(`[API] Falha ao enviar mensagem para ${phone || groupId}`, e.message);
        res.status(500).json({ status: 'error', message: e.toString() });
    }
});

// Enviar Arquivo/Imagem
app.post('/api/send-file', async (req, res) => {
    if (status !== 'CONNECTED' || !client) {
        return res.status(400).json({ 
            status: 'error', 
            message: status === 'QRCODE' ? 'Necessário ler QR Code' : 'WhatsApp não está conectado',
            state: status 
        });
    }

    const { phone, groupId, url, caption, fileName } = req.body;
    if (!url || (!phone && !groupId)) {
        return res.status(400).json({ status: 'error', message: 'Parâmetros insuficientes' });
    }

    try {
        const dest = groupId || (phone.includes('@') ? phone : `${phone}@c.us`);
        const result = await client.sendFile(dest, url, fileName || 'arquivo', caption || '');
        res.json({ status: 'success', result });
    } catch (e) {
        console.error(`[API] Falha ao enviar arquivo para ${phone || groupId}`, e.message);
        res.status(500).json({ status: 'error', message: e.toString() });
    }
});

// Health Check Simples para os Scrapers
app.get('/api/:session/check-connection-state', (req, res) => {
    res.json({ status: 'success', state: status });
});

// Inicialização do Servidor Express
app.listen(PORT, '0.0.0.0', async () => {
    log('INFO', `WPPConnect Bridge Server rodando na porta ${PORT}`);
    // Inicia o WhatsApp imediatamente ao subir o servidor
    await initializeClient();
});
