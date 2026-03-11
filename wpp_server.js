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
let lastTelegramMsgId = null;
let retryCount = 0; // Contador de retentativas de inicialização

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
                // Remove o QR anterior antes de enviar o novo
                if (lastTelegramMsgId) {
                    await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteMessage`, {
                        chat_id: chatId,
                        message_id: lastTelegramMsgId
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
                    lastTelegramMsgId = resp.data.result.message_id;
                    log('DEBUG', `Novo lastTelegramMsgId: ${lastTelegramMsgId}`);
                }
            } else {
                // Se for mensagem de conexão, TENTA EDITAR A LEGENDA DA FOTO ORIGINAL
                let edited = false;
                if (lastTelegramMsgId && (message.includes('Conectado') || message.includes('sucesso'))) {
                    try {
                        const editResp = await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/editMessageCaption`, {
                            chat_id: chatId,
                            message_id: lastTelegramMsgId,
                            caption: message,
                            parse_mode: 'Markdown'
                        });
                        if (editResp.data && editResp.data.ok) {
                            edited = true;
                            log('DEBUG', 'Legenda do QR Code editada com sucesso');
                        }
                    } catch (e) {
                        log('WARN', 'Não foi possível editar a legenda, enviando nova mensagem');
                    }
                }

                // Se não era para editar ou a edição falhou, envia mensagem normal
                if (!edited) {
                    const sendResp = await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
                        chat_id: chatId,
                        text: message,
                        parse_mode: 'Markdown'
                    });
                    if (sendResp.data && sendResp.data.ok && !base64Qr) {
                        // Não atualizamos lastTelegramMsgId aqui para não perder a referência da foto se for apenas um aviso
                    }
                }
            }
        } catch (e) {
            log('ERROR', `Erro Telegram: ${e.message}`);
        }
    }
}

async function initializeClient() {
    if (client || starting) return;
    starting = true;
    status = 'STARTING';
    currentQr = null;
    // Não resetamos qrCount aqui para ele acumular entre retentativas de browserClose

    log('INFO', `Iniciando sessão '${SESSION_NAME}' (Tentativa ${retryCount + 1})`);

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
            folderNameToken: tokensPath,
            mkdirFolderToken: true,
            tokenStore: 'file',
            catchQR: (base64Qr) => {
                currentQr = base64Qr.startsWith('data:') ? base64Qr : `data:image/png;base64,${base64Qr}`;
                status = 'QRCODE';
                qrCount++;
                
                log('INFO', `QR Code gerado (${qrCount}º)`);
                notifyTelegram(`📲 *${qrCount}º QR Code do WhatsApp*\nEscaneie para conectar o servidor.`, currentQr);
            },
            statusFind: (statusSession) => {
                log('INFO', `Status: ${statusSession}`);
                if (statusSession === 'inChat' || statusSession === 'isLogged' || statusSession === 'qrReadSuccess') {
                    const wasAlreadyConnected = (status === 'CONNECTED');
                    status = 'CONNECTED';
                    currentQr = null;
                    retryCount = 0; // Reseta retentativas em caso de sucesso
                    
                    if (!wasAlreadyConnected && qrCount > 0) {
                        notifyTelegram("✅ *WhatsApp Conectado com sucesso!*");
                        qrCount = 0; 
                    }
                } else if (statusSession === 'notLogged' || statusSession === 'desconnectedMobile') {
                    status = 'DISCONNECTED';
                } else if (statusSession === 'browserClose' || statusSession === 'autocloseCalled') {
                    status = 'DISCONNECTED';
                    const wasStarting = starting;
                    client = null;
                    starting = false;

                    // Se fechou sozinho enquanto tentava iniciar, tenta de novo após um delay
                    if (wasStarting && retryCount < 5) {
                        retryCount++;
                        log('WARN', `Browser fechou durante inicialização. Retentando em 5s... (${retryCount}/5)`);
                        setTimeout(initializeClient, 5000);
                    }
                }
            },
            headless: true,
            useChrome: !!executablePath,
            autoClose: 0,
            waitForLogin: true,
            disableWelcome: true,
            updatesLog: false,
            debug: false,
            linkPreview: false,
            disableAutoClose: true,
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
                    `--user-data-dir=${userDataPath}`,
                    '--disable-extensions'
                ]
            }
        });

        // Garantia extra pós-criação
        try {
            if (client && typeof client.disableAutoClose === 'function') {
                await client.disableAutoClose();
                log('DEBUG', 'AutoClose desativado via função');
            }
        } catch (e) {}

        starting = false;
    } catch (error) {
        log('ERROR', `Erro fatal na inicialização: ${error ? error.message : 'Desconhecido'}`);
        status = 'DISCONNECTED';
        client = null;
        starting = false;
        
        if (retryCount < 5) {
            retryCount++;
            log('INFO', `Falha na criação do cliente. Retentando em 10s... (${retryCount}/5)`);
            setTimeout(initializeClient, 10000);
        } else {
            notifyTelegram(`❌ *Erro Crítico no Servidor WPP*\nNão foi possível iniciar após 5 tentativas.`);
        }
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
