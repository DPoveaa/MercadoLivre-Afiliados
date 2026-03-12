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
let qrCount = 0;
let lastTelegramMsgIds = {}; // Objeto para rastrear MsgID por ChatID

// Caminhos fixos e isolados
const tokensPath = path.join(__dirname, 'tokens');
const sessionPath = path.join(tokensPath, SESSION_NAME);
const userDataPath = path.join(sessionPath, 'userData');

// Garante que a pasta base existe
if (!fs.existsSync(tokensPath)) fs.mkdirSync(tokensPath, { recursive: true });

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function log(level, message) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${level}] ${message}`);
}

async function notifyTelegram(message, base64Qr = null) {
    if (!TELEGRAM_BOT_TOKEN || ADMIN_CHAT_IDS.length === 0) return;

    for (const chatId of ADMIN_CHAT_IDS) {
        try {
            if (base64Qr) {
                // Se for um novo QR, deleta o anterior (se houver) e manda o novo
                if (lastTelegramMsgIds[chatId]) {
                    await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteMessage`, {
                        chat_id: chatId,
                        message_id: lastTelegramMsgIds[chatId]
                    }).catch(() => {});
                }

                const form = new FormData();
                const base64Image = base64Qr.split(';base64,').pop();
                const buffer = Buffer.from(base64Image, 'base64');
                
                form.append('chat_id', chatId);
                form.append('photo', buffer, { filename: 'qrcode.png' });
                form.append('caption', message);
                form.append('parse_mode', 'Markdown');

                const resp = await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto`, form, {
                    headers: form.getHeaders(),
                    timeout: 30000
                });
                
                if (resp.data && resp.data.ok) {
                    lastTelegramMsgIds[chatId] = resp.data.result.message_id;
                }
            } else {
                // Se for uma mensagem de texto (ex: sucesso de conexão)
                // Remove o QR anterior deste chat específico se ele ainda existir
                if (lastTelegramMsgIds[chatId]) {
                    await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteMessage`, {
                        chat_id: chatId,
                        message_id: lastTelegramMsgIds[chatId]
                    }).catch(() => {});
                    delete lastTelegramMsgIds[chatId];
                }

                await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
                    chat_id: chatId,
                    text: message,
                    parse_mode: 'Markdown'
                });
            }
        } catch (e) {
            log('ERROR', `Erro Telegram (${chatId}): ${e.message}`);
        }
    }
}

async function initializeClient() {
    if (client || starting) return;
    starting = true;
    status = 'STARTING';
    currentQr = null;

    try {
        log('INFO', `Iniciando sessão '${SESSION_NAME}' (Metodologia: Keep-Alive)`);
        
        // Verifica se existem tokens salvos para debug
        const tokenFile = path.join(tokensPath, `${SESSION_NAME}.data.json`);
        if (fs.existsSync(tokenFile)) {
            log('INFO', `Token de sessão encontrado: ${tokenFile}`);
        } else {
            log('WARN', `Nenhum token de sessão encontrado. Novo login será necessário.`);
        }

        const isLinux = process.platform === 'linux';
        const isWin = process.platform === 'win32';
        let executablePath = undefined;

        if (isLinux) {
            const candidates = ['/usr/bin/google-chrome', '/usr/bin/chromium-browser', '/snap/bin/chromium', '/usr/bin/chromium'];
            for (const p of candidates) {
                if (fs.existsSync(p)) { executablePath = p; break; }
            }
        } else if (isWin) {
            const candidates = [
                'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe')
            ];
            for (const p of candidates) {
                if (fs.existsSync(p)) { executablePath = p; break; }
            }
        }

        // REMOVIDO: Limpeza automática que deletava a sessão a cada reinício
        // Agora só limpamos se houver um erro crítico ou manual.

        client = await wppconnect.create({
            session: SESSION_NAME,
            folderNameToken: tokensPath,
            mkdirFolderToken: true,
            catchQR: (base64Qr) => {
                currentQr = base64Qr.startsWith('data:') ? base64Qr : `data:image/png;base64,${base64Qr}`;
                status = 'QRCODE';
                qrCount++;
                log('INFO', `QR Code gerado (${qrCount}º)`);
                notifyTelegram(`📲 *${qrCount}º QR Code do WhatsApp*\nEscaneie agora para conectar o servidor.`, currentQr);
            },
            statusFind: (statusSession) => {
                log('INFO', `Status da Sessão: ${statusSession}`);
                
                if (statusSession === 'isLogged' || statusSession === 'inChat' || statusSession === 'qrReadSuccess') {
                    if (status !== 'CONNECTED') {
                        status = 'CONNECTED';
                        currentQr = null;
                        notifyTelegram("✅ *WhatsApp Conectado!*\nO servidor está pronto para enviar mensagens.");
                        log('INFO', 'WhatsApp conectado e pronto!');
                    }
                }

                if (statusSession === 'desconnectedMobile' || statusSession === 'notLogged') {
                    status = 'DISCONNECTED';
                    log('WARN', 'WhatsApp desconectado no celular.');
                }

                if (statusSession === 'browserClose' || statusSession === 'autocloseCalled') {
                    log('WARN', 'Navegador fechado. Tentando reiniciar em 10s...');
                    client = null;
                    status = 'DISCONNECTED';
                    starting = false;
                    setTimeout(initializeClient, 10000);
                }
            },
            headless: true,
            useChrome: false,
            autoClose: false,
            waitForLogin: false,
            logQR: true,
            puppeteerOptions: {
                userDataDir: userDataPath,
                executablePath: executablePath,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-first-run',
                    '--no-zygote',
                    '--window-size=1280,720',
                    '--disable-extensions'
                ]
            }
        });

        // Metodologia Keep-Alive: O cliente fica aberto permanentemente
        log('INFO', 'Cliente WPP iniciado com sucesso (Keep-Alive ativo)');
        starting = false;

    } catch (error) {
        log('ERROR', `Erro na inicialização: ${error.message}`);
        status = 'DISCONNECTED';
        client = null;
        starting = false;
        setTimeout(initializeClient, 10000);
    }
}

// Endpoints API REST

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

app.post('/api/send-message', async (req, res) => {
    log('DEBUG', `Recebida solicitação de envio. Status atual: ${status}`);
    
    if (status !== 'CONNECTED' || !client) {
        log('WARN', `Tentativa de envio sem conexão. Status: ${status}`);
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
        log('ERROR', `Falha envio msg: ${e.message}`);
        res.status(500).json({ status: 'error', message: e.toString() });
    }
});

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
        log('ERROR', `Falha envio arquivo: ${e.message}`);
        res.status(500).json({ status: 'error', message: e.toString() });
    }
});

app.get('/api/:session/check-connection-state', (req, res) => {
    res.json({ status: 'success', state: status });
});

// Inicialização
app.listen(PORT, '0.0.0.0', async () => {
    log('INFO', `WPPConnect Bridge Server na porta ${PORT}`);
    await initializeClient();
});
